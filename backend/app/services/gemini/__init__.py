"""
Gemini AI Service Module

Provides Gemini API client and helper utilities for AI content generation.

Usage:
    from app.services.gemini import get_gemini_client, generate_content_with_text
"""

from .client import get_gemini_client, create_client, get_types_module
from .helpers import (
    generate_content_with_text,
    generate_content_with_images,
    generate_structured_output,
)

__all__ = [
    "get_gemini_client",
    "create_client",
    "get_types_module",
    "generate_content_with_text",
    "generate_content_with_images",
    "generate_structured_output",
]
