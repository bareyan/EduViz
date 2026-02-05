"""
Code Formatting Utilities

Handles class name generation, segment formatting, and other
code-related formatting tasks.

Responsibilities:
- Convert section IDs to valid Python class names
- Format narration segments for LLM context
- Clean and normalize code output
"""

from typing import Dict, Any


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
        return "\n".join([
            f"- T+{s.get('start_time', 0):.1f}s: {s.get('text', '')[:max_chars]}"
            for s in segs
        ])
