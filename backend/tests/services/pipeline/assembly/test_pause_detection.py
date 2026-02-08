"""
Tests for pause-based audio segmentation with Gemini TTS

Validates the timing extraction approach:
1. Insert ``(pause)`` markers between segments
2. Find all energy-valley candidates (threshold-free)
3. Use DP to assign optimal N-1 boundaries from candidates
4. Derive segment ranges with boundary-keep for natural transitions
5. Split audio at ranges, trim residual silence
"""

import pytest
import struct
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.pipeline.assembly.sections import (
    _find_valley_candidates,
    _extract_energy_envelope,
    _estimate_boundary_positions,
    _candidate_score,
    _assign_boundaries_dp,
    _select_boundary_silences,
    _derive_segment_ranges,
    _split_audio_at_ranges,
    _trim_segment_edges,
    _generate_audio_whole_section,
    _count_words,
    PAUSE_MARKERS,
)


# ---------------------------------------------------------------------------
# Helpers
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


# ---------------------------------------------------------------------------
# Unit tests: _count_words
# ---------------------------------------------------------------------------


class TestCountWords:
    def test_simple(self):
        assert _count_words("hello world") == 2

    def test_with_punctuation(self):
        assert _count_words("Hello, world!  How's it going?") == 5

    def test_empty(self):
        assert _count_words("") == 0


# ---------------------------------------------------------------------------
# Unit tests: _estimate_boundary_positions
# ---------------------------------------------------------------------------


class TestEstimateBoundaryPositions:
    def test_single_segment_returns_empty(self):
        assert _estimate_boundary_positions(["only one segment"], 10.0) == []

    def test_two_equal_segments(self):
        positions = _estimate_boundary_positions(
            ["one two three", "four five six"], 10.0
        )
        assert len(positions) == 1
        assert abs(positions[0] - 5.0) < 0.1  # 50% of 10s

    def test_unequal_segments(self):
        # 2 words vs 6 words → boundary at 2/8 = 25% of 20s = 5.0s
        positions = _estimate_boundary_positions(
            ["two words", "this has six whole words yeah"], 20.0
        )
        assert len(positions) == 1
        assert 4.0 < positions[0] < 6.5

    def test_three_segments(self):
        positions = _estimate_boundary_positions(
            ["one two", "three four", "five six"], 12.0
        )
        assert len(positions) == 2
        assert abs(positions[0] - 4.0) < 0.5
        assert abs(positions[1] - 8.0) < 0.5


# ---------------------------------------------------------------------------
# Unit tests: _candidate_score
# ---------------------------------------------------------------------------


class TestCandidateScore:
    def test_perfect_match(self):
        """Candidate centred exactly on expected position gets high proximity."""
        score = _candidate_score(4.5, 5.5, expected=5.0,
                                 max_duration=2.0, proximity_window=5.0,
                                 estimate_weight=0.5)
        assert score > 0.4

    def test_far_from_expected(self):
        """Candidate far from expected position gets low proximity."""
        score_close = _candidate_score(4.5, 5.5, expected=5.0,
                                       max_duration=2.0, proximity_window=5.0,
                                       estimate_weight=0.5)
        score_far = _candidate_score(14.5, 15.5, expected=5.0,
                                     max_duration=2.0, proximity_window=5.0,
                                     estimate_weight=0.5)
        assert score_close > score_far

    def test_longer_silence_scores_higher(self):
        """Longer silence → higher duration component."""
        score_short = _candidate_score(5.0, 5.5, expected=5.25,
                                       max_duration=2.0, proximity_window=10.0,
                                       estimate_weight=0.0)
        score_long = _candidate_score(4.0, 6.0, expected=5.0,
                                      max_duration=2.0, proximity_window=10.0,
                                      estimate_weight=0.0)
        assert score_long > score_short


# ---------------------------------------------------------------------------
# Unit tests: _assign_boundaries_dp
# ---------------------------------------------------------------------------


