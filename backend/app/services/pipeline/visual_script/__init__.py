"""
Visual Script Generation Pipeline

Generates detailed visual storyboards (Visual Scripts) from audio segments.
This step sits between script generation and Manim animation generation.

The Visual Script serves as a detailed plan for the animator, including:
- Visual descriptions for each audio segment
- Visual elements to be used (shapes, equations, etc.)
- Post-narration pauses for complex animations
- Timing synchronization information
"""

from .generator import (
    VisualScriptGenerator,
    GenerationResult,
    update_audio_segments_with_actual_durations,
    load_visual_script,
)
from .schemas import (
    VisualSegment,
    VisualScriptPlan,
    get_schema as get_visual_script_schema,
)
from .prompts import (
    build_audio_segments_from_section,
    build_user_prompt,
)
from .config import (
    DEFAULT_POST_PAUSE,
    MAX_POST_PAUSE,
    MIN_POST_PAUSE,
    GENERATION_TIMEOUT,
    GENERATION_TEMPERATURE,
)

__all__ = [
    # Generator
    "VisualScriptGenerator",
    "GenerationResult",
    # Schemas
    "VisualSegment",
    "VisualScriptPlan",
    "get_visual_script_schema",
    # Helpers
    "build_audio_segments_from_section",
    "build_user_prompt",
    "update_audio_segments_with_actual_durations",
    "load_visual_script",
    # Config
    "DEFAULT_POST_PAUSE",
    "MAX_POST_PAUSE",
    "MIN_POST_PAUSE",
    "GENERATION_TIMEOUT",
    "GENERATION_TEMPERATURE",
]
