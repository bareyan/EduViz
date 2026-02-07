"""
Tests for pause-based audio segmentation with Gemini TTS

Validates the timing extraction approach:
1. Insert long pause markers between segments
2. Analyse energy envelope to find the N-1 quietest valleys
3. Split audio at speech boundaries (excluding pauses)
4. Trim residual silence from segment edges
"""

import pytest
import struct
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.pipeline.assembly.sections import (
    _detect_silence_boundaries,
    _find_energy_valleys,
    _extract_energy_envelope,
    _split_audio_at_pauses,
    _trim_segment_edges,
    _generate_audio_whole_section,
)


@pytest.mark.asyncio
async def test_detect_silence_boundaries(tmp_path):
    """Test silence detection parses ffmpeg output and returns (start, end) regions."""

    # Mock ffmpeg output with silence detection
    mock_output = """
[silencedetect @ 0x123] silence_start: 5.2
[silencedetect @ 0x123] silence_end: 5.8 | silence_duration: 0.6
[silencedetect @ 0x123] silence_start: 12.5
[silencedetect @ 0x123] silence_end: 13.1 | silence_duration: 0.6
    """.strip()

    mock_process = AsyncMock()
    mock_process.communicate = AsyncMock(return_value=(b"", mock_output.encode()))

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        audio_path = str(tmp_path / "test.mp3")
        regions = await _detect_silence_boundaries(audio_path)

    # Should detect 2 separate pause regions (far apart → no merge)
    assert len(regions) == 2
    assert regions[0] == (5.2, 5.8)
    assert regions[1] == (12.5, 13.1)


@pytest.mark.asyncio
async def test_detect_silence_no_pauses(tmp_path):
    """Test silence detection handles audio with no pauses"""

    mock_output = "No silence detected\n"

    mock_process = AsyncMock()
    mock_process.communicate = AsyncMock(return_value=(b"", mock_output.encode()))

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        audio_path = str(tmp_path / "test.mp3")
        regions = await _detect_silence_boundaries(audio_path)

    assert len(regions) == 0


@pytest.mark.asyncio
async def test_detect_silence_merges_nearby(tmp_path):
    """Nearby silences (breathing artifacts inside a long pause) are merged."""

    # Two silence chunks separated by only 0.4 s (< default merge_gap=1.0)
    mock_output = """
[silencedetect @ 0x1] silence_start: 5.0
[silencedetect @ 0x1] silence_end: 5.8 | silence_duration: 0.8
[silencedetect @ 0x1] silence_start: 6.2
[silencedetect @ 0x1] silence_end: 7.0 | silence_duration: 0.8
    """.strip()

    mock_process = AsyncMock()
    mock_process.communicate = AsyncMock(return_value=(b"", mock_output.encode()))

    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        regions = await _detect_silence_boundaries(
            str(tmp_path / "test.mp3"), merge_gap=1.0
        )

    # Should merge into a single region spanning both silences
    assert len(regions) == 1
    assert regions[0] == (5.0, 7.0)


@pytest.mark.asyncio
async def test_split_audio_at_pauses(tmp_path):
    """Test audio splitting at detected pause regions (speech-only extraction)."""

    section_dir = tmp_path / "section_0"
    section_dir.mkdir()
    section_audio = section_dir / "section_audio.mp3"
    section_audio.write_text("mock audio")

    narration_segments = [
        {"text": "First segment content."},
        {"text": "Second segment content."},
        {"text": "Third segment content."},
    ]
    cleaned_texts = [
        "First segment content.",
        "Second segment content.",
        "Third segment content.",
    ]
    # Two pause regions (start, end) for 3 segments
    pause_regions = [(5.0, 6.0), (12.0, 13.6)]
    total_duration = 20.0

    # Mock ffmpeg extract + get_audio_duration
    mock_process = AsyncMock()
    mock_process.communicate = AsyncMock(return_value=(b"", b""))
    mock_process.returncode = 0

    async def mock_duration(path):
        if "seg_0" in path:
            return 5.0  # [0, 5.0]
        elif "seg_1" in path:
            return 6.0  # [6.0, 12.0]
        else:
            return 6.4  # [13.6, 20.0]

    with patch("asyncio.create_subprocess_exec", return_value=mock_process), \
         patch("app.services.pipeline.assembly.sections.get_audio_duration", side_effect=mock_duration), \
         patch("app.services.pipeline.assembly.sections._trim_segment_edges", new_callable=AsyncMock):

        segments = await _split_audio_at_pauses(
            section_audio_path=str(section_audio),
            pause_regions=pause_regions,
            narration_segments=narration_segments,
            cleaned_texts=cleaned_texts,
            section_dir=section_dir,
            total_duration=total_duration,
        )

    assert len(segments) == 3

    # Segment 0: before first pause
    assert segments[0]["segment_index"] == 0
    assert segments[0]["start_time"] == 0.0
    assert segments[0]["end_time"] == 5.0  # silence_start of first pause
    assert segments[0]["duration"] == 5.0

    # Segment 1: between pauses (speech only)
    assert segments[1]["segment_index"] == 1
    assert segments[1]["start_time"] == 6.0  # silence_end of first pause
    assert segments[1]["end_time"] == 12.0  # silence_start of second pause
    assert segments[1]["duration"] == 6.0

    # Segment 2: after last pause
    assert segments[2]["segment_index"] == 2
    assert segments[2]["start_time"] == 13.6  # silence_end of second pause
    assert segments[2]["end_time"] == 20.0
    assert abs(segments[2]["duration"] - 6.4) < 0.1


@pytest.mark.asyncio
async def test_split_audio_too_many_pauses(tmp_path):
    """Test handling when too many pause regions are detected."""

    section_dir = tmp_path / "section_0"
    section_dir.mkdir()
    section_audio = section_dir / "section_audio.mp3"
    section_audio.write_text("mock audio")

    narration_segments = [
        {"text": "First segment."},
        {"text": "Second segment."},
    ]
    cleaned_texts = ["First segment.", "Second segment."]
    # 3 pause regions for only 2 segments
    pause_regions = [(4.5, 5.5), (9.5, 10.5), (14.5, 15.5)]
    total_duration = 20.0

    mock_process = AsyncMock()
    mock_process.communicate = AsyncMock(return_value=(b"", b""))
    mock_process.returncode = 0

    async def mock_duration(path):
        return 5.0

    with patch("asyncio.create_subprocess_exec", return_value=mock_process), \
         patch("app.services.pipeline.assembly.sections.get_audio_duration", side_effect=mock_duration), \
         patch("app.services.pipeline.assembly.sections._trim_segment_edges", new_callable=AsyncMock):

        segments = await _split_audio_at_pauses(
            section_audio_path=str(section_audio),
            pause_regions=pause_regions,
            narration_segments=narration_segments,
            cleaned_texts=cleaned_texts,
            section_dir=section_dir,
            total_duration=total_duration,
        )

    # Should only use first N-1 regions (1 region for 2 segments)
    assert len(segments) == 2
    assert segments[0]["start_time"] == 0.0
    assert segments[0]["end_time"] == 4.5   # silence_start of first region
    assert segments[1]["start_time"] == 5.5  # silence_end of first region
    assert segments[1]["end_time"] == 20.0


@pytest.mark.asyncio
async def test_generate_audio_whole_section_with_pauses(tmp_path):
    """Test whole-section audio generation uses energy-valley detection."""

    section_dir = tmp_path / "section_0"
    section_dir.mkdir()

    narration_segments = [
        {"text": "First segment with some content."},
        {"text": "Second segment with more content."},
        {"text": "Third segment with final content."},
    ]

    mock_tts = MagicMock()

    async def mock_generate_speech(text, output_path, voice):
        assert "......" in text
        Path(output_path).write_text("mock audio with pauses")
        return 15.0

    mock_tts.generate_speech = AsyncMock(side_effect=mock_generate_speech)

    # Energy-valley returns 2 regions for 3 segments
    mock_valleys = [(5.0, 6.0), (10.0, 11.0)]

    async def mock_split(section_audio_path, pause_regions, **kwargs):
        assert len(pause_regions) == 2
        return [
            {
                "segment_index": 0,
                "text": "First segment with some content.",
                "audio_path": str(section_dir / "seg_0" / "audio.mp3"),
                "duration": 5.5,
                "start_time": 0.0,
                "end_time": 5.5,
                "seg_dir": str(section_dir / "seg_0"),
            },
            {
                "segment_index": 1,
                "text": "Second segment with more content.",
                "audio_path": str(section_dir / "seg_1" / "audio.mp3"),
                "duration": 5.0,
                "start_time": 5.5,
                "end_time": 10.5,
                "seg_dir": str(section_dir / "seg_1"),
            },
            {
                "segment_index": 2,
                "text": "Third segment with final content.",
                "audio_path": str(section_dir / "seg_2" / "audio.mp3"),
                "duration": 4.5,
                "start_time": 10.5,
                "end_time": 15.0,
                "seg_dir": str(section_dir / "seg_2"),
            },
        ]

    with patch(
        "app.services.pipeline.assembly.sections._find_energy_valleys",
        return_value=mock_valleys,
    ), patch(
        "app.services.pipeline.assembly.sections._split_audio_at_pauses",
        side_effect=mock_split,
    ), patch(
        "app.services.pipeline.assembly.sections.get_audio_duration",
        return_value=15.0,
    ):
        segments, total_duration = await _generate_audio_whole_section(
            tts_engine=mock_tts,
            narration_segments=narration_segments,
            section_dir=section_dir,
            section_index=0,
            voice="Charon",
        )

    assert len(segments) == 3
    assert total_duration == 15.0
    assert segments[0]["duration"] == 5.5
    assert segments[1]["duration"] == 5.0
    assert segments[2]["duration"] == 4.5
    mock_tts.generate_speech.assert_called_once()


@pytest.mark.asyncio
async def test_generate_audio_whole_section_fallback_to_proportional(tmp_path):
    """Proportional fallback when energy-valley fails (e.g. corrupt audio)."""

    section_dir = tmp_path / "section_0"
    section_dir.mkdir()

    narration_segments = [
        {"text": "First segment."},
        {"text": "Second segment."},
        {"text": "Third segment."},
    ]

    mock_tts = AsyncMock()
    mock_tts.generate_speech = AsyncMock(return_value=15.0)

    # Energy-valley returns too few regions (simulate corrupt audio)
    mock_valleys = [(7.0, 8.0)]  # Only 1 for 3 segments (need 2)

    with patch(
        "app.services.pipeline.assembly.sections._find_energy_valleys",
        return_value=mock_valleys,
    ), patch(
        "app.services.pipeline.assembly.sections.get_audio_duration",
        return_value=15.0,
    ):
        segments, total_duration = await _generate_audio_whole_section(
            tts_engine=mock_tts,
            narration_segments=narration_segments,
            section_dir=section_dir,
            section_index=0,
            voice="Charon",
        )

    assert len(segments) == 3
    assert abs(total_duration - 15.0) < 0.1
    assert all(
        s["audio_path"] == str(section_dir / "section_audio.mp3")
        for s in segments
    )
    total_seg_duration = sum(s["duration"] for s in segments)
    assert abs(total_seg_duration - 15.0) < 0.1


# ---------------------------------------------------------------------------
# Energy-valley detection unit tests
# ---------------------------------------------------------------------------


def _make_pcm(segments: list[tuple[float, float]], sample_rate: int = 16000) -> bytes:
    """Build synthetic 16-bit PCM with speech (loud) and pause (quiet) segments.

    *segments* is a list of ``(duration_sec, amplitude)`` pairs.
    """
    samples: list[int] = []
    for dur, amp in segments:
        n = int(sample_rate * dur)
        samples.extend([int(amp)] * n)
    return struct.pack(f"<{len(samples)}h", *samples)


@pytest.mark.asyncio
async def test_energy_valleys_synthetic():
    """Energy-valley detection finds pauses in synthetic audio."""
    # [speech 3s @ 10000] [pause 2s @ 200] [speech 3s @ 10000] [pause 2s @ 200] [speech 3s @ 10000]
    pcm = _make_pcm([
        (3.0, 10000), (2.0, 200), (3.0, 10000), (2.0, 200), (3.0, 10000),
    ])

    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(pcm, b""))

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        valleys = await _find_energy_valleys("fake.mp3", num_valleys=2)

    assert len(valleys) == 2
    # First valley should be around 3.0-5.0 s
    assert 2.5 < valleys[0][0] < 3.5
    assert 4.5 < valleys[0][1] < 5.5
    # Second valley around 8.0-10.0 s
    assert 7.5 < valleys[1][0] < 8.5
    assert 9.5 < valleys[1][1] < 10.5


@pytest.mark.asyncio
async def test_energy_valleys_with_breathing_artifact():
    """Energy valleys correctly identifies pauses even when a breathing artifact
    makes the pause region partially louder (but still quieter than speech)."""
    # [speech 3s] [silence 0.8s] [breath 0.4s @ 3000] [silence 0.8s] [speech 3s]
    pcm = _make_pcm([
        (3.0, 10000),
        (0.8, 200), (0.4, 3000), (0.8, 200),  # breathy pause
        (3.0, 10000),
    ])

    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(pcm, b""))

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        valleys = await _find_energy_valleys("fake.mp3", num_valleys=1)

    # Should still find 1 valley in the pause region (even with the breath)
    assert len(valleys) == 1
    assert 2.5 < valleys[0][0] < 3.5
    assert 4.5 < valleys[0][1] < 5.5


@pytest.mark.asyncio
async def test_energy_valleys_zero_requested():
    """Requesting 0 valleys returns empty list."""
    result = await _find_energy_valleys("fake.mp3", num_valleys=0)
    assert result == []


@pytest.mark.asyncio
async def test_energy_envelope_extraction():
    """_extract_energy_envelope returns correct length and values."""
    # 1 second of loud + 1 second of quiet
    pcm = _make_pcm([(1.0, 10000), (1.0, 200)])

    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(pcm, b""))

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        energy, ws = await _extract_energy_envelope("fake.mp3", window_sec=0.05, smooth_sec=0.1)

    # 2 seconds / 0.05 window = 40 windows
    assert len(energy) == 40
    assert ws == 0.05
    # First half should be much louder than second half
    first_half_avg = sum(energy[:20]) / 20
    second_half_avg = sum(energy[20:]) / 20
    assert first_half_avg > second_half_avg * 5
