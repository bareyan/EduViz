"""
Manim Generator - New Pipeline Implementation

Handles the multi-stage animation generation workflow:
1. Choreograph: Plan visuals from narration
2. Implement: Convert plans to Manim code
3. Refine: Automated fixing with static and runtime validation
4. Render: Produce final video sections
"""

from typing import Dict, Any, Optional
from pathlib import Path

from app.core import get_logger
from app.services.infrastructure.llm import PromptingEngine, CostTracker
from app.utils.section_status import write_status, SectionState

from .orchestrator import AnimationOrchestrator
from .core import (
    RefinementError,
    ImplementationError,
    RenderingError, 
    create_scene_file, 
    render_scene,
    AnimationFileManager
)
from .core.validation import VisionValidator
from ..config import (
    ENABLE_VISION_QC,
    MAX_CLEAN_RETRIES,
)
from .constants import DEFAULT_THEME_CODE

logger = get_logger(__name__, component="manim_generator")


class ManimGenerator:
    """
    Manim Animation Orchestrator.
    
    Coordinates the multi-stage pipeline (Choreograph -> Implement -> Refine)
    and handles rendering. Follows SRP by delegating generation stages to 
    dedicated processor classes.
    """

    def __init__(self, pipeline_name: Optional[str] = None):
        self.pipeline_name = pipeline_name

        # Infrastructure
        self.cost_tracker = CostTracker()
        
        # Services
        self.file_manager = AnimationFileManager()
        
        # Initialize the Animation Orchestrator (Modular Architecture)
        self.orchestrator = AnimationOrchestrator(
            engine=PromptingEngine("animation_implementation", self.cost_tracker, pipeline_name=pipeline_name),
            cost_tracker=self.cost_tracker
        )

        self.vision_engine = PromptingEngine(
            "visual_qc",
            self.cost_tracker,
            pipeline_name=pipeline_name,
        )
        self.vision_validator = VisionValidator(self.vision_engine)

        # Execution stats
        self.stats = {
            "total_sections": 0,
            "failed_sections": [],
            "skipped_sections": 0
        }

    def get_cost_summary(self) -> Dict[str, Any]:
        """Get cost summary"""
        return self.cost_tracker.get_summary()

    def print_cost_summary(self):
        """Print cost summary"""
        self.cost_tracker.print_summary()

    async def generate_animation(
        self,
        section: Dict[str, Any],
        output_dir: str,
        section_index: int,
        audio_duration: float,
        style: str = DEFAULT_THEME_CODE,
        job_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Orchestrates the animation generation pipeline for a section.
        
        Args:
            section: Section metadata from narration stage.
            output_dir: Where to save generated code and video.
            section_index: Index of the current section.
            audio_duration: Duration of the narration audio.
            style: Visual style (e.g., '3b1b').
            job_id: Optional job identifier for logging context.
            
        Returns:
            Dict containing video_path, manim_code.
            
        Raises:
            AnimationError or its subclasses: if any stage fails.
        """
        self.stats["total_sections"] += 1
        logger.info(f"Starting animation pipeline for section {section_index} (Job: {job_id})")

        # Build context for logging
        context = {
            "section_index": section_index,
            "job_id": job_id or "unknown"
        }

        # Modular Pipeline Flow (Choreograph -> Implement -> Refine)
        section_dir = Path(output_dir)
        write_status(section_dir, "generating_manim")

        def on_raw_code(code: str, attempt_idx: int) -> None:
            self.file_manager.prepare_scene_file(
                output_dir=output_dir,
                section_index=section_index,
                code_content=code
            )

        def status_callback(status: SectionState) -> None:
            write_status(section_dir, status)

        final_manim_code = await self.orchestrator.generate(
            section,
            audio_duration,
            context,
            on_raw_code=on_raw_code,
            status_callback=status_callback
        )
        
        # Check if generation succeeded
        if not final_manim_code or not final_manim_code.strip():
            logger.error(
                f"Orchestrator failed to generate valid code for section {section_index} "
                f"after all retry attempts"
            )
            raise ImplementationError(
                f"Failed to generate valid animation code for section {section_index} "
                f"after {MAX_CLEAN_RETRIES} attempts"
            )

        # Stage 4: Rendering (Production)
        return await self.process_code_and_render(
            manim_code=final_manim_code,
            section=section,
            output_dir=output_dir,
            section_index=section_index,
            audio_duration=audio_duration,
            style=style
        )

    async def process_code_and_render(
        self,
        manim_code: str,
        section: Dict[str, Any],
        output_dir: str,
        section_index: int,
        audio_duration: Optional[float] = None,
        style: str = DEFAULT_THEME_CODE,
    ) -> Dict[str, Any]:
        """Validates, prepares, and renders Manim code.
        
        This stage is the final production step. It asserts that the code is
        valid before attempting to render, ensuring engineering stability.
        """
        target_duration = audio_duration or section.get("duration_seconds", 60)
        
        # Validate code presence
        if not manim_code:
            logger.error(f"No code generated for section {section_index}")
            raise RefinementError(f"No code generated for section {section_index}")

        # 2. File Preparation via Manager
        section_id = section.get("id", f"section_{section_index}").replace("-", "_").replace(" ", "_")
        scene_name = f"Section{section_id.title().replace('_', '')}"
        
        logger.info(f"Preparing scene: {scene_name}")
        
        full_code = create_scene_file(manim_code, section_id, target_duration, style)
        
        # Delegate I/O to FileManager
        code_file = self.file_manager.prepare_scene_file(
            output_dir=output_dir,
            section_index=section_index,
            code_content=full_code
        )

        # 3. Execution (Rendering)
        write_status(Path(output_dir), "generating_video")
        output_video = await render_scene(
            self, 
            code_file, 
            scene_name, 
            output_dir,
            section_index, 
            file_manager=self.file_manager,  # Inject manager
            section=section, 
            clean_retry=0
        )

        if not output_video:
            logger.error(f"Rendering stage failed to produce output for section {section_index}")
            raise RenderingError(f"Manim failed to render video for section {section_index}")

        if ENABLE_VISION_QC:
            vision_messages = await self._run_vision_verification(
                output_video=output_video,
                output_dir=output_dir,
                section_index=section_index,
            )
        else:
            vision_messages = []

        return {
            "video_path": output_video,
            "manim_code": full_code,
            "manim_code_path": str(code_file),
            "vision_issues": vision_messages,
        }

    async def _run_vision_verification(
        self,
        output_video: str,
        output_dir: str,
        section_index: int,
    ) -> list[str]:
        """Run vision QC as verification-only for uncertain spatial issues.

        Architecture:
            The spatial validator catches most issues deterministically.
            Vision QC only verifies issues where the spatial validator
            was uncertain (needs_verification=True). Confirmed issues
            are logged but NOT auto-fixed (would require re-render).
        """
        # Get uncertain spatial issues from the last runtime validation
        uncertain_issues = [
            issue
            for issue in self.orchestrator.refiner.last_runtime_issues
            if issue.is_spatial and issue.needs_verification
        ]

        if not uncertain_issues:
            return []

        logger.info(
            f"Vision QC: verifying {len(uncertain_issues)} uncertain "
            f"spatial issues for section {section_index}"
        )

        confirmed = await self.vision_validator.verify_issues(
            video_path=output_video,
            uncertain_issues=uncertain_issues,
            output_dir=output_dir,
            context={"section_index": section_index},
        )

        if confirmed:
            logger.warning(
                f"Vision QC confirmed {len(confirmed)} issues in section "
                f"{section_index} (not auto-fixed — would require re-render)"
            )

        return [issue.message for issue in confirmed]

    async def render_from_code(
        self,
        manim_code: str,
        output_dir: str,
        section_index: int = 0,
        audio_duration: float = 60.0
    ) -> Optional[str]:
        """Utility for rendering straight from code (legacy support)."""
        result = await self.process_code_and_render(
            manim_code=manim_code,
            section={"id": f"manual_{section_index}"},
            output_dir=output_dir,
            section_index=section_index,
            audio_duration=audio_duration
        )
        return result.get("video_path")
