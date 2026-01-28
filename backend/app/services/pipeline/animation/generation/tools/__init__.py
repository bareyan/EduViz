"""
Manim Tools Module

Unified tool-based approach for Manim generation and correction.
Uses Gemini function calling for structured, reliable outputs.

Structure:
    tools/
    ├── __init__.py         # Exports
    ├── schemas.py          # Tool schemas (JSON schemas for function calling)
    ├── context.py          # Manim context (colors, styles, API reference)
    ├── generation.py       # Code generation and correction tools (unified)
    ├── code_manipulation.py # Code extraction and fix application utilities
"""

from .schemas import (
    WRITE_CODE_SCHEMA,
    FIX_CODE_SCHEMA,
    GENERATE_CODE_SCHEMA,  # Backward compatibility
    VISUAL_SCRIPT_SCHEMA,
)

from .context import (
    ManimContext,
    build_context,
    get_style_config,
    get_style_instructions,
    get_theme_setup_code,
    get_animation_guidance,
    get_language_instructions,
    get_manim_reference,
)

from .generation import (
    GenerationToolHandler,
    GenerationResult,
)

from .code_manipulation import (
    extract_code_from_response,
    apply_fixes,
    find_similar_text,
)

__all__ = [
    # Schemas
    "WRITE_CODE_SCHEMA",
    "FIX_CODE_SCHEMA",
    "GENERATE_CODE_SCHEMA",  # Backward compatibility
    "VISUAL_SCRIPT_SCHEMA",
    # Context
    "ManimContext",
    "build_context",
    "get_style_config",
    "get_style_instructions",
    "get_theme_setup_code",
    "get_animation_guidance",
    "get_language_instructions",
    "get_manim_reference",
    # Generation (handles both generation and correction)
    "GenerationToolHandler",
    "GenerationResult",
    # Code manipulation utilities
    "extract_code_from_response",
    "apply_fixes",
    "find_similar_text",
]
