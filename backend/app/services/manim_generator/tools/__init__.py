"""
Manim Tools Module

Unified tool-based approach for Manim generation and correction.
Uses Gemini function calling for structured, reliable outputs.

Structure:
    tools/
    ├── __init__.py     # Exports
    ├── schemas.py      # Tool schemas (JSON schemas for function calling)
    ├── context.py      # Manim context (colors, styles, API reference)
    ├── generation.py   # Code generation tools
    └── correction.py   # Code correction tools
"""

from .schemas import (
    GENERATE_CODE_SCHEMA,
    SEARCH_REPLACE_SCHEMA,
    VISUAL_SCRIPT_SCHEMA,
    ANALYSIS_SCHEMA,
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

from .correction import (
    CorrectionToolHandler,
    CorrectionResult,
)

__all__ = [
    # Schemas
    "GENERATE_CODE_SCHEMA",
    "SEARCH_REPLACE_SCHEMA",
    "VISUAL_SCRIPT_SCHEMA",
    "ANALYSIS_SCHEMA",
    # Context
    "ManimContext",
    "build_context",
    "get_style_config",
    "get_style_instructions",
    "get_theme_setup_code",
    "get_animation_guidance",
    "get_language_instructions",
    "get_manim_reference",
    # Generation
    "GenerationToolHandler",
    "GenerationResult",
    # Correction
    "CorrectionToolHandler",
    "CorrectionResult",
]