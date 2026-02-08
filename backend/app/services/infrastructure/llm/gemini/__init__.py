"""
Gemini AI Service Module

Provides Gemini API client and helper utilities for AI content generation.

Usage:
    from app.services.infrastructure.llm.gemini import get_gemini_client, generate_content_with_text
"""

from .client import get_gemini_client, create_client
from .helpers import (
    generate_content_with_text,
    generate_content_with_images,
    generate_structured_output,
)

__all__ = [
    "get_gemini_client",
    "create_client",

    "generate_content_with_text",
    "generate_content_with_images",
    "generate_structured_output",
]
