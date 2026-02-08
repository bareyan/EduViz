"""
Code Formatting Utilities

Handles class name generation, segment formatting, and other
code-related formatting tasks.

Responsibilities:
- Convert section IDs to valid Python class names
- Format narration segments for LLM context
- Clean and normalize code output
"""

import json
from typing import Dict, Any

# Language code to display name mapping
_SUPPORTED_LANGUAGES = {
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
}


class CodeFormatter:
    """Formats code and related strings for animation generation."""
    
    @staticmethod
    def derive_class_name(section: Dict[str, Any]) -> str:
        """Convert section ID to valid PEP8 class name.
        
        Args:
            section: Section dictionary with 'id' or 'index'
            
        Returns:
            Valid Python class name in PascalCase
            
        Example:
            >>> CodeFormatter.derive_class_name({"id": "intro-to-calculus"})
            'IntroToCalculus'
        """
        raw_id = section.get("id", f"section_{section.get('index', 0)}")
        normalized = raw_id.replace("-", "_").replace(" ", "_")
        return "".join(word.title() for word in normalized.split("_"))
    
    @staticmethod
    def summarize_segments(section: Dict[str, Any], max_chars: int = 60) -> str:
        """Format narration segments for LLM context.
        
        Args:
            section: Section dictionary with 'narration_segments'
            max_chars: Maximum characters per segment text
            
        Returns:
            Formatted string with timestamped segments
            
        Example:
            >>> formatter.summarize_segments({"narration_segments": [
            ...     {"start_time": 0.0, "text": "Welcome to calculus"},
            ...     {"start_time": 2.5, "text": "Today we'll learn derivatives"}
            ... ]})
            '- T+0.0s: Welcome to calculus\\n- T+2.5s: Today we\\'ll learn derivatives'
        """
        segs = section.get("narration_segments", [])
        lines = []
        running_time = 0.0

        for seg in segs:
            raw_start = seg.get("start_time")
            if isinstance(raw_start, (int, float)):
                start_time = float(raw_start)
            else:
                start_time = running_time

            text = str(seg.get("text", ""))[:max_chars]
            lines.append(f"- T+{start_time:.1f}s: {text}")

            est = seg.get("estimated_duration")
            if isinstance(est, (int, float)) and est > 0:
                running_time = max(running_time, start_time + float(est))

        return "\n".join(lines)

    @staticmethod
    def serialize_for_prompt(data: Any, default: str = "None provided") -> str:
        """Serialize optional structured data for prompt templates."""
        if data in (None, "", [], {}):
            return default
        if isinstance(data, str):
            return data
        try:
            return json.dumps(data, ensure_ascii=False, indent=2)
        except (TypeError, ValueError):
            return str(data)
    
    @staticmethod
    def get_language_name(language_code: str) -> str:
        """Convert language code to display name.
        
        Args:
            language_code: ISO language code (e.g., 'en', 'fr', 'ru')
            
        Returns:
            Display name of the language (e.g., 'English', 'French', 'Russian')
            Defaults to 'English' for unknown codes
            
        Example:
            >>> CodeFormatter.get_language_name('ru')
            'Russian'
            >>> CodeFormatter.get_language_name('unknown')
            'English'
        """
        from ..constants import DEFAULT_LANGUAGE
        return _SUPPORTED_LANGUAGES.get(language_code, _SUPPORTED_LANGUAGES[DEFAULT_LANGUAGE])
