"""
Section Orchestration Module
Coordinates section-level processing including parallel execution and resource management
Separated from VideoGenerator for better testability and single responsibility
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional
from pathlib import Path
from dataclasses import dataclass

from ..animation.generation import ManimGenerator
from ..audio import TTSEngine
from .sections import (
    clean_narration_for_tts,
    process_single_subsection,
    process_segments_audio_first,
)
from .progress import ProgressTracker
from app.core import get_logger, LogTimer
from app.core.llm_logger import set_llm_section_log, clear_llm_section_log
from app.core.logging import (
    job_id_var,
    section_index_var,
    set_section_context,
    clear_section_context,
    DevelopmentFormatter,
)

logger = get_logger(__name__, component="section_orchestrator")


@dataclass
class SectionResult:
    """Result of processing a single section"""
    index: int
    video_path: Optional[str]
    audio_path: Optional[str]
    duration: float
    title: str
    manim_code_path: Optional[str] = None
    manim_code: Optional[str] = None
    error: Optional[str] = None

    def is_successful(self) -> bool:
        """Check if section processing was successful"""
        return self.video_path is not None and self.error is None


class SectionOrchestrator:
    """
    Orchestrates parallel processing of video sections
    
    Responsibilities:
    - Manage concurrent section processing with semaphore
    - Coordinate TTS and Manim generation
    - Handle section resume logic
    - Aggregate section results
    - Report progress
    
    This class handles the complex async orchestration of section processing
    while keeping individual processing logic in section_processor.
    """

    def __init__(
        self,
        manim_generator: ManimGenerator,
        tts_engine: TTSEngine,
        progress_tracker: ProgressTracker,
        max_concurrent: int = 8
    ):
        """
        Initialize section orchestrator
        
        Args:
            manim_generator: Manim generator instance
            tts_engine: TTS engine instance
            progress_tracker: Progress tracker for reporting
            max_concurrent: Maximum number of sections to process concurrently
        """
        self.manim_generator = manim_generator
        self.tts_engine = tts_engine
        self.progress_tracker = progress_tracker
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)

        logger.info("Initialized SectionOrchestrator", extra={
            "max_concurrent": max_concurrent
        })

    async def process_sections_parallel(
        self,
        sections: List[Dict[str, Any]],
        sections_dir: Path,
        voice: str,
        style: str,
        language: str,
        resume: bool = False
    ) -> List[SectionResult]:
        """
        Process all sections in parallel with controlled concurrency
        
        Args:
            sections: List of section dictionaries from script
            sections_dir: Directory for section outputs
            voice: Voice identifier for TTS
            style: Style identifier for TTS
            language: Language code
            resume: Whether to skip already-completed sections
        
        Returns:
            List of SectionResult objects
        
        Example:
            results = await orchestrator.process_sections_parallel(
                sections=script["sections"],
                sections_dir=Path("/tmp/job123/sections"),
                voice="en-US-Neural2-J",
                style="default",
                language="en",
                resume=True
            )
        """
        with LogTimer(logger, f"process_sections_parallel ({len(sections)} sections)"):
            total_sections = len(sections)
            completed_count = [0]  # Mutable counter for closure

            logger.info("Starting parallel section processing", extra={
                "total_sections": total_sections,
                "max_concurrent": self.max_concurrent,
                "resume": resume
            })

            self.progress_tracker.report_stage_progress(
                stage="sections",
                progress=0,
                message=f"Processing {total_sections} sections (max {self.max_concurrent} concurrent)..."
            )

            async def process_section(i: int, section: Dict[str, Any]) -> SectionResult:
                """Process a single section with semaphore control"""
                async with self.semaphore:
                    return await self._process_single_section(
                        section_index=i,
                        section=section,
                        sections_dir=sections_dir,
                        voice=voice,
                        style=style,
                        language=language,
                        resume=resume,
                        completed_count=completed_count,
                        total_sections=total_sections,
                    )

            # Create tasks for all sections
            section_tasks = [
                process_section(i, section)
                for i, section in enumerate(sections)
            ]

            # Execute with gather to collect all results
            section_results = await asyncio.gather(*section_tasks, return_exceptions=True)

            # Convert exceptions to error results
            final_results = []
            for i, result in enumerate(section_results):
                if isinstance(result, Exception):
                    logger.error(f"Section {i} processing error: {result}", extra={
                        "section_index": i,
                        "error": str(result)
                    })
                    final_results.append(SectionResult(
                        index=i,
                        video_path=None,
                        audio_path=None,
                        duration=sections[i].get("duration_seconds", 30),
                        title=sections[i].get("title", f"Section {i + 1}"),
                        error=str(result)
                    ))
                else:
                    final_results.append(result)

            self.progress_tracker.report_stage_progress(
                stage="sections",
                progress=100,
                message="All sections processed"
            )

            # Log summary
            successful = sum(1 for r in final_results if r.is_successful())
            logger.info("Section processing complete", extra={
                "total_sections": len(final_results),
                "successful": successful,
                "failed": len(final_results) - successful
            })

            return final_results

    async def _process_single_section(
        self,
        section_index: int,
        section: Dict[str, Any],
        sections_dir: Path,
        voice: str,
        style: str,
        language: str,
        resume: bool,
        completed_count: List[int],
        total_sections: int,
    ) -> SectionResult:
        """
        Process a single section (internal method)
        
        Handles:
        - Resume logic (skip if already completed)
        - Narration segment processing (multi-segment vs single)
        - Progress reporting
        - Error handling
        """
        section_dir = sections_dir / str(section_index)
        section_dir.mkdir(parents=True, exist_ok=True)

        section_id = section.get("id", f"section_{section_index}")
        section_title = section.get("title", f"Section {section_index + 1}")
        section_log_path = section_dir / "llm_calls.jsonl"
        section_text_log_path = section_dir / "section.log"
        section_context = {
            "section_index": section_index,
            "section_id": section_id,
            "title": section_title,
            "job_id": job_id_var.get(),
        }

        set_llm_section_log(section_log_path, section_context)
        set_section_context(section_index, section_id)

        section_handler = None
        root_logger = logging.getLogger()
        try:
            section_handler = logging.FileHandler(section_text_log_path)
            section_handler.setLevel(root_logger.level)
            section_handler.setFormatter(DevelopmentFormatter())

            class _SectionFilter(logging.Filter):
                def __init__(self, expected_index: int):
                    super().__init__()
                    self.expected_index = expected_index

                def filter(self, record: logging.LogRecord) -> bool:
                    return section_index_var.get() == self.expected_index

            section_handler.addFilter(_SectionFilter(section_index))
            root_logger.addHandler(section_handler)
        except Exception as e:
            logger.warning(
                "Failed to initialize section log file",
                extra={"section_index": section_index, "error": str(e)},
            )

        try:
            # Build initial result
            result = SectionResult(
                index=section_index,
                video_path=None,
                audio_path=None,
                duration=section.get("duration_seconds", 30),
                title=section_title
            )

            # Check for existing completed section
            merged_path = sections_dir / f"merged_{section_index}.mp4"
            final_section_path = section_dir / "final_section.mp4"

            existing_video_path = None
            if merged_path.exists():
                existing_video_path = str(merged_path)
            elif final_section_path.exists():
                existing_video_path = str(final_section_path)

            # Resume logic: skip if already completed
            if resume and self.progress_tracker.is_section_complete(section_index) and existing_video_path:
                logger.info(f"[Resume] Skipping section {section_index + 1}/{total_sections} (cached)", extra={
                    "section_index": section_index,
                    "total_sections": total_sections
                })

                result.video_path = existing_video_path
                section_audio_path = section_dir / "section_audio.mp3"
                if section_audio_path.exists():
                    result.audio_path = str(section_audio_path)

                completed_count[0] += 1
                self.progress_tracker.report_section_progress(
                    completed_count=completed_count[0],
                    total_count=total_sections,
                    is_cached=True
                )
                return result

            # Process section
            logger.info(f"[Parallel] Starting section {section_index + 1}/{total_sections}: {result.title}", extra={
                "section_index": section_index,
                "total_sections": total_sections,
                "title": result.title
            })

            narration_segments = section.get("narration_segments", [])

            if not narration_segments:
                # Single narration processing
                tts_text = section.get("tts_narration") or section.get("narration", "")
                clean_narration = clean_narration_for_tts(tts_text)

                logger.debug(f"Processing section {section_index} as single narration", extra={
                    "section_index": section_index,
                    "narration_length": len(clean_narration)
                })

                subsection_results = await process_single_subsection(
                    manim_generator=self.manim_generator,
                    tts_engine=self.tts_engine,
                    section=section,
                    narration=clean_narration,
                    section_dir=section_dir,
                    section_index=section_index,
                    voice=voice,
                    style=style,
                    language=language
                )

                result.video_path = subsection_results.get("video_path")
                result.audio_path = subsection_results.get("audio_path")
                result.duration = subsection_results.get("duration", 30)
                if subsection_results.get("error"):
                    result.error = subsection_results.get("error")
                if subsection_results.get("manim_code_path"):
                    result.manim_code_path = subsection_results["manim_code_path"]
                    section["manim_code_path"] = subsection_results["manim_code_path"]
                if subsection_results.get("manim_code"):
                    result.manim_code = subsection_results["manim_code"]

            else:
                # Multi-segment processing
                logger.debug(f"Processing section {section_index} with {len(narration_segments)} segments", extra={
                    "section_index": section_index,
                    "segment_count": len(narration_segments)
                })

                segment_result = await process_segments_audio_first(
                    manim_generator=self.manim_generator,
                    tts_engine=self.tts_engine,
                    section=section,
                    narration_segments=narration_segments,
                    section_dir=section_dir,
                    section_index=section_index,
                    voice=voice,
                    style=style,
                    language=language
                )

                result.video_path = segment_result.get("video_path")
                result.audio_path = segment_result.get("audio_path")
                result.duration = segment_result.get("duration", 30)
                if segment_result.get("error"):
                    result.error = segment_result.get("error")
                if segment_result.get("manim_code_path"):
                    result.manim_code_path = segment_result["manim_code_path"]
                    section["manim_code_path"] = segment_result["manim_code_path"]
                if segment_result.get("manim_code"):
                    result.manim_code = segment_result["manim_code"]

            # Mark as complete/failed and report progress
            if result.video_path and not result.error:
                self.progress_tracker.mark_section_complete(section_index)
                completed_count[0] += 1
            else:
                self.progress_tracker.mark_section_failed(section_index)

            self.progress_tracker.report_section_progress(
                completed_count=completed_count[0],
                total_count=total_sections,
                is_cached=False
            )

            logger.info(f"[Parallel] Finished section {section_index + 1}/{total_sections}", extra={
                "section_index": section_index,
                "total_sections": total_sections,
                "has_video": result.video_path is not None,
                "has_audio": result.audio_path is not None
            })

            return result

        except Exception as e:
            logger.error(f"Failed to process section {section_index}", extra={
                "section_index": section_index,
                "error": str(e)
            }, exc_info=True)
            result.error = str(e)
            self.progress_tracker.mark_section_failed(section_index)
            self.progress_tracker.report_section_progress(
                completed_count=completed_count[0],
                total_count=total_sections,
                is_cached=False
            )
            return result
        finally:
            if section_handler:
                try:
                    root_logger.removeHandler(section_handler)
                    section_handler.close()
                except Exception:
                    pass
            clear_section_context()
            clear_llm_section_log()

    def aggregate_results(
        self,
        section_results: List[SectionResult],
        sections: List[Dict[str, Any]]
    ) -> tuple[List[str], List[Optional[str]], List[Dict[str, Any]]]:
        """
        Aggregate section results into video/audio lists and chapters
        
        Args:
            section_results: List of section processing results
            sections: Original section dictionaries (will be updated)
        
        Returns:
            Tuple of (video_paths, audio_paths, chapters)
        
        This method:
        - Filters out failed sections
        - Updates section dictionaries with paths
        - Builds chapter metadata
        - Calculates cumulative timestamps
        """
        section_videos = []
        section_audios = []
        chapters = []
        current_time = 0.0

        for result in section_results:
            i = result.index

            # Update section dictionary
            if i < len(sections):
                sections[i]["order"] = i

            # Handle successful sections
            if result.video_path and result.audio_path:
                section_videos.append(result.video_path)
                section_audios.append(result.audio_path)
                if i < len(sections):
                    sections[i]["video"] = result.video_path
                    sections[i]["audio"] = result.audio_path

                logger.debug(f"Section {i} has video and audio", extra={
                    "section_index": i
                })

            elif result.video_path:
                section_videos.append(result.video_path)
                section_audios.append(None)
                if i < len(sections):
                    sections[i]["video"] = result.video_path

                logger.warning(f"Section {i} has video but no audio", extra={
                    "section_index": i
                })

            elif result.audio_path:
                if i < len(sections):
                    sections[i]["audio"] = result.audio_path

                logger.warning(f"Section {i} has audio but no video - SKIPPING from final video", extra={
                    "section_index": i
                })
                continue

            else:
                logger.warning(f"Section {i} has neither video nor audio - SKIPPING", extra={
                    "section_index": i,
                    "error": result.error
                })
                continue

            # Update manim code paths
            if result.manim_code_path and i < len(sections):
                sections[i]["manim_code_path"] = result.manim_code_path
                if "manim_code" in sections[i]:
                    del sections[i]["manim_code"]

            # Build chapter metadata (only for sections with video)
            if result.video_path:
                chapters.append({
                    "title": result.title,
                    "start_time": current_time,
                    "duration": result.duration
                })
                current_time += result.duration

        logger.info("Aggregated section results", extra={
            "video_count": len(section_videos),
            "audio_count": len([a for a in section_audios if a]),
            "chapter_count": len(chapters),
            "total_duration": current_time
        })

        return section_videos, section_audios, chapters
