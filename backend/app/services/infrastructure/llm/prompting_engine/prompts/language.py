"""
Language detection prompts.
"""

from .base import PromptTemplate


LANGUAGE_DETECTION = PromptTemplate(
    template="""Detect the primary language of this text. Respond with ONLY the ISO 639-1 code (e.g., "en", "fr", "es").

Text:
{content}

Language code:""",
    description="Detect language from text content"
)
