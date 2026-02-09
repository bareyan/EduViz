"""
API schemas for generation endpoints

Request/Response models for video generation operations.
"""

from pydantic import BaseModel
from typing import List, Optional


class GenerationRequest(BaseModel):
    """Request to generate video(s) from analyzed content"""
    file_id: str
    analysis_id: str  # ID returned by /analyze for this file
    selected_topics: List[int]  # Indices from analysis.suggested_topics
    style: str = "3b1b"
    voice: str = "Algieba"  # Gemini TTS voice (use Edge voice if TTS_ENGINE=edge)
    video_mode: str = "comprehensive"  # "comprehensive" or "overview"
    language: str = "en"  # Language code for narration and content
    content_focus: str = "as_document"  # "practice", "theory", or "as_document"
    document_context: str = "auto"  # "standalone", "series" (alias: "part-of-series"), or "auto"
    pipeline: str = "default"  # Named pipeline from GET /pipelines
    resume_job_id: Optional[str] = None  # If provided, resume this job


class GeneratedVideo(BaseModel):
    """A generated video section"""
    section_id: str
    title: str
    duration_seconds: int
    video_path: str
    narration: str


class GenerationResponse(BaseModel):
    """Response after initiating generation"""
    job_id: str
    status: str
    message: str
