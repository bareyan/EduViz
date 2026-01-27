"""
Prompting Engine - Centralized LLM interaction layer

Provides unified interface for all LLM operations across the application.
Handles Gemini API calls, function calling, retries, and cost tracking.

PROMPT ORGANIZATION:
    prompts/
    ├── language.py          # Language detection
    ├── script_generation.py # Script/outline prompts
    ├── manim.py            # Manim code generation
    ├── code_correction.py  # Error fixing
    ├── translation.py      # Translation prompts
    ├── analysis.py         # Content analysis
    └── visual_qc.py        # Visual quality control

Usage:
    from app.services.prompting_engine import format_prompt, PromptingEngine
    
    engine = PromptingEngine()
    prompt = format_prompt("LANGUAGE_DETECTION", content="Hello")
"""

from .base_engine import PromptingEngine, PromptConfig
from .tool_handler import ToolHandler, Tool
from .prompts import (
    PromptTemplate,
    get_prompt,
    format_prompt,
    list_prompts,
    list_prompts_by_domain,
)

__all__ = [
    # Engine
    "PromptingEngine",
    "PromptConfig",
    # Tools
    "ToolHandler",
    "Tool",
    # Prompts
    "PromptTemplate",
    "get_prompt",
    "format_prompt",
    "list_prompts",
    "list_prompts_by_domain",
]
