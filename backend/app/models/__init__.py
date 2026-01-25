"""
Pydantic models for API request/response schemas
"""

from pydantic import BaseModel
from typing import List, Optional


# === Request Models ===

class AnalysisRequest(BaseModel):
    """Request to analyze an uploaded file"""
    file_id: str


class GenerationRequest(BaseModel):
    """Request to generate video(s) from analyzed content"""
    file_id: str
    analysis_id: str
    selected_topics: List[int]  # List of topic indices to generate
    style: str = "3blue1brown"
    max_video_length: int = 20  # Max minutes per video
    voice: str = "en-US-GuyNeural"  # Edge TTS voice
    video_mode: str = "comprehensive"  # "comprehensive" or "overview"
    language: str = "en"  # Language code for narration and content
    content_focus: str = "as_document"  # "practice", "theory", or "as_document"
    document_context: str = "auto"  # "standalone", "series", or "auto"
    pipeline: str = "default"  # Pipeline configuration: "default", "high_quality", "cost_optimized"
    resume_job_id: Optional[str] = None  # If provided, resume this job


class HighQualityCompileRequest(BaseModel):
    """Request to recompile video in high quality"""
    quality: str = "high"  # medium, high, 4k


class CodeUpdateRequest(BaseModel):
    """Request to update Manim code for a section"""
    code: str


class TranslationRequest(BaseModel):
    """Request to translate video to another language"""
    target_language: str


class RecompileRequest(BaseModel):
    """Request to recompile sections"""
    section_ids: Optional[List[str]] = None  # If None, recompile all failed sections


# === Response Models ===

class TopicSuggestion(BaseModel):
    """A suggested video topic from analysis"""
    index: int
    title: str
    description: str
    estimated_duration: int  # in minutes
    complexity: str  # "beginner", "intermediate", "advanced"
    subtopics: List[str]


class AnalysisResult(BaseModel):
    """Result of document analysis"""
    analysis_id: str
    file_id: str
    material_type: str  # "pdf", "image", "text"
    total_content_pages: int
    detected_math_elements: int
    suggested_topics: List[TopicSuggestion]
    estimated_total_videos: int
    summary: str


class VideoChapter(BaseModel):
    """A chapter/section within a video"""
    title: str
    start_time: float
    duration: float


class GeneratedVideo(BaseModel):
    """A generated video"""
    video_id: str
    title: str
    duration: float
    chapters: List[VideoChapter]
    download_url: str
    thumbnail_url: Optional[str]


class JobResponse(BaseModel):
    """Response with job status and results"""
    job_id: str
    status: str
    progress: float
    message: str
    result: Optional[List[GeneratedVideo]] = None


class ResumeInfo(BaseModel):
    """Information about resumable job progress"""
    can_resume: bool
    completed_sections: int
    total_sections: int
    failed_sections: List[str]
    last_completed_section: Optional[str]


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


class DetailedProgress(BaseModel):
    """Detailed progress information for a job"""
    job_id: str
    status: str
    progress: float
    message: str
    current_stage: str  # "analyzing", "script", "sections", "combining"
    current_section_index: Optional[int] = None
    script_ready: bool = False
    script_title: Optional[str] = None
    total_sections: int = 0
    completed_sections: int = 0
    sections: List[SectionProgress] = []


class SectionInfo(BaseModel):
    """Information about a video section"""
    id: str
    title: str
    status: str
    has_video: bool
    has_audio: bool
    has_code: bool
    video_url: Optional[str]
    error: Optional[str]


class TranslationInfo(BaseModel):
    """Information about available translations"""
    language: str
    language_name: str
    has_audio: bool
    has_video: bool
    video_url: Optional[str]


class TranslationResponse(BaseModel):
    """Response from translation request"""
    job_id: str
    language: str
    status: str
    message: str
