"""Tests for app.services.pipeline.audio.gemini."""

import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from app.services.pipeline.audio.gemini import (
    GeminiTTSEngine,
    _RateLimiter,
    GEMINI_VOICES,
    DEFAULT_GEMINI_VOICE,
)


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestRateLimiter:
    async def test_acquire_under_limit(self):
        limiter = _RateLimiter(max_rpm=5)
        # Should not block
        for _ in range(5):
            await limiter.acquire()

    async def test_acquire_blocks_when_full(self):
        limiter = _RateLimiter(max_rpm=2)
        await limiter.acquire()
        await limiter.acquire()
        # Next acquire should block — we just verify it eventually completes
        # by setting a very short sleep mock
        with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            # Simulate timestamps expiring soon
            import time
            limiter._timestamps = [time.monotonic() - 59.5, time.monotonic() - 59.5]
            await limiter.acquire()
            # Should have waited
            mock_sleep.assert_called_once()


# ---------------------------------------------------------------------------
# GeminiTTSEngine
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_genai():
    """Patch google.genai so we don't need the real SDK."""
    with patch("app.services.pipeline.audio.gemini.engine.os.getenv") as mock_env:
        mock_env.side_effect = lambda key, default=None: {
            "GEMINI_API_KEY": "fake-key",
            "GEMINI_TTS_RPM": "100",  # high limit to avoid waits in tests
        }.get(key, default)
        yield mock_env


@pytest.fixture
def engine():
    return GeminiTTSEngine(model="gemini-2.5-flash-preview-tts")


@pytest.mark.asyncio
class TestGeminiTTSEngine:

    async def test_synthesize_success(self, engine, tmp_path):
        """Successful TTS call: API → WAV → MP3."""
        fake_pcm = b"\x00\x00" * 24000  # 1 second of silence at 24kHz 16-bit mono
        output_mp3 = str(tmp_path / "audio.mp3")

        with (
            patch.object(engine, "_call_gemini_tts", AsyncMock(return_value=fake_pcm)),
            patch.object(engine, "_convert_wav_to_mp3", AsyncMock()),
            patch.object(engine, "_get_audio_duration", AsyncMock(return_value=5.2)),
            patch(
                "app.services.pipeline.audio.gemini.engine._rate_limiter",
                AsyncMock(acquire=AsyncMock()),
            ),
        ):
            duration = await engine.synthesize("Hello world", output_mp3, voice="Charon")

        assert duration == 5.2

    async def test_synthesize_fallback_on_api_failure(self, engine, tmp_path):
        output_mp3 = str(tmp_path / "audio.mp3")

        with (
            patch.object(engine, "_call_gemini_tts", AsyncMock(return_value=None)),
            patch.object(engine, "_create_placeholder_audio", AsyncMock(return_value=6.0)),
            patch(
                "app.services.pipeline.audio.gemini.engine._rate_limiter",
                AsyncMock(acquire=AsyncMock()),
            ),
        ):
            duration = await engine.synthesize("Hello", output_mp3)

        assert duration == 6.0

    async def test_unknown_voice_falls_back(self, engine, tmp_path):
        output_mp3 = str(tmp_path / "audio.mp3")

        with (
            patch.object(engine, "_call_gemini_tts", AsyncMock(return_value=b"\x00")) as mock_call,
            patch.object(engine, "_write_wav"),
            patch.object(engine, "_convert_wav_to_mp3", AsyncMock()),
            patch.object(engine, "_get_audio_duration", AsyncMock(return_value=1.0)),
            patch(
                "app.services.pipeline.audio.gemini.engine._rate_limiter",
                AsyncMock(acquire=AsyncMock()),
            ),
        ):
            await engine.synthesize("test", output_mp3, voice="NonExistentVoice")
            # Should have been called with the default voice
            mock_call.assert_called_once_with("test", DEFAULT_GEMINI_VOICE)

    async def test_generate_speech_alias(self, engine, tmp_path):
        output_mp3 = str(tmp_path / "audio.mp3")

        with (
            patch.object(engine, "synthesize", AsyncMock(return_value=3.0)) as mock_synth,
        ):
            duration = await engine.generate_speech("hi", output_mp3, voice="Puck")

        assert duration == 3.0
        mock_synth.assert_called_once()

    async def test_voice_helpers(self):
        voices = GeminiTTSEngine.get_available_voices()
        assert "Charon" in voices
        assert "Puck" in voices
        assert len(voices) == len(GEMINI_VOICES)

    async def test_default_voice(self):
        assert GeminiTTSEngine.get_default_voice() == "Charon"


# ---------------------------------------------------------------------------
# Factory function
# ---------------------------------------------------------------------------

class TestCreateTTSEngine:

    def test_default_returns_edge(self):
        with patch.dict("os.environ", {}, clear=False):
            # Remove TTS_ENGINE if present
            import os
            os.environ.pop("TTS_ENGINE", None)
            from app.services.pipeline.audio import create_tts_engine, TTSEngine
            engine = create_tts_engine()
            assert isinstance(engine, TTSEngine)

    def test_gemini_returns_gemini(self):
        with patch.dict("os.environ", {"TTS_ENGINE": "gemini"}):
            from importlib import reload
            import app.services.pipeline.audio as audio_mod
            # Re-call the factory (env is set)
            engine = audio_mod.create_tts_engine()
            assert isinstance(engine, GeminiTTSEngine)
            assert getattr(engine, "_whole_section_tts", False) is True
