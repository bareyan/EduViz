"""
Video Generator - Orchestrates the complete video generation pipeline
Refactored to pure orchestration - delegates to specialized components
"""

import shutil
from typing import Dict, Any, Optional, Callable
from pathlib import Path

from ..content_analysis import MaterialAnalyzer
from ..script_generation import ScriptGenerator
from ..animation import ManimGenerator
from ..animation.config import normalize_theme_style
from ..audio import TTSEngine, create_tts_engine

from .processor import VideoProcessor
from .progress import ProgressTracker
from .orchestrator import SectionOrchestrator
from app.core import get_logger, set_job_id, LogTimer
from app.services.pipeline.animation.generation.constants import DEFAULT_THEME_CODE

logger = get_logger(__name__, component="video_generator")


class VideoGenerator:
    """
    Pure orchestrator for video generation pipeline
    
    Delegates to:
    - MaterialAnalyzer: Content analysis
    - ScriptGenerator: Script creation
    - ManimGenerator: Visual generation
    - TTSEngine: Audio synthesis
    - VideoProcessor: FFmpeg operations
    - ProgressTracker: State management
    - SectionOrchestrator: Parallel processing
    
    This class coordinates the high-level workflow without implementing
    low-level details, making it easy to test and maintain.
    """

    def __init__(self, output_base_dir: str, pipeline_name: Optional[str] = None):
        """
        Initialize video generator and all subsystems
        
        Args:
            output_base_dir: Base directory for all job outputs
        """
        self.output_base_dir = Path(output_base_dir)
        self.output_base_dir.mkdir(parents=True, exist_ok=True)

        self.pipeline_name = pipeline_name

        # Initialize service dependencies
        self.analyzer = MaterialAnalyzer(pipeline_name=pipeline_name)
        self.script_generator = ScriptGenerator(pipeline_name=pipeline_name)
        self.manim_generator = ManimGenerator(pipeline_name=pipeline_name)
        self.tts_engine = create_tts_engine()

        # Initialize processing components
        self.video_processor = VideoProcessor()

        logger.info("Initialized VideoGenerator", extra={
            "output_base_dir": str(self.output_base_dir)
        })

    def check_existing_progress(self, job_id: str) -> Dict[str, Any]:
        """
        Check what progress already exists for a job
        
        Args:
            job_id: Unique job identifier
        
        Returns:
            Dictionary with progress information
        """
        tracker = ProgressTracker(job_id, self.output_base_dir)
        progress = tracker.check_existing_progress()

        return {
            "has_script": progress.has_script,
            "script": progress.script,
            "completed_sections": list(progress.completed_sections),
            "has_final_video": progress.has_final_video,
            "total_sections": progress.total_sections
        }

    @staticmethod
    def _normalize_language_code(language: Optional[str]) -> Optional[str]:
        """Normalize language values to lowercase ISO-like codes."""
        if not language:
            return None
        normalized = str(language).strip().lower()
        return normalized or None

    @classmethod
    def _resolve_output_language(
        cls,
        requested_language: str,
        script_payload: Dict[str, Any],
        script_data: Dict[str, Any],
    ) -> str:
        """Resolve a concrete output language, handling 'auto' requests."""
        requested = cls._normalize_language_code(requested_language)
        if requested and requested != "auto":
            return requested

        sections = script_data.get("sections", [])
        first_section_language = None
        if sections and isinstance(sections[0], dict):
            first_section_language = sections[0].get("language")

        candidates = (
            script_payload.get("output_language"),
            script_payload.get("language"),
            script_payload.get("detected_language"),
            script_data.get("output_language"),
            script_data.get("language"),
            script_data.get("detected_language"),
            first_section_language,
        )

        for candidate in candidates:
            normalized = cls._normalize_language_code(candidate)
            if normalized and normalized != "auto":
                return normalized

        return "en"

    async def generate_video(
        self,
        job_id: str,
        material_path: Optional[str] = None,
        topic: Optional[Dict[str, Any]] = None,
        voice: str = "en-US-Neural2-J",
        style: str = DEFAULT_THEME_CODE,
        language: str = "en",
        video_mode: str = "comprehensive",
        content_focus: str = "as_document",
        document_context: str = "auto",
        resume: bool = False,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        max_concurrent_sections: int = 1
    ) -> Dict[str, Any]:
        """
        Generate complete video from material
        
        This is the main orchestration method that coordinates all subsystems
        to produce a final video. It:
        1. Checks/resumes existing progress
        2. Analyzes material (if needed)
        3. Generates script (if needed)
        4. Processes sections in parallel
        5. Combines sections into final video
        6. Reports cost and cleanup
        
        Args:
            job_id: Unique job identifier
            material_path: Path to source material (PDF, image, etc.)
            topic: Topic payload derived from selected analysis topics
            voice: Voice identifier for TTS
            style: Style identifier for TTS
            language: Language code (e.g., "en", "es")
            video_mode: "comprehensive" for detailed videos, "overview" for short summaries
            content_focus: "practice", "theory", or "as_document"
            document_context: "standalone", "series", or "auto"
            resume: Whether to resume from existing progress
            progress_callback: Optional callback for progress updates
            max_concurrent_sections: Maximum sections to process in parallel
        
        Returns:
            Dictionary with:
            - job_id: Job identifier
            - video_path: Path to final video
            - script: Complete script data
            - chapters: List of chapter metadata
            - total_duration: Total video duration
            - cost_summary: Generation cost breakdown
            - status: "completed" or "failed"
            - error: Error message (if failed)
        """
        with LogTimer(logger, f"generate_video (job: {job_id[:8]})"):
            set_job_id(job_id)

            try:
                # Initialize components for this job
                job_dir = self.output_base_dir / job_id
                job_dir.mkdir(parents=True, exist_ok=True)
                sections_dir = job_dir / "sections"
                sections_dir.mkdir(parents=True, exist_ok=True)

                tracker = ProgressTracker(job_id, self.output_base_dir, progress_callback)
                style = normalize_theme_style(style)

                logger.info("Starting video generation", extra={
                    "job_id": job_id,
                    "resume": resume,
                    "voice": voice,
                    "style": style,
                    "language": language,
                    "video_mode": video_mode,
                    "content_focus": content_focus,
                    "document_context": document_context,
                    "max_concurrent": max_concurrent_sections
                })

                # Step 1: Check existing progress
                progress = tracker.check_existing_progress()

                if progress.has_final_video:
                    logger.info("Final video already exists, returning cached result")
                    final_video_path = job_dir / "final_video.mp4"
                    return {
                        "job_id": job_id,
                        "video_path": str(final_video_path),
                        "script": progress.script,
                        "status": "completed",
                        "cached": True
                    }

                # Step 2: Generate or load script
                if progress.has_script and resume:
                    logger.info("Loading existing script for resume")
                    tracker.report_stage_progress("script", 100, "Loaded existing script")
                    script = tracker.load_script()
                else:
                    logger.info(f"Generating new script (video_mode: {video_mode})")
                    script = await self._generate_script(
                        job_id=job_id,
                        material_path=material_path,
                        topic=topic,
                        language=language,
                        video_mode=video_mode,
                        content_focus=content_focus,
                        document_context=document_context,
                        tracker=tracker,
                        artifacts_dir=str(sections_dir),
                    )
                    tracker.save_script(script)

                # Extract sections from script (script generator wraps it in {"script": {...}})
                script_data = script.get("script", script)  # Support both wrapped and unwrapped formats
                sections = script_data.get("sections", [])
                if not sections:
                    raise ValueError("Script has no sections")

                effective_language = self._resolve_output_language(language, script, script_data)
                script_data["language"] = effective_language
                script_data["output_language"] = effective_language
                script["output_language"] = effective_language

                for section in sections:
                    section.setdefault("content_focus", content_focus)
                    section.setdefault("video_mode", video_mode)
                    section.setdefault("document_context", document_context)
                    section["language"] = effective_language

                logger.info(f"Processing {len(sections)} sections", extra={
                    "section_count": len(sections),
                    "effective_language": effective_language,
                })

                # Step 3: Process sections in parallel
                orchestrator = SectionOrchestrator(
                    manim_generator=self.manim_generator,
                    tts_engine=self.tts_engine,
                    progress_tracker=tracker,
                    max_concurrent=max_concurrent_sections
                )

                section_results = await orchestrator.process_sections_parallel(
                    sections=sections,
                    sections_dir=sections_dir,
                    voice=voice,
                    style=style,
                    language=effective_language,
                    resume=resume,
                    job_id=job_id
                )

                # Step 4: Aggregate results
                section_videos, section_audios, chapters = orchestrator.aggregate_results(
                    section_results=section_results,
                    sections=sections
                )

                # Save updated script with section paths
                tracker.save_script(script)
                logger.info("Saved updated script with section metadata", extra={
                    "section_count": len(sections)
                })

                # Step 5: Combine sections into final video
                tracker.report_stage_progress("combining", 0, "Combining sections...")

                final_video_path = job_dir / "final_video.mp4"

                if section_videos and section_audios:
                    await self.video_processor.combine_sections(
                        videos=section_videos,
                        audios=section_audios,
                        output_path=str(final_video_path),
                        sections_dir=str(sections_dir)
                    )
                elif section_videos:
                    await self.video_processor.concatenate_videos(
                        video_paths=section_videos,
                        output_path=str(final_video_path)
                    )
                else:
                    raise ValueError("No video sections were generated")

                tracker.report_stage_progress("combining", 100, "Video complete!")

                # Step 6: Report cost summary
                self.manim_generator.print_cost_summary()

                cost_summary = self.manim_generator.get_cost_summary()

                # Calculate total duration
                total_duration = sum(chapter["duration"] for chapter in chapters)

                # Step 7: Cleanup
                await self._cleanup_intermediate_files(sections_dir)

                logger.info("Video generation completed successfully", extra={
                    "job_id": job_id,
                    "video_path": str(final_video_path),
                    "section_count": len(sections),
                    "total_duration": total_duration,
                    "total_cost": cost_summary.get("total_cost_usd", 0)
                })

                # Unwrap script for the return value (extract inner script from wrapper)
                return_script = script_data  # script_data is already the unwrapped version

                return {
                    "job_id": job_id,
                    "video_path": str(final_video_path),
                    "script": return_script,
                    "chapters": chapters,
                    "total_duration": total_duration,
                    "cost_summary": cost_summary,
                    "status": "completed"
                }

            except Exception as e:
                logger.error("Video generation failed", extra={
                    "job_id": job_id,
                    "error": str(e)
                }, exc_info=True)

                return {
                    "job_id": job_id,
                    "error": str(e),
                    "status": "failed"
                }

    async def _generate_script(
        self,
        job_id: str,
        material_path: Optional[str],
        topic: Optional[Dict[str, Any]],
        language: str,
        video_mode: str,
        content_focus: str,
        document_context: str,
        tracker: ProgressTracker,
        artifacts_dir: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate script from material (internal helper)
        
        Coordinates script generator with progress reporting.
        
        Args:
            job_id: Unique job identifier
            material_path: Path to source material
            topic: Selected-topic context payload from analysis
            language: Language code
            video_mode: "comprehensive" or "overview"
            content_focus: "practice", "theory", or "as_document"
            document_context: "standalone", "series", or "auto"
            tracker: Progress tracker instance
        """
        if not material_path:
            raise ValueError("material_path required for new jobs")

        tracker.report_stage_progress("script", 0, "Generating script...")

        logger.info("Generating script from material", extra={
            "material_path": material_path,
            "video_mode": video_mode,
            "content_focus": content_focus,
            "document_context": document_context,
        })
        
        # Generate script directly from material
        # The script generator handles content extraction and processing internally
        script = await self.script_generator.generate_script(
            file_path=material_path,
            topic=topic or {"title": "Educational Content", "description": ""},
            language=language,
            video_mode=video_mode,
            content_focus=content_focus,
            document_context=document_context,
            artifacts_dir=artifacts_dir,
        )

        tracker.report_stage_progress("script", 100, "Script generated")

        return script

    async def _cleanup_intermediate_files(self, sections_dir: Path) -> None:
        """
        Remove all generation intermediates after a successful run.

        Keeps:
        - final_video.mp4
        - translations/ (if it exists)

        Removes:
        - sections/
        - script.json
        - all other temporary artifacts in the job directory
        """
        try:
            job_dir = sections_dir.parent
            keep_entries = {"final_video.mp4", "translations"}

            logger.info("Cleaning up intermediate files", extra={
                "sections_dir": str(sections_dir),
                "job_dir": str(job_dir)
            })

            cleanup_count = 0
            if sections_dir.exists():
                shutil.rmtree(sections_dir)
                cleanup_count += 1

            for entry in job_dir.iterdir():
                if entry.name in keep_entries:
                    continue

                if entry.is_dir():
                    shutil.rmtree(entry)
                    cleanup_count += 1
                else:
                    entry.unlink(missing_ok=True)
                    cleanup_count += 1

            logger.info("Cleanup complete", extra={
                "files_removed": cleanup_count
            })

        except Exception as e:
            logger.warning("Cleanup error (non-fatal)", extra={
                "error": str(e)
            })
