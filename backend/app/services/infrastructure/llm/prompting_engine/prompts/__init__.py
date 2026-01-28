"""
Prompt Registry - Clean exports and registry pattern.

Structure:
    prompts/
    ├── __init__.py      # This file - exports and registry
    ├── base.py          # PromptTemplate class
    ├── language.py      # Language detection
    ├── script_generation.py  # Script/outline prompts
    ├── translation.py   # Translation prompts
    └── analysis.py      # Content analysis

Note: Manim generation uses tool-based prompts in pipeline/animation/prompts.py

Usage:
    from app.services.infrastructure.llm.prompting_engine.prompts import format_prompt
    
    prompt = format_prompt("LANGUAGE_DETECTION", content="Hello world")
    
    # Or import directly:
    from app.services.infrastructure.llm.prompting_engine.prompts.translation import TRANSLATE_NARRATION_BULK
"""

from typing import Dict

# Base class
from .base import PromptTemplate

# Import all prompts by domain
from .language import LANGUAGE_DETECTION

from .script_generation import (
    SCRIPT_OVERVIEW,
    SCRIPT_OUTLINE,
    SCRIPT_SECTION,
)

from .translation import (
    TRANSLATE_NARRATION,
    TRANSLATE_NARRATION_BULK,
    TRANSLATE_DISPLAY_TEXT,
    TRANSLATE_DISPLAY_TEXT_BATCH,
    TRANSLATE_TTS,
    TRANSLATE_TTS_SPEAKABLE,
    TRANSLATE_BATCH,
    TRANSLATE_ITEMS_BATCH,
)

from .analysis import (
    ANALYZE_TEXT,
    ANALYZE_TEXT_CONTENT,
    ANALYZE_PDF,
    ANALYZE_PDF_CONTENT,
    ANALYZE_IMAGE,
)


# =============================================================================
# REGISTRY - Maps string names to prompt templates
# =============================================================================

_REGISTRY: Dict[str, PromptTemplate] = {
    # Language
    "LANGUAGE_DETECTION": LANGUAGE_DETECTION,
    
    # Script Generation
    "SCRIPT_OVERVIEW": SCRIPT_OVERVIEW,
    "SCRIPT_OUTLINE": SCRIPT_OUTLINE,
    "SCRIPT_SECTION": SCRIPT_SECTION,
    
    # Translation
    "TRANSLATE_NARRATION": TRANSLATE_NARRATION,
    "TRANSLATE_NARRATION_BULK": TRANSLATE_NARRATION_BULK,
    "TRANSLATE_DISPLAY_TEXT": TRANSLATE_DISPLAY_TEXT,
    "TRANSLATE_DISPLAY_TEXT_BATCH": TRANSLATE_DISPLAY_TEXT_BATCH,
    "TRANSLATE_TTS": TRANSLATE_TTS,
    "TRANSLATE_TTS_SPEAKABLE": TRANSLATE_TTS_SPEAKABLE,
    "TRANSLATE_BATCH": TRANSLATE_BATCH,
    "TRANSLATE_ITEMS_BATCH": TRANSLATE_ITEMS_BATCH,
    
    # Analysis
    "ANALYZE_TEXT": ANALYZE_TEXT,
    "ANALYZE_TEXT_CONTENT": ANALYZE_TEXT_CONTENT,
    "ANALYZE_PDF": ANALYZE_PDF,
    "ANALYZE_PDF_CONTENT": ANALYZE_PDF_CONTENT,
    "ANALYZE_IMAGE": ANALYZE_IMAGE,
}


# =============================================================================
# PUBLIC API
# =============================================================================

def get_prompt(name: str) -> PromptTemplate:
    """Get a prompt template by name."""
    if name not in _REGISTRY:
        available = ", ".join(sorted(_REGISTRY.keys()))
        raise KeyError(f"Unknown prompt: '{name}'. Available: {available}")
    return _REGISTRY[name]


def format_prompt(name: str, **kwargs) -> str:
    """Get and format a prompt in one call."""
    return get_prompt(name).format(**kwargs)


def list_prompts() -> list:
    """List all available prompt names."""
    return sorted(_REGISTRY.keys())


def list_prompts_by_domain() -> Dict[str, list]:
    """List prompts grouped by domain."""
    return {
        "language": ["LANGUAGE_DETECTION"],
        "script_generation": ["SCRIPT_OVERVIEW", "SCRIPT_OUTLINE", "SCRIPT_SECTION"],
        "translation": [
            "TRANSLATE_NARRATION", "TRANSLATE_NARRATION_BULK",
            "TRANSLATE_DISPLAY_TEXT", "TRANSLATE_DISPLAY_TEXT_BATCH",
            "TRANSLATE_TTS", "TRANSLATE_TTS_SPEAKABLE",
            "TRANSLATE_BATCH", "TRANSLATE_ITEMS_BATCH"
        ],
        "analysis": ["ANALYZE_TEXT", "ANALYZE_TEXT_CONTENT", "ANALYZE_PDF", "ANALYZE_PDF_CONTENT", "ANALYZE_IMAGE"],
    }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Base
    "PromptTemplate",
    
    # Functions
    "get_prompt",
    "format_prompt",
    "list_prompts",
    "list_prompts_by_domain",
    
    # Language
    "LANGUAGE_DETECTION",
    
    # Script Generation
    "SCRIPT_OVERVIEW",
    "SCRIPT_OUTLINE", 
    "SCRIPT_SECTION",
    
    # Translation
    "TRANSLATE_NARRATION",
    "TRANSLATE_NARRATION_BULK",
    "TRANSLATE_DISPLAY_TEXT",
    "TRANSLATE_DISPLAY_TEXT_BATCH",
    "TRANSLATE_TTS",
    "TRANSLATE_TTS_SPEAKABLE",
    "TRANSLATE_BATCH",
    "TRANSLATE_ITEMS_BATCH",
    
    # Analysis
    "ANALYZE_TEXT",
    "ANALYZE_TEXT_CONTENT",
    "ANALYZE_PDF",
    "ANALYZE_PDF_CONTENT",
    "ANALYZE_IMAGE",
]
