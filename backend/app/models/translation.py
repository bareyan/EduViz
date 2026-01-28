"""
API schemas for translation endpoints

Models for translation requests and responses.
"""

from pydantic import BaseModel
from typing import Optional


class TranslationRequest(BaseModel):
    """Request to translate video to another language"""
    job_id: str
    target_language: str
    voice: Optional[str] = None  # Optional voice preference


class TranslationInfo(BaseModel):
    """Information about available translations"""
    language: str
    language_name: str
    has_audio: bool
    has_video: bool
    video_url: Optional[str] = None


class TranslationResponse(BaseModel):
    """Response from translation request"""
    job_id: str
    language: str
    status: str
    message: str
