"""
Script Generation Package

Generates video scripts using centralized prompting engine.

Modes:
- Overview: Single-prompt for short videos (~5 min)
- Comprehensive: Two-phase (outline + sections) for detailed lectures
"""

from .generator import ScriptGenerator
from .outline_builder import OutlineBuilder
from .section_generator import SectionGenerator
from .overview_generator import OverviewGenerator
from .base import BaseScriptGenerator

__all__ = [
    "ScriptGenerator",
    "OutlineBuilder",
    "SectionGenerator",
    "OverviewGenerator",
    "BaseScriptGenerator",
]
