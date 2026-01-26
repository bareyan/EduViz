"""
Script generation package

Provides two script generation modes:
1) Overview mode: Single-prompt generation for short ~5 minute videos
2) Comprehensive mode: Two-phase approach (outline + sections) for detailed lectures

Main entry point: ScriptGenerator
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