class TestAssignBoundariesDP:
    def test_single_boundary(self):
        candidates = [(3.0, 4.0), (7.0, 8.0), (12.0, 13.0)]
        result = _assign_boundaries_dp(
            candidates, expected_positions=[7.5],
            max_duration=1.0, proximity_window=5.0, estimate_weight=0.5,
        )
        assert len(result) == 1
        # Should pick the one closest to 7.5 → (7.0, 8.0)
        assert result[0] == (7.0, 8.0)

    def test_two_boundaries_ordered(self):
        candidates = [(2.0, 3.0), (5.0, 6.0), (9.0, 10.0), (14.0, 15.0)]
        result = _assign_boundaries_dp(
            candidates, expected_positions=[5.5, 10.0],
            max_duration=1.0, proximity_window=5.0, estimate_weight=0.5,
        )
        assert len(result) == 2
        # Must be chronologically ordered
        assert result[0][0] < result[1][0]

    def test_raises_when_too_few_candidates(self):
        with pytest.raises(RuntimeError, match="Not enough candidates"):
            _assign_boundaries_dp(
                [(1.0, 2.0)], expected_positions=[5.0, 10.0],
                max_duration=1.0, proximity_window=5.0, estimate_weight=0.5,
            )


# ---------------------------------------------------------------------------
# Unit tests: _select_boundary_silences
# ---------------------------------------------------------------------------


class TestSelectBoundarySilences:
    def test_selects_correct_count(self):
        candidates = [(2.0, 3.0), (5.0, 6.0), (8.0, 9.0), (12.0, 13.0)]
        expected = [5.5, 9.0]
        result = _select_boundary_silences(candidates, expected, total_duration=15.0)
        assert len(result) == 2

    def test_returns_all_when_too_few(self):
        candidates = [(5.0, 6.0)]
        expected = [5.0, 10.0]
        result = _select_boundary_silences(candidates, expected, total_duration=15.0)
        assert len(result) == 1  # not enough, returns what we have

    def test_empty_expected(self):
        result = _select_boundary_silences(
            [(1.0, 2.0)], expected_positions=[], total_duration=10.0
        )
        assert result == []


# ---------------------------------------------------------------------------
# Unit tests: _derive_segment_ranges
# ---------------------------------------------------------------------------


class TestDeriveSegmentRanges:
    def test_no_boundaries(self):
        ranges = _derive_segment_ranges(10.0, [])
        assert ranges == [(0.0, 10.0)]

    def test_single_boundary(self):
        ranges = _derive_segment_ranges(10.0, [(4.5, 5.5)], boundary_keep=0.5)
        assert len(ranges) == 2
        # First range ends somewhere inside the silence with keep
        assert ranges[0][0] == 0.0
        assert 4.5 <= ranges[0][1] <= 5.0
        # Second range starts from the other side
        assert ranges[1][1] == 10.0

    def test_boundary_keep_zero(self):
        """With no boundary keep, cuts exactly at boundary edges."""
        ranges = _derive_segment_ranges(20.0, [(5.0, 6.0), (12.0, 13.0)],
                                        boundary_keep=0.0)
        assert len(ranges) == 3
        assert abs(ranges[0][1] - 5.0) < 0.01
        assert abs(ranges[1][0] - 6.0) < 0.01
        assert abs(ranges[1][1] - 12.0) < 0.01
        assert abs(ranges[2][0] - 13.0) < 0.01

    def test_two_boundaries_boundary_preserved(self):
        ranges = _derive_segment_ranges(20.0, [(5.0, 7.0), (12.0, 14.0)],
                                        boundary_keep=0.5)
        assert len(ranges) == 3
        # Each segment should have reasonable start/end
        for start, end in ranges:
            assert end > start


# ---------------------------------------------------------------------------
# Energy-valley candidate detection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_valley_candidates_synthetic():
    """Energy-valley detection finds pauses in synthetic audio."""
    # [speech 3s @ 10000] [pause 2s @ 200] [speech 3s @ 10000] [pause 2s @ 200] [speech 3s @ 10000]
    pcm = _make_pcm([
        (3.0, 10000), (2.0, 200), (3.0, 10000), (2.0, 200), (3.0, 10000),
    ])

    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(pcm, b""))

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        candidates = await _find_valley_candidates("fake.mp3")

    # Should find at least 2 valleys (the two pauses)
    assert len(candidates) >= 2
    # First valley around 3.0-5.0s
    assert 2.5 < candidates[0][0] < 3.5
    assert 4.5 < candidates[0][1] < 5.5


@pytest.mark.asyncio
async def test_valley_candidates_with_breathing_artifact():
    """Energy valleys are found even with a breathing artifact in the pause."""
    pcm = _make_pcm([
        (3.0, 10000),
        (0.8, 200), (0.4, 3000), (0.8, 200),  # breathy pause
        (3.0, 10000),
    ])

    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(pcm, b""))

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        candidates = await _find_valley_candidates("fake.mp3")

    assert len(candidates) >= 1
    # Valley should be in the pause region
    assert any(2.5 < c[0] < 4.0 for c in candidates)


@pytest.mark.asyncio
async def test_energy_envelope_extraction():
    """_extract_energy_envelope returns correct length and values."""
    pcm = _make_pcm([(1.0, 10000), (1.0, 200)])

    mock_proc = AsyncMock()
    mock_proc.communicate = AsyncMock(return_value=(pcm, b""))

    with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
        energy, ws = await _extract_energy_envelope("fake.mp3",
                                                     window_sec=0.05,
                                                     smooth_sec=0.1)

    assert len(energy) == 40  # 2s / 0.05 = 40
    assert ws == 0.05
    first_half_avg = sum(energy[:20]) / 20
    second_half_avg = sum(energy[20:]) / 20
    assert first_half_avg > second_half_avg * 5


# ---------------------------------------------------------------------------
# _split_audio_at_ranges
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_split_audio_at_ranges(tmp_path):
    """Test audio splitting at pre-computed segment ranges."""

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
    # Pre-computed ranges (as would come from _derive_segment_ranges)
    segment_ranges = [(0.0, 4.75), (5.25, 11.75), (12.25, 20.0)]

    mock_process = AsyncMock()
    mock_process.communicate = AsyncMock(return_value=(b"", b""))
    mock_process.returncode = 0

    async def mock_duration(path):
        if "seg_0" in path:
            return 4.75
        elif "seg_1" in path:
            return 6.5
        else:
            return 7.75

    with patch("asyncio.create_subprocess_exec", return_value=mock_process), \
         patch("app.services.pipeline.assembly.sections.get_audio_duration",
               side_effect=mock_duration), \
         patch("app.services.pipeline.assembly.sections._trim_segment_edges",
               new_callable=AsyncMock):

        segments = await _split_audio_at_ranges(
            section_audio_path=str(section_audio),
            segment_ranges=segment_ranges,
            narration_segments=narration_segments,
            cleaned_texts=cleaned_texts,
            section_dir=section_dir,
        )

    assert len(segments) == 3
    assert segments[0]["start_time"] == 0.0
    assert segments[0]["end_time"] == 4.75
    assert segments[0]["duration"] == 4.75
    assert segments[1]["start_time"] == 5.25
    assert segments[1]["end_time"] == 11.75
    assert segments[1]["duration"] == 6.5
    assert segments[2]["start_time"] == 12.25
    assert segments[2]["end_time"] == 20.0
    assert segments[2]["duration"] == 7.75


