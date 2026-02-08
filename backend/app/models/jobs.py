"""
API schemas for job management endpoints

Models for job status, progress tracking, and resumable jobs.
"""

from pydantic import BaseModel
from typing import List, Optional, Union
from .sections import SectionProgress


class ResumeInfo(BaseModel):
    """Information about resumable job progress"""
    can_resume: bool
    completed_sections: int
    total_sections: int
    failed_sections: List[str] = []
    last_completed_section: Optional[str] = None


class DetailedProgress(BaseModel):
    """Detailed progress information for a job"""
    job_id: str
    status: str
    progress: float  # 0.0 to 1.0
    message: str
    current_stage: str  # "analyzing", "script", "sections", "combining"
    current_section_index: Optional[int] = None
    script_ready: bool = False
    script_title: Optional[str] = None
    total_sections: int = 0
    completed_sections: int = 0
    sections: List[SectionProgress] = []


class JobResponse(BaseModel):
    """Response with job status and results"""
    job_id: str
    status: str
    progress: float
    message: str
    result: Optional[Union[dict, list]] = None
    details: Optional[DetailedProgress] = None


class JobUpdateRequest(BaseModel):
    """Request to update job metadata"""
    title: Optional[str] = None
