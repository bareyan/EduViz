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
    _should_use_chunked_whole_section_tts,
    _split_segments_into_contiguous_chunks,
    _normalize_segment_timings_to_total,
    _generate_audio_whole_section_chunked,
    _generate_audio_whole_section,
    _generate_audio_per_segment,
    process_segments_audio_first,
    process_single_subsection,
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


class TestChunkedWholeSectionPolicy:
    def test_chunked_whole_section_used_for_long_comprehensive_gemini(self):
        engine = MagicMock(spec=[])
        engine._whole_section_tts = True
        section = {"video_mode": "comprehensive", "duration_seconds": 120}
        segments = [{"text": "A", "estimated_duration": 60}, {"text": "B", "estimated_duration": 60}]
        assert _should_use_chunked_whole_section_tts(section, segments, engine) is True

    def test_chunked_whole_section_not_used_for_overview(self):
        engine = MagicMock(spec=[])
        engine._whole_section_tts = True
        section = {"video_mode": "overview", "duration_seconds": 180}
        segments = [{"text": "A", "estimated_duration": 90}, {"text": "B", "estimated_duration": 90}]
        assert _should_use_chunked_whole_section_tts(section, segments, engine) is False

    def test_chunked_whole_section_not_used_below_threshold(self):
        engine = MagicMock(spec=[])
        engine._whole_section_tts = True
        section = {"video_mode": "comprehensive", "duration_seconds": 119.9}
        segments = [{"text": "A", "estimated_duration": 60}, {"text": "B", "estimated_duration": 60}]
        assert _should_use_chunked_whole_section_tts(section, segments, engine) is False


class TestChunkHelpers:
    def test_split_segments_into_two_contiguous_chunks(self):
        segments = [
            {"text": "s1", "estimated_duration": 30},
            {"text": "s2", "estimated_duration": 20},
            {"text": "s3", "estimated_duration": 20},
            {"text": "s4", "estimated_duration": 30},
        ]
        chunks = _split_segments_into_contiguous_chunks(segments, chunk_count=2)
        assert len(chunks) == 2
        assert len(chunks[0]) == 2
        assert len(chunks[1]) == 2
        assert [s["text"] for s in chunks[0] + chunks[1]] == [s["text"] for s in segments]

    def test_normalize_segment_timings_to_total(self):
        segment_info = [
            {"segment_index": 0, "text": "A", "duration": 2.0},
            {"segment_index": 1, "text": "B", "duration": 3.0},
            {"segment_index": 2, "text": "C", "duration": 5.0},
        ]
        normalized = _normalize_segment_timings_to_total(segment_info, stitched_total_duration=20.0)
        assert len(normalized) == 3
        assert normalized[0]["start_time"] == pytest.approx(0.0)
        assert normalized[0]["end_time"] == pytest.approx(4.0)
        assert normalized[1]["start_time"] == pytest.approx(4.0)
        assert normalized[1]["end_time"] == pytest.approx(10.0)
        assert normalized[2]["start_time"] == pytest.approx(10.0)
        assert normalized[2]["end_time"] == pytest.approx(20.0)
        assert normalized[-1]["end_time"] == pytest.approx(20.0)


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


