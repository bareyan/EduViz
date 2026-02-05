"""
Manim Generator - New Pipeline Implementation

Handles the multi-stage animation generation workflow:
1. Choreograph: Plan visuals from narration
2. Implement: Convert plans to Manim code
3. Refine: Automated fixing using validator feedback
4. Render: Produce final video sections
"""

from pathlib import Path
from typing import Dict, Any, Optional

from app.core import get_logger
from app.services.infrastructure.llm import PromptingEngine, CostTracker

from .processors import Animator
from .core import (
    RefinementError, 
    RenderingError, 
    create_scene_file, 
    render_scene,
    extract_scene_name,
)
from .validation import CodeValidator
from ..config import MAX_CLEAN_RETRIES, MAX_SURGICAL_FIX_ATTEMPTS

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
        self.validator = CodeValidator()
        
        # Initialize the Unified Animator (Single-Shot Agent)
        self.animator = Animator(
            PromptingEngine("animation_implementation", self.cost_tracker, pipeline_name=pipeline_name),
            self.validator,
            max_fix_attempts=MAX_SURGICAL_FIX_ATTEMPTS
        )

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
        style: str = "3b1b",
        status_callback: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Orchestrates the animation generation pipeline for a section.
        
        Args:
            section: Section metadata from narration stage.
            output_dir: Where to save generated code and video.
            section_index: Index of the current section.
            audio_duration: Duration of the narration audio.
            style: Visual style (e.g., '3b1b').
            
        Returns:
            Dict containing video_path, manim_code, and validation results.
            
        Raises:
            AnimationError or its subclasses: if any stage fails.
        """
        self.stats["total_sections"] += 1
        logger.info(f"Starting animation pipeline for section {section_index}")

        # Persist intermediate scene code to disk after initial generation and each fix
        section_id = section.get("id", f"section_{section_index}").replace("-", "_").replace(" ", "_")
        target_duration = audio_duration or section.get("duration_seconds", 60)
        code_file = Path(output_dir) / f"scene_{section_index}.py"

        def code_persistor(code: str, stage: str) -> None:
            try:
                full_code = create_scene_file(code, section_id, target_duration, style)
                code_file.parent.mkdir(parents=True, exist_ok=True)
                code_file.write_text(full_code, encoding="utf-8")
                logger.info(
                    f"Persisted intermediate scene code for section {section_index}",
                    extra={"stage": stage, "path": str(code_file)},
                )
            except Exception as exc:
                logger.warning(f"Failed to persist scene code at stage {stage}: {exc}")

        # Unified Agentic Flow (Plan -> Implement -> Refine in one session)
        if status_callback:
            try:
                status_callback("generating_manim", None)
            except Exception:
                pass

        final_manim_code, fallback_used = await self.animator.animate(
            section,
            audio_duration,
            style=style,
            code_persistor=code_persistor,
            status_callback=status_callback,
        )

        # Stage 4: Rendering (Production)
        return await self.process_code_and_render(
            manim_code=final_manim_code,
            section=section,
            output_dir=output_dir,
            section_index=section_index,
            audio_duration=audio_duration,
            style=style,
            status_callback=status_callback,
            allow_static_only=fallback_used,
        )

    async def process_code_and_render(
        self,
        manim_code: str,
        section: Dict[str, Any],
        output_dir: str,
        section_index: int,
        audio_duration: Optional[float] = None,
        style: str = "3b1b",
        status_callback: Optional[Any] = None,
        allow_static_only: bool = False,
    ) -> Dict[str, Any]:
        """Validates, prepares, and renders Manim code.
        
        This stage is the final production step. It asserts that the code is
        valid before attempting to render, ensuring engineering stability.
        """
        target_duration = audio_duration or section.get("duration_seconds", 60)
        
        # 1. Final Stability Check
        validation = self.validator.validate(manim_code)
        if allow_static_only:
            if not validation.static.valid:
                logger.error(f"Syntax validation failed for section {section_index}")
                raise RefinementError(
                    f"Syntax validation failed: {validation.get_error_summary()}"
                )
            logger.warning(
                f"Proceeding with static-only validation for section {section_index}",
                extra={"error_reason": "fallback_syntax_valid"},
            )
        else:
            if not validation.valid:
                logger.error(f"Post-refinement validation failed for section {section_index}")
                raise RefinementError(f"Stabilized code failed final validation: {validation.get_error_summary()}")

        # 2. File Preparation
        section_id = section.get("id", f"section_{section_index}").replace("-", "_").replace(" ", "_")
        code_file = Path(output_dir) / f"scene_{section_index}.py"
        
        full_code = create_scene_file(manim_code, section_id, target_duration, style)
        scene_name = extract_scene_name(full_code) or f"Section{section_id.title().replace('_', '')}"
        
        with open(code_file, "w", encoding="utf-8") as f:
            f.write(full_code)

        # 3. Execution (Rendering)
        if status_callback:
            try:
                status_callback("generating_video", None)
            except Exception:
                pass

        output_video = await render_scene(
            self, code_file, scene_name, output_dir,
            section_index, section=section, clean_retry=0
        )

        if not output_video:
            logger.error(f"Rendering stage failed to produce output for section {section_index}")
            raise RenderingError(f"Manim failed to render video for section {section_index}")

        return {
            "video_path": output_video,
            "manim_code": full_code,
            "manim_code_path": str(code_file),
            "validation_results": validation.to_dict()
        }

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
