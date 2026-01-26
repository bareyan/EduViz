"""
Script generation package

Provides a two-phase script generation pipeline:
1) OutlineBuilder - creates detailed pedagogical outline
2) SectionGenerator - generates narration for each section

Main entry point: ScriptGenerator
"""

from .generator import ScriptGenerator
from .outline_builder import OutlineBuilder
from .section_generator import SectionGenerator
from .base import BaseScriptGenerator

__all__ = [
    "ScriptGenerator",
    "OutlineBuilder",
    "SectionGenerator",
    "BaseScriptGenerator",
]