@pytest.mark.asyncio
class TestGenerateAudioWholeSectionChunked:
    async def test_chunked_whole_section_uses_two_tts_calls_for_long_comprehensive(self, tmp_path):
        segments = [
            {"text": "Segment 1", "estimated_duration": 30},
            {"text": "Segment 2", "estimated_duration": 30},
            {"text": "Segment 3", "estimated_duration": 30},
            {"text": "Segment 4", "estimated_duration": 30},
        ]
        mock_engine = AsyncMock()

        async def mock_whole(*args, **kwargs):
            section_dir = kwargs["section_dir"]
            chunk_segments = kwargs["narration_segments"]
            Path(section_dir).mkdir(parents=True, exist_ok=True)
            (Path(section_dir) / "section_audio.mp3").write_bytes(b"chunk audio")

            if chunk_segments[0]["text"] == "Segment 1":
                return [
                    {"segment_index": 0, "text": "Segment 1", "duration": 2.0, "start_time": 0.0, "end_time": 2.0},
                    {"segment_index": 1, "text": "Segment 2", "duration": 3.0, "start_time": 2.0, "end_time": 5.0},
                ], 5.0

            return [
                {"segment_index": 0, "text": "Segment 3", "duration": 4.0, "start_time": 0.0, "end_time": 4.0},
                {"segment_index": 1, "text": "Segment 4", "duration": 7.0, "start_time": 4.0, "end_time": 11.0},
            ], 11.0

        async def mock_concat(_paths, output_path):
            Path(output_path).write_bytes(b"stitched")
            return True

        with patch(
            "app.services.pipeline.assembly.sections._generate_audio_whole_section",
            side_effect=mock_whole,
        ) as mock_whole_call, patch(
            "app.services.pipeline.assembly.sections.concatenate_audio_files",
            side_effect=mock_concat,
        ), patch(
            "app.services.pipeline.assembly.sections.get_audio_duration",
            AsyncMock(return_value=16.0),
        ):
            info, total = await _generate_audio_whole_section_chunked(
                tts_engine=mock_engine,
                narration_segments=segments,
                section_dir=tmp_path,
                section_index=0,
                voice="Charon",
            )

        assert mock_whole_call.call_count == 2
        assert len(info) == 4
        assert [s["segment_index"] for s in info] == [0, 1, 2, 3]
        assert all(info[i]["start_time"] <= info[i + 1]["start_time"] for i in range(len(info) - 1))
        assert info[-1]["end_time"] == pytest.approx(16.0, abs=0.01)
        assert total == pytest.approx(16.0, abs=0.01)


@pytest.mark.asyncio
class TestChunkedFallbackBehavior:
    async def test_chunked_failure_falls_back_to_single_whole_section(self, tmp_path):
        section = {
            "id": "s1",
            "title": "Long Section",
            "video_mode": "comprehensive",
            "duration_seconds": 150,
            "language": "en",
        }
        narration_segments = [
            {"text": "One", "estimated_duration": 75},
            {"text": "Two", "estimated_duration": 75},
        ]

        tts_engine = MagicMock(spec=[])
        tts_engine._whole_section_tts = True

        manim_generator = MagicMock()
        manim_generator.generate_animation = AsyncMock(side_effect=Exception("stop after fallback check"))

        fallback_segment_info = [
            {
                "segment_index": 0,
                "text": "One",
                "duration": 10.0,
                "start_time": 0.0,
                "end_time": 10.0,
                "audio_path": str(tmp_path / "section_audio.mp3"),
                "seg_dir": str(tmp_path / "seg_0"),
            }
        ]

        with patch(
            "app.services.pipeline.assembly.sections._generate_audio_whole_section_chunked",
            AsyncMock(return_value=([], 0.0)),
        ) as mock_chunked, patch(
            "app.services.pipeline.assembly.sections._generate_audio_whole_section",
            AsyncMock(return_value=(fallback_segment_info, 10.0)),
        ) as mock_single:
            await process_segments_audio_first(
                manim_generator=manim_generator,
                tts_engine=tts_engine,
                section=section,
                narration_segments=narration_segments,
                section_dir=tmp_path,
                section_index=0,
                voice="Charon",
                style="clean",
                language="en",
            )

        assert mock_chunked.await_count == 1
        assert mock_single.await_count == 1

    async def test_chunked_failure_and_single_failure_preserve_empty_result(self, tmp_path):
        section = {
            "id": "s1",
            "title": "Long Section",
            "video_mode": "comprehensive",
            "duration_seconds": 150,
            "language": "en",
        }
        narration_segments = [
            {"text": "One", "estimated_duration": 75},
            {"text": "Two", "estimated_duration": 75},
        ]

        tts_engine = MagicMock(spec=[])
        tts_engine._whole_section_tts = True

        manim_generator = MagicMock()
        manim_generator.generate_animation = AsyncMock()

        with patch(
            "app.services.pipeline.assembly.sections._generate_audio_whole_section_chunked",
            AsyncMock(return_value=([], 0.0)),
        ) as mock_chunked, patch(
            "app.services.pipeline.assembly.sections._generate_audio_whole_section",
            AsyncMock(return_value=([], 0.0)),
        ) as mock_single:
            result = await process_segments_audio_first(
                manim_generator=manim_generator,
                tts_engine=tts_engine,
                section=section,
                narration_segments=narration_segments,
                section_dir=tmp_path,
                section_index=0,
                voice="Charon",
                style="clean",
                language="en",
            )

        assert mock_chunked.await_count == 1
        assert mock_single.await_count == 1
        assert result["video_path"] is None
        assert result["audio_path"] is None
        assert manim_generator.generate_animation.await_count == 0


