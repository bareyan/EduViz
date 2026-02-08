"""
Progress Tracking Module
Manages job state, resume capability, and progress reporting
Separated from generation logic for better testability and single responsibility
"""

import json
from typing import Dict, Any, List, Set, Optional, Callable
from pathlib import Path
from dataclasses import dataclass

from app.core import get_logger

logger = get_logger(__name__, component="progress_tracker")

_WRAPPER_METADATA_KEYS = (
    "mode",
    "output_language",
    "detected_language",
    "language",
    "source_language",
)


def _unwrap_script_with_metadata(raw_script: Dict[str, Any]) -> Dict[str, Any]:
    """Unwrap wrapped scripts while preserving language-related metadata."""
    if "script" in raw_script and isinstance(raw_script.get("script"), dict):
        inner = raw_script["script"]
        if "sections" in inner or "title" in inner:
            merged = dict(inner)
            for key in _WRAPPER_METADATA_KEYS:
                if key in raw_script and key not in merged:
                    merged[key] = raw_script[key]
            return merged
    return raw_script


@dataclass
class JobProgress:
    """
    Represents the complete progress state of a video generation job
    
    Attributes:
        job_id: Unique identifier for the job
        has_script: Whether script.json exists
        script: Loaded script data (if available)
        completed_sections: Set of section indices that are completed
        has_final_video: Whether final_video.mp4 exists
        total_sections: Total number of sections in the script
        sections_dir: Path to sections directory
        job_dir: Path to job directory
    """
    job_id: str
    has_script: bool
    script: Optional[Dict[str, Any]]
    completed_sections: Set[int]
    has_final_video: bool
    total_sections: int
    sections_dir: Path
    job_dir: Path

    def is_resumable(self) -> bool:
        """Check if this job can be resumed"""
        return self.has_script and len(self.completed_sections) > 0 and not self.has_final_video

    def get_remaining_sections(self) -> List[int]:
        """Get list of section indices that still need processing"""
        return [i for i in range(self.total_sections) if i not in self.completed_sections]

    def completion_percentage(self) -> float:
        """Calculate completion percentage"""
        if self.total_sections == 0:
            return 0.0
        return (len(self.completed_sections) / self.total_sections) * 100


