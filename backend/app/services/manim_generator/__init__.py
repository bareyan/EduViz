"""
Manim Generator Package

Provides AI-powered Manim animation generation using Gemini.

Modules:
    - generator: Main ManimGenerator class
    - renderer: Scene rendering with error correction
    - prompts: Prompt templates and builders
    - cost_tracker: API usage and cost tracking
    - code_helpers: Code cleaning and scene file creation
"""

from .generator import ManimGenerator
from .cost_tracker import CostTracker, track_cost_safely

__all__ = [
    'ManimGenerator',
    'CostTracker',
    'track_cost_safely',
]
