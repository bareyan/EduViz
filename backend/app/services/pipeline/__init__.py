"""
Pipeline services - core video generation flow.

Pipeline Stages:
1. Content Analysis - Analyze uploaded materials
2. Script Generation - Create video script with chapters
3. Visual Script Generation - Create detailed visual storyboards
4. Animation Generation - Generate Manim code from visual scripts
5. Audio Generation - Text-to-speech for narration
6. Video Assembly - Combine videos, audio, and subtitles
"""

from .visual_script import (
    VisualScriptGenerator,
    VisualScriptPlan,
    VisualSegment,
)

__all__ = [
    "VisualScriptGenerator",
    "VisualScriptPlan",
    "VisualSegment",
]
