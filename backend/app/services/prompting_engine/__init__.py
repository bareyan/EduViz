"""
Prompting Engine - Centralized LLM interaction layer

Provides unified interface for all LLM operations across the application.
Handles Gemini API calls, function calling, retries, and cost tracking.

ALL PROMPTS ARE IN: prompts.py
"""

from .base_engine import PromptingEngine, PromptConfig
from .tool_handler import ToolHandler, Tool
from .prompts import prompts, get_prompt, format_prompt, list_prompts, PromptTemplate

__all__ = [
    # Engine
    "PromptingEngine",
    "PromptConfig",
    # Tools
    "ToolHandler",
    "Tool",
    # Prompts
    "prompts",
    "get_prompt",
    "format_prompt",
    "list_prompts",
    "PromptTemplate",
]
