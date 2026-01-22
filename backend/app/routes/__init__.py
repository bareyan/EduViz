"""
Routes module - contains all API route handlers
"""

from .upload import router as upload_router
from .analysis import router as analysis_router
from .generation import router as generation_router
from .jobs import router as jobs_router
from .sections import router as sections_router
from .translation import router as translation_router

__all__ = [
    "upload_router",
    "analysis_router", 
    "generation_router",
    "jobs_router",
    "sections_router",
    "translation_router",
]