@pytest.mark.asyncio
class TestSectionDataForwarding:
    async def test_process_segments_audio_first_forwards_section_data(self, tmp_path):
        section = {
            "id": "s1",
            "title": "Section",
            "video_mode": "comprehensive",
            "duration_seconds": 120,
            "language": "en",
            "supporting_data": [
                {
                    "type": "referenced_content",
                    "label": "Figure 3",
                    "value": {"binding_key": "figure:3", "recreate_in_video": True},
                }
            ],
            "source_pages": {"start": 2, "end": 4},
            "source_pdf_path": "/tmp/source.pdf",
        }
        narration_segments = [
            {"text": "Figure 3 shows the block stack.", "estimated_duration": 8.0}
        ]

        tts_engine = MagicMock(spec=[])
        tts_engine._whole_section_tts = True
        manim_generator = MagicMock()
        manim_generator.generate_animation = AsyncMock(side_effect=Exception("stop after payload capture"))

        segment_info = [
            {
                "segment_index": 0,
                "text": narration_segments[0]["text"],
                "duration": 8.0,
                "start_time": 0.0,
                "end_time": 8.0,
                "audio_path": str(tmp_path / "section_audio.mp3"),
                "seg_dir": str(tmp_path / "seg_0"),
            }
        ]

        with patch(
            "app.services.pipeline.assembly.sections._generate_audio_whole_section",
            AsyncMock(return_value=(segment_info, 8.0)),
        ):
            await process_segments_audio_first(
                manim_generator=manim_generator,
                tts_engine=tts_engine,
                section=section,
                narration_segments=narration_segments,
                section_dir=tmp_path,
                section_index=0,
                voice="Charon",
                style="clean",
                language="en",
            )

        payload = manim_generator.generate_animation.await_args.kwargs["section"]
        assert payload["section_data"]["supporting_data"] == section["supporting_data"]
        assert payload["section_data"]["source_pages"] == section["source_pages"]
        assert payload["section_data"]["source_pdf_path"] == section["source_pdf_path"]
        assert payload["section_data"]["reference_items"][0]["binding_key"] == "figure:3"

    async def test_process_single_subsection_adds_section_data(self, tmp_path):
        section = {
            "id": "single",
            "title": "Single Subsection",
            "language": "en",
            "supporting_data": [
                {
                    "type": "referenced_content",
                    "label": "Table 1",
                    "value": {"binding_key": "table:1", "recreate_in_video": True},
                }
            ],
        }
        tts_engine = MagicMock()
        tts_engine.generate_speech = AsyncMock(return_value=None)
        manim_generator = MagicMock()
        manim_generator.generate_animation = AsyncMock(side_effect=Exception("stop after payload capture"))

        with patch(
            "app.services.pipeline.assembly.sections.get_audio_duration",
            AsyncMock(return_value=4.0),
        ):
            await process_single_subsection(
                manim_generator=manim_generator,
                tts_engine=tts_engine,
                section=section,
                narration="Table 1 compares methods.",
                section_dir=tmp_path,
                section_index=0,
                voice="Charon",
                style="clean",
                language="en",
            )

        payload = manim_generator.generate_animation.await_args.kwargs["section"]
        assert payload["section_data"]["supporting_data"] == section["supporting_data"]
        assert payload["section_data"]["reference_items"][0]["binding_key"] == "table:1"