# ---------------------------------------------------------------------------
# Integration: _generate_audio_whole_section
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_audio_whole_section_with_dp(tmp_path):
    """Whole-section generation: (pause) markers → valley candidates → DP → ranges → split."""

    section_dir = tmp_path / "section_0"
    section_dir.mkdir()

    narration_segments = [
        {"text": "First segment with some content."},
        {"text": "Second segment with more content."},
        {"text": "Third segment with final content."},
    ]

    mock_tts = MagicMock()

    async def mock_generate_speech(text, output_path, voice):
        # Verify (pause) markers are used, not dots
        assert "(pause)" in text
        assert "......" not in text
        Path(output_path).write_text("mock audio with pauses")
        return 15.0

    mock_tts.generate_speech = AsyncMock(side_effect=mock_generate_speech)

    # Valley candidates (more than needed — DP picks the best 2 of 4)
    mock_candidates = [(3.0, 4.0), (5.0, 6.0), (9.0, 10.5), (12.0, 13.0)]

    async def mock_split(section_audio_path, segment_ranges, **kwargs):
        assert len(segment_ranges) == 3  # 3 segments
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
        "app.services.pipeline.assembly.sections._find_valley_candidates",
        return_value=mock_candidates,
    ), patch(
        "app.services.pipeline.assembly.sections._split_audio_at_ranges",
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
    """Proportional fallback when valley candidates are insufficient."""

    section_dir = tmp_path / "section_0"
    section_dir.mkdir()

    narration_segments = [
        {"text": "First segment."},
        {"text": "Second segment."},
        {"text": "Third segment."},
    ]

    mock_tts = AsyncMock()
    mock_tts.generate_speech = AsyncMock(return_value=15.0)

    # Only 1 candidate for 3 segments (need 2 boundaries) → fallback
    mock_candidates = [(7.0, 8.0)]

    with patch(
        "app.services.pipeline.assembly.sections._find_valley_candidates",
        return_value=mock_candidates,
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
    # All segments should share the full audio path (proportional fallback)
    assert all(
        s["audio_path"] == str(section_dir / "section_audio.mp3")
        for s in segments
    )
    total_seg_duration = sum(s["duration"] for s in segments)
    assert abs(total_seg_duration - 15.0) < 0.1


# ---------------------------------------------------------------------------
# End-to-end DP pipeline test (no mocking of DP functions)
# ---------------------------------------------------------------------------


class TestDPPipelineEndToEnd:
    """Full pipeline: candidates → estimate → DP → ranges → verify."""

    def test_three_segments(self):
        """Three segments with 4 candidates → should pick 2 boundaries."""
        candidates = [
            (3.0, 4.0),   # valley 1
            (5.0, 6.5),   # valley 2 (wide)
            (10.0, 11.0), # valley 3
            (14.0, 15.0), # valley 4
        ]
        texts = ["Hello world here.", "Middle segment text.", "Final words here."]
        total = 20.0

        estimated = _estimate_boundary_positions(texts, total)
        assert len(estimated) == 2

        selected = _select_boundary_silences(
            candidates, estimated, total_duration=total,
        )
        assert len(selected) == 2
        # Boundaries must be ordered
        assert selected[0][0] < selected[1][0]

        ranges = _derive_segment_ranges(total, selected, boundary_keep=0.5)
        assert len(ranges) == 3
        # Ranges should cover the full duration (approximately)
        assert ranges[0][0] == 0.0
        assert ranges[-1][1] == total
        # Each range is positive
        for start, end in ranges:
            assert end > start

    def test_two_segments_many_candidates(self):
        """Two segments with many candidates — DP picks the best one."""
        candidates = [
            (1.0, 1.5), (3.0, 4.0), (5.0, 6.0),
            (7.0, 8.0), (9.0, 10.0), (11.0, 11.5),
        ]
        texts = ["Short first.", "Longer second segment with many words to say."]
        total = 15.0

        estimated = _estimate_boundary_positions(texts, total)
        assert len(estimated) == 1

        selected = _select_boundary_silences(
            candidates, estimated, total_duration=total,
        )
        assert len(selected) == 1

        ranges = _derive_segment_ranges(total, selected)
        assert len(ranges) == 2
