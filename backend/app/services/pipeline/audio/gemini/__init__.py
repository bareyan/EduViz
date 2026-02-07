"""Gemini TTS package."""

from .constants import (
    DEFAULT_GEMINI_MODEL,
    DEFAULT_GEMINI_VOICE,
    GEMINI_VOICES,
    PAUSE_MARKERS,
)
from .engine import GeminiTTSEngine, _RateLimiter
from .timing import (
    GeminiTTSTimingComponent,
    SubtitleTimingItem,
    TTSTimingConfig,
    TTSTimingResult,
    generate_tts_timing,
)

__all__ = [
    "DEFAULT_GEMINI_MODEL",
    "DEFAULT_GEMINI_VOICE",
    "GEMINI_VOICES",
    "PAUSE_MARKERS",
    "GeminiTTSEngine",
    "_RateLimiter",
    "GeminiTTSTimingComponent",
    "SubtitleTimingItem",
    "TTSTimingConfig",
    "TTSTimingResult",
    "generate_tts_timing",
]