class ProgressTracker:
    """
    Manages job progress tracking, state persistence, and resume capability
    
    Responsibilities:
    - Check existing progress for jobs
    - Track section completion
    - Manage resume state
    - Report progress to callbacks
    - Persist state to disk
    
    This class maintains state for a single job and should be created per job.
    """

    def __init__(
        self,
        job_id: str,
        output_base_dir: Path,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        """
        Initialize progress tracker for a job
        
        Args:
            job_id: Unique job identifier
            output_base_dir: Base directory for all job outputs
            progress_callback: Optional callback function for progress updates
        """
        self.job_id = job_id
        self.output_base_dir = output_base_dir
        self.job_dir = output_base_dir / job_id
        self.sections_dir = self.job_dir / "sections"
        self.progress_callback = progress_callback

        self.completed_sections: Set[int] = set()
        self.total_sections: int = 0

        logger.info(f"Initialized ProgressTracker for job {job_id[:8]}", extra={
            "job_id": job_id,
            "job_dir": str(self.job_dir)
        })

    def check_existing_progress(self) -> JobProgress:
        """
        Check what progress already exists for this job
        
        Returns:
            JobProgress object with current state
        
        Example:
            progress = tracker.check_existing_progress()
            if progress.is_resumable():
                print(f"Can resume from {len(progress.completed_sections)} sections")
        """
        logger.debug(f"Checking existing progress for job {self.job_id[:8]}")

        result = JobProgress(
            job_id=self.job_id,
            has_script=False,
            script=None,
            completed_sections=set(),
            has_final_video=False,
            total_sections=0,
            sections_dir=self.sections_dir,
            job_dir=self.job_dir
        )

        if not self.job_dir.exists():
            logger.info(f"No existing progress found for job {self.job_id[:8]}")
            return result

        # Check for script
        script_path = self.job_dir / "script.json"
        if script_path.exists():
            result.has_script = True
            try:
                with open(script_path, encoding="utf-8") as f:
                    raw_script = json.load(f)
                result.script = _unwrap_script_with_metadata(raw_script)
                result.total_sections = len(result.script.get("sections", []))
                logger.debug(f"Found existing script with {result.total_sections} sections", extra={
                    "total_sections": result.total_sections
                })
            except Exception:
                logger.error("Failed to load script.json", exc_info=True)

        # Check for final video
        final_video_path = self.job_dir / "final_video.mp4"
        if final_video_path.exists():
            result.has_final_video = True
            logger.info(f"Found existing final video for job {self.job_id[:8]}")

        # Check for completed sections
        if self.sections_dir.exists():
            for section_index in range(result.total_sections):
                section_dir = self.sections_dir / str(section_index)
                if not section_dir.exists():
                    continue

                # Check for merged video
                merged_path = self.sections_dir / f"merged_{section_index}.mp4"
                final_section_path = section_dir / "final_section.mp4"

                if merged_path.exists() or final_section_path.exists():
                    result.completed_sections.add(section_index)

            self.completed_sections = result.completed_sections
            logger.info(f"Found {len(result.completed_sections)} completed sections", extra={
                "completed_count": len(result.completed_sections),
                "total_sections": result.total_sections,
                "completed_indices": sorted(result.completed_sections)
            })

        return result

    def mark_section_complete(self, section_index: int) -> None:
        """
        Mark a section as completed
        
        Args:
            section_index: Index of the completed section
        """
        self.completed_sections.add(section_index)
        logger.debug(f"Marked section {section_index} as complete", extra={
            "section_index": section_index,
            "completed_count": len(self.completed_sections),
            "total_sections": self.total_sections
        })

    def is_section_complete(self, section_index: int) -> bool:
        """Check if a section is already completed"""
        return section_index in self.completed_sections

    def report_stage_progress(
        self,
        stage: str,
        progress: int,
        message: str
    ) -> None:
        """
        Report progress for a stage
        
        Args:
            stage: Stage name (e.g., "analysis", "script", "sections", "combining")
            progress: Progress percentage (0-100)
            message: Human-readable progress message
        """
        if self.progress_callback:
            self.progress_callback({
                "stage": stage,
                "progress": progress,
                "message": message
            })

        logger.info(f"[{stage}] {message}", extra={
            "stage": stage,
            "progress": progress,
            "job_id": self.job_id
        })

    def report_section_progress(
        self,
        completed_count: int,
        total_count: int,
        is_cached: bool = False
    ) -> None:
        """
        Report progress for section processing
        
        Args:
            completed_count: Number of sections completed
            total_count: Total number of sections
            is_cached: Whether this section was resumed from cache
        """
        self.total_sections = total_count
        progress_pct = int((completed_count / total_count) * 100) if total_count > 0 else 0

        status = "cached" if is_cached else "completed"
        message = f"Section {completed_count}/{total_count} {status}"

        self.report_stage_progress("sections", progress_pct, message)

    def save_script(self, script: Dict[str, Any]) -> None:
        """
        Save script data to disk
        
        Args:
            script: Script dictionary to save (may be wrapped or unwrapped)
        """
        script_path = self.job_dir / "script.json"

        try:
            with open(script_path, "w", encoding="utf-8") as f:
                json.dump(script, f, indent=2, ensure_ascii=False)

            # Count sections from either wrapped or unwrapped format
            # Handle case where script might be a list or dict
            if isinstance(script, list):
                section_count = len(script)
            elif isinstance(script, dict):
                script_data = script.get('script', script)
                if isinstance(script_data, list):
                    section_count = len(script_data)
                elif isinstance(script_data, dict):
                    section_count = len(script_data.get('sections', []))
                else:
                    section_count = 0
            else:
                section_count = 0
            
            logger.debug(f"Saved script.json with {section_count} sections", extra={
                "section_count": section_count,
                "script_path": str(script_path)
            })

        except Exception:
            logger.error("Failed to save script.json", exc_info=True)
            raise

    def load_script(self) -> Dict[str, Any]:
        """
        Load script data from disk
        
        Returns:
            Unwrapped script dictionary with title, sections at top level
        
        Raises:
            FileNotFoundError: If script.json doesn't exist
            json.JSONDecodeError: If script.json is invalid
        """
        script_path = self.job_dir / "script.json"

        if not script_path.exists():
            logger.error(f"script.json not found at {script_path}")
            raise FileNotFoundError(f"Script not found: {script_path}")

        try:
            with open(script_path, encoding="utf-8") as f:
                raw_script = json.load(f)

            script = _unwrap_script_with_metadata(raw_script)
                
            section_count = len(script.get('sections', []))
            logger.debug(f"Loaded script.json with {section_count} sections")
            return script

        except Exception:
            logger.error("Failed to load script.json", exc_info=True)
            raise

    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary of current progress
        
        Returns:
            Dictionary with progress summary
        """
        return {
            "job_id": self.job_id,
            "completed_sections": len(self.completed_sections),
            "total_sections": self.total_sections,
            "completion_percentage": (
                (len(self.completed_sections) / self.total_sections * 100)
                if self.total_sections > 0 else 0
            ),
            "is_complete": len(self.completed_sections) == self.total_sections,
            "job_dir": str(self.job_dir)
        }
