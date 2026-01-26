"""
Job status constants and enumerations.

Centralized job status definitions to replace magic strings throughout codebase.
"""

from enum import Enum


class JobStatus(Enum):
    """Enumeration of all possible job statuses."""
    
    PENDING = "pending"
    ANALYZING = "analyzing"
    GENERATING_SCRIPT = "generating_script"
    CREATING_ANIMATIONS = "creating_animations"
    SYNTHESIZING_AUDIO = "synthesizing_audio"
    COMPOSING_VIDEO = "composing_video"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"
    
    def is_terminal(self) -> bool:
        """Check if this status is a terminal state (no further progress)."""
        return self in (JobStatus.COMPLETED, JobStatus.FAILED)
    
    def is_in_progress(self) -> bool:
        """Check if this status indicates active processing."""
        return self not in (JobStatus.PENDING, JobStatus.COMPLETED, JobStatus.FAILED)


# Mapping of status to human-readable stage names
STATUS_TO_STAGE_MAP = {
    "pending": "analyzing",
    "analyzing": "analyzing",
    "generating_script": "script",
    "creating_animations": "sections",
    "synthesizing_audio": "sections",
    "composing_video": "combining",
    "completed": "completed",
    "failed": "failed"
}


def get_stage_from_status(status: str) -> str:
    """
    Convert a job status to its stage name.
    
    Args:
        status: The job status string
        
    Returns:
        The corresponding stage name for UI/reporting
    """
    return STATUS_TO_STAGE_MAP.get(status, "unknown")


__all__ = [
    "JobStatus",
    "STATUS_TO_STAGE_MAP",
    "get_stage_from_status",
]
