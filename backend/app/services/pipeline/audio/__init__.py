"""Audio generation - text-to-speech."""

import os
from typing import Union

from .tts_engine import TTSEngine
from .gemini_tts_engine import GeminiTTSEngine

# Type alias for any TTS engine
AnyTTSEngine = Union[TTSEngine, GeminiTTSEngine]


def create_tts_engine() -> AnyTTSEngine:
    """Factory: return the right TTS engine based on ``TTS_ENGINE`` env var.

    Supported values:
      - ``"edge"``   (default) – free Edge TTS via ``edge-tts``
      - ``"gemini"`` – Gemini 2.5 Flash TTS (rate-limited: 8 RPM / 100 RPD)

    The returned object exposes the same ``generate_speech`` / ``synthesize``
    interface regardless of backend.
    """
    engine_name = os.getenv("TTS_ENGINE", "edge").lower().strip()

    if engine_name == "gemini":
        engine = GeminiTTSEngine()
        # Flag used by section processor to switch to whole-section generation
        engine._whole_section_tts = True  # type: ignore[attr-defined]
        return engine

    # Default: Edge TTS (free, no rate limits)
    return TTSEngine()


__all__ = ["TTSEngine", "GeminiTTSEngine", "AnyTTSEngine", "create_tts_engine"]
