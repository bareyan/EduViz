"""
Pydantic models for API request/response schemas

Organized by endpoint:
- analysis.py: Analysis request/response models
- generation.py: Generation request/response models
- jobs.py: Job status and progress models
- sections.py: Section and code update models
- translation.py: Translation request/response models
"""

# Analysis models
from .analysis import AnalysisRequest, AnalysisResult, TopicSuggestion

# Generation models
from .generation import GenerationRequest, GenerationResponse, GeneratedVideo

# Section models
from .sections import (
    CodeUpdateRequest,
    SectionProgress,
    SectionInfo,
    HighQualityCompileRequest,
    RecompileRequest,
)

# Job models
from .jobs import ResumeInfo, DetailedProgress, JobResponse

# Translation models
from .translation import TranslationRequest, TranslationInfo, TranslationResponse

__all__ = [
    # Analysis
    "AnalysisRequest",
    "AnalysisResult",
    "TopicSuggestion",
    # Generation
    "GenerationRequest",
    "GenerationResponse",
    "GeneratedVideo",
    # Sections
    "CodeUpdateRequest",
    "SectionProgress",
    "SectionInfo",
    "HighQualityCompileRequest",
    "RecompileRequest",
    # Jobs
    "ResumeInfo",
    "DetailedProgress",
    "JobResponse",
    # Translation
    "TranslationRequest",
    "TranslationInfo",
    "TranslationResponse",
]
