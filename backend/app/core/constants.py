"""
Shared constants used across the application.

Centralizes constants that were previously duplicated across multiple modules.
"""

from typing import Dict

# Language code to full name mapping
# Used by: translation_service, tts_engine, routes/translation
LANGUAGE_NAMES: Dict[str, str] = {
    "en": "English",
    "fr": "French",
    "es": "Spanish",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "ar": "Arabic",
    "ru": "Russian",
    "ua": "Ukrainian",
    "hy": "Armenian",
    "hi": "Hindi",
    "tr": "Turkish",
    "pl": "Polish",
    "nl": "Dutch",
    "sv": "Swedish",
    "da": "Danish",
    "no": "Norwegian",
    "fi": "Finnish",
}


def get_language_name(code: str) -> str:
    """Get language name from code, returns code if not found."""
    return LANGUAGE_NAMES.get(code, code.upper())
