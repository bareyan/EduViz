"""
Job route helper functions.

Extracted from routes/jobs.py to reduce function complexity and improve readability.
Each function handles a specific aspect of job processing.
"""

from typing import Optional, Dict, Any, List

from app.config import OUTPUT_DIR
from app.models import SectionProgress
from app.core import load_script
from app.utils.section_status import read_status as _read_section_status


def get_stage_from_status(status: str) -> str:
    """
    Map job status to display stage.
    
    Args:
        status: Current job status
        
    Returns:
        Human-readable stage name for UI display
    """
    status_to_stage = {
        "pending": "analyzing",
        "analyzing": "analyzing",
        "generating_script": "script",
        "creating_animations": "sections",
        "synthesizing_audio": "sections",
        "composing_video": "combining",
        "completed": "completed",
        "failed": "failed"
    }
    return status_to_stage.get(status, "unknown")


def build_section_progress(
    job_id: str,
    section: Dict[str, Any],
    index: int,
    current_stage: str,
    completed_sections: int
) -> SectionProgress:
    """
    Build a SectionProgress object from script section data.
    
    Checks status.json and filesystem to determine section status.
    
    Args:
        job_id: Job identifier for path construction
        section: Section data from script
        index: Section index in script
        current_stage: Current processing stage
        completed_sections: Count of already-completed sections
        
    Returns:
        SectionProgress object with complete section metadata
    """
    section_id = section.get("id", f"section_{index}")
    sections_dir = OUTPUT_DIR / job_id / "sections"
    section_dir = sections_dir / str(index)  # Use index for directory (matches orchestrator)

    # Check what files exist
    has_video = False
    has_audio = False
    has_code = False

    merged_path = sections_dir / f"merged_{index}.mp4"
    final_section_path = section_dir / "final_section.mp4"
    audio_path = section_dir / "section_audio.mp3"

    # Look for manim code files
    code_files = list(section_dir.glob("*.py")) if section_dir.exists() else []
    has_code = len(code_files) > 0

    # First, check live status from status.json (most up-to-date)
    live_status = _read_section_status(section_dir)
    
    # Map live status to display status
    if live_status in ("generating_audio", "generating_video", "fixing_error", "completed"):
        status = live_status
    # Fall back to file-based detection
    elif merged_path.exists() or final_section_path.exists():
        has_video = True
        status = "completed"
    elif has_code:
        status = "generating_video"
    elif audio_path.exists():
        has_audio = True
        status = "generating_video"
    else:
        if current_stage == "sections" and index == completed_sections:
            status = "generating_audio"
        else:
            status = "waiting"

    if audio_path.exists():
        has_audio = True

    # Get narration preview
    narration = section.get("tts_narration") or section.get("narration", "")
    narration_preview = narration[:200] + "..." if len(narration) > 200 else narration

    return SectionProgress(
        index=index,
        id=section_id,
        title=section.get("title", f"Section {index + 1}"),
        status=status,
        duration_seconds=section.get("duration_seconds"),
        narration_preview=narration_preview,
        has_video=has_video,
        has_audio=has_audio,
        has_code=has_code,
        error=None,
        fix_attempts=0,
        qc_iterations=0
    )


def build_sections_progress(
    job_id: str,
    current_stage: str
) -> tuple[List[SectionProgress], int]:
    """
    Build section progress list from job script and filesystem.
    
    Iterates through all sections in the script, checking filesystem for
    video/audio files and code, then builds complete progress objects.
    
    Args:
        job_id: Job identifier
        current_stage: Current processing stage for status determination
        
    Returns:
        Tuple of (sections_list, completed_count)
    """
    sections = []
    completed_sections = 0

    try:
        script = load_script(job_id)
    except Exception as e:
        # Script not found or unreadable - return empty
        print(f"Could not load script for job {job_id}: {e}")
        return sections, completed_sections

    for i, section in enumerate(script.get("sections", [])):
        # Build progress for each section
        progress = build_section_progress(
            job_id, section, i, current_stage, completed_sections
        )

        if progress.status == "completed":
            completed_sections += 1

        sections.append(progress)

    return sections, completed_sections


def get_current_section_index(
    sections: List[SectionProgress],
    completed_sections: int,
    total_sections: int,
    current_stage: str
) -> Optional[int]:
    """
    Determine which section is currently being processed.
    
    Args:
        sections: List of section progress objects
        completed_sections: Count of completed sections
        total_sections: Total number of sections
        current_stage: Current processing stage
        
    Returns:
        Index of current section or None if not processing sections
    """
    if current_stage != "sections" or not sections:
        return None

    # Find first section not completed or waiting
    for section in sections:
        if section.status not in ["completed", "waiting"]:
            return section.index

    # If all sections are completed or waiting, check if more to process
    if completed_sections < total_sections:
        return completed_sections

    return None


__all__ = [
    "get_stage_from_status",
    "build_section_progress",
    "build_sections_progress",
    "get_current_section_index",
]
