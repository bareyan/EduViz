"""
Diff-based Code Correction Module

Uses Aider-style SEARCH/REPLACE blocks for efficient, targeted code fixes.
This approach is 5-10x cheaper and faster than full code regeneration.

Features:
- Structured JSON output mode (Gemini schema - guaranteed format)
- Text-based SEARCH/REPLACE blocks (traditional)
- Fuzzy matching for whitespace differences
- Automatic fallback between modes
- Package version context (Manim 0.18.1)

Usage:
    from app.services.pipeline.animation.correction import correct_manim_code_with_diff
    
    # Drop-in replacement for renderer
    corrected = await correct_manim_code_with_diff(generator, code, error, section)
"""

from .parser import find_search_replace_blocks, SearchReplaceBlock
from .applier import apply_search_replace, apply_all_blocks, validate_syntax
from .integration import correct_manim_code_with_diff
from .prompts import MANIM_VERSION, MANIM_CONTEXT, parse_error_context

__all__ = [
    # Main interface
    'correct_manim_code_with_diff',
    # Parser
    'find_search_replace_blocks',
    'SearchReplaceBlock',
    # Applier
    'apply_search_replace',
    'apply_all_blocks',
    'validate_syntax',
    # Context
    'MANIM_VERSION',
    'MANIM_CONTEXT',
    'parse_error_context',
]
