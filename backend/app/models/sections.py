"""
API schemas for section management endpoints

Models for section info, code updates, and section progress tracking.
"""

from pydantic import BaseModel
from typing import List, Optional


class CodeUpdateRequest(BaseModel):
    """Request to update Manim code for a section"""
    code: str
    fix_attempt: int = 1


class SectionProgress(BaseModel):
    """Progress information for a single section"""
    index: int
    id: str
    title: str
    status: str  # "waiting", "generating_script", "generating_manim", "fixing_manim", "generating_audio", "completed", "failed"
    duration_seconds: Optional[float] = None
    narration_preview: Optional[str] = None  # First 200 chars of narration
    has_video: bool = False
    has_audio: bool = False
    has_code: bool = False
    error: Optional[str] = None
    fix_attempts: int = 0
    qc_iterations: int = 0


class SectionInfo(BaseModel):
    """Information about a video section"""
    id: str
    title: str
    status: str
    has_video: bool
    has_audio: bool
    has_code: bool
    video_url: Optional[str] = None
    error: Optional[str] = None


class HighQualityCompileRequest(BaseModel):
    """Request to recompile video in high quality"""
    quality: str = "high"  # medium, high, 4k


class RecompileRequest(BaseModel):
    """Request to recompile sections"""
    section_ids: Optional[List[str]] = None  # If None, recompile all failed sections
