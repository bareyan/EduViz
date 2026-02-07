"""
Tests for the whole-section TTS path in assembly/sections.py

Verifies that when a TTS engine has ``_whole_section_tts = True`` (e.g. Gemini TTS),
the section processor consolidates all segment texts into a single TTS call and
distributes timing proportionally.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from app.services.pipeline.assembly.sections import (
    _is_whole_section_tts,
    _generate_audio_whole_section,
    _generate_audio_per_segment,
    clean_narration_for_tts,
)


class TestIsWholeSectionTTS:
    def test_returns_false_for_edge_engine(self):
        engine = MagicMock(spec=[])
        assert _is_whole_section_tts(engine) is False

    def test_returns_true_when_flag_set(self):
        engine = MagicMock(spec=[])
        engine._whole_section_tts = True
        assert _is_whole_section_tts(engine) is True

    def test_returns_false_when_flag_false(self):
        engine = MagicMock(spec=[])
        engine._whole_section_tts = False
        assert _is_whole_section_tts(engine) is False


@pytest.mark.asyncio
class TestGenerateAudioWholeSection:
    """Test the whole-section TTS path (1 API call per section)."""

    async def test_single_api_call_for_all_segments(self, tmp_path):
        """All segments should be combined into ONE generate_speech call."""
        segments = [
            {"text": "First segment of narration.", "estimated_duration": 5.0},
            {"text": "Second segment of narration.", "estimated_duration": 5.0},
            {"text": "Third segment.", "estimated_duration": 3.0},
        ]

        mock_engine = AsyncMock()
        mock_engine.generate_speech = AsyncMock(return_value=12.0)

        with patch(
            "app.services.pipeline.assembly.sections.get_audio_duration",
            AsyncMock(return_value=12.0),
        ):
            info, total = await _generate_audio_whole_section(
                tts_engine=mock_engine,
                narration_segments=segments,
                section_dir=tmp_path,
                section_index=0,
                voice="Charon",
            )

        # Only 1 API call
        assert mock_engine.generate_speech.call_count == 1

        # All segments should be returned
        assert len(info) == 3
        assert total == pytest.approx(12.0, abs=0.01)

    async def test_proportional_timing(self, tmp_path):
        """Segment timings should be distributed by character count."""
        segments = [
            {"text": "Short."},           # 6 chars
            {"text": "A much longer segment here."},  # 26 chars
        ]

        mock_engine = AsyncMock()
        mock_engine.generate_speech = AsyncMock(return_value=10.0)

        with patch(
            "app.services.pipeline.assembly.sections.get_audio_duration",
            AsyncMock(return_value=10.0),
        ):
            info, total = await _generate_audio_whole_section(
                tts_engine=mock_engine,
                narration_segments=segments,
                section_dir=tmp_path,
                section_index=0,
                voice="Charon",
            )

        assert total == pytest.approx(10.0, abs=0.01)

        # Segment 0 is 6 chars, segment 1 is 26 chars → 6/32 and 26/32
        assert info[0]["duration"] < info[1]["duration"]
        assert info[0]["start_time"] == pytest.approx(0.0)
        assert info[0]["end_time"] == pytest.approx(info[1]["start_time"], abs=0.01)
        assert info[1]["end_time"] == pytest.approx(total, abs=0.01)

    async def test_returns_empty_on_failure(self, tmp_path):
        """If TTS call fails, returns empty info."""
        segments = [{"text": "Hello.", "estimated_duration": 3.0}]

        mock_engine = AsyncMock()
        mock_engine.generate_speech = AsyncMock(side_effect=Exception("API error"))

        info, total = await _generate_audio_whole_section(
            tts_engine=mock_engine,
            narration_segments=segments,
            section_dir=tmp_path,
            section_index=0,
            voice="Charon",
        )

        assert info == []
        assert total == 0.0


@pytest.mark.asyncio
class TestGenerateAudioPerSegment:
    """Test the per-segment TTS path (original behavior)."""

    async def test_one_call_per_segment(self, tmp_path):
        segments = [
            {"text": "Segment one.", "estimated_duration": 4.0},
            {"text": "Segment two.", "estimated_duration": 4.0},
        ]

        mock_engine = AsyncMock()
        mock_engine.generate_speech = AsyncMock(return_value=4.0)

        with patch(
            "app.services.pipeline.assembly.sections.get_audio_duration",
            AsyncMock(return_value=4.0),
        ):
            info, total = await _generate_audio_per_segment(
                tts_engine=mock_engine,
                narration_segments=segments,
                section_dir=tmp_path,
                section_index=0,
                voice="en-GB-RyanNeural",
            )

        assert mock_engine.generate_speech.call_count == 2
        assert len(info) == 2
        assert total == pytest.approx(8.0, abs=0.01)
