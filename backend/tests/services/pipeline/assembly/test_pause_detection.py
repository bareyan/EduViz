"""
Tests for pause-based audio segmentation with Gemini TTS

Validates the timing extraction approach:
1. Insert pause markers between segments
2. Detect pauses in generated audio
3. Split audio at pause boundaries
4. Extract exact segment durations
"""

import pytest
import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.pipeline.assembly.sections import (
    _detect_silence_boundaries,
    _split_audio_at_pauses,
    _generate_audio_whole_section,
)


@pytest.mark.asyncio
async def test_detect_silence_boundaries(tmp_path):
    """Test silence detection parses ffmpeg output correctly"""
    
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
        pause_times = await _detect_silence_boundaries(audio_path)
    
    # Should detect 2 pauses at midpoints
    assert len(pause_times) == 2
    assert abs(pause_times[0] - 5.5) < 0.1  # (5.2 + 5.8) / 2
    assert abs(pause_times[1] - 12.8) < 0.1  # (12.5 + 13.1) / 2


@pytest.mark.asyncio
async def test_detect_silence_no_pauses(tmp_path):
    """Test silence detection handles audio with no pauses"""
    
    mock_output = "No silence detected\n"
    
    mock_process = AsyncMock()
    mock_process.communicate = AsyncMock(return_value=(b"", mock_output.encode()))
    
    with patch("asyncio.create_subprocess_exec", return_value=mock_process):
        audio_path = str(tmp_path / "test.mp3")
        pause_times = await _detect_silence_boundaries(audio_path)
    
    assert len(pause_times) == 0


@pytest.mark.asyncio
async def test_split_audio_at_pauses(tmp_path):
    """Test audio splitting at detected pause boundaries"""
    
    section_dir = tmp_path / "section_0"
    section_dir.mkdir()
    section_audio = section_dir / "section_audio.mp3"
    section_audio.write_text("mock audio")
    
    narration_segments = [
        {"text": "First segment content."},
        {"text": "Second segment content."},
        {"text": "Third segment content."}
    ]
    cleaned_texts = [
        "First segment content.",
        "Second segment content.",
        "Third segment content."
    ]
    pause_times = [5.5, 12.8]  # Two pauses for 3 segments
    total_duration = 20.0
    
    # Mock ffmpeg segment extraction
    mock_process = AsyncMock()
    mock_process.communicate = AsyncMock(return_value=(b"", b""))
    
    # Mock get_audio_duration to return realistic durations
    async def mock_duration(path):
        if "seg_0" in path:
            return 5.5
        elif "seg_1" in path:
            return 7.3  # 12.8 - 5.5
        else:
            return 7.2  # 20.0 - 12.8
    
    with patch("asyncio.create_subprocess_exec", return_value=mock_process), \
         patch("app.services.pipeline.assembly.sections.get_audio_duration", side_effect=mock_duration):
        
        segments = await _split_audio_at_pauses(
            section_audio_path=str(section_audio),
            pause_times=pause_times,
            narration_segments=narration_segments,
            cleaned_texts=cleaned_texts,
            section_dir=section_dir,
            total_duration=total_duration
        )
    
    assert len(segments) == 3
    
    # Verify segment 0
    assert segments[0]["segment_index"] == 0
    assert segments[0]["start_time"] == 0.0
    assert segments[0]["end_time"] == 5.5
    assert segments[0]["duration"] == 5.5
    assert "seg_0" in segments[0]["audio_path"]
    
    # Verify segment 1
    assert segments[1]["segment_index"] == 1
    assert segments[1]["start_time"] == 5.5
    assert segments[1]["end_time"] == 12.8
    assert abs(segments[1]["duration"] - 7.3) < 0.1
    
    # Verify segment 2
    assert segments[2]["segment_index"] == 2
    assert segments[2]["start_time"] == 12.8
    assert segments[2]["end_time"] == 20.0
    assert abs(segments[2]["duration"] - 7.2) < 0.1


@pytest.mark.asyncio
async def test_split_audio_too_many_pauses(tmp_path):
    """Test handling when too many pauses are detected"""
    
    section_dir = tmp_path / "section_0"
    section_dir.mkdir()
    section_audio = section_dir / "section_audio.mp3"
    section_audio.write_text("mock audio")
    
    narration_segments = [
        {"text": "First segment."},
        {"text": "Second segment."}
    ]
    cleaned_texts = ["First segment.", "Second segment."]
    pause_times = [5.0, 10.0, 15.0]  # 3 pauses for only 2 segments
    total_duration = 20.0
    
    mock_process = AsyncMock()
    mock_process.communicate = AsyncMock(return_value=(b"", b""))
    
    async def mock_duration(path):
        return 5.0
    
    with patch("asyncio.create_subprocess_exec", return_value=mock_process), \
         patch("app.services.pipeline.assembly.sections.get_audio_duration", side_effect=mock_duration):
        
        segments = await _split_audio_at_pauses(
            section_audio_path=str(section_audio),
            pause_times=pause_times,
            narration_segments=narration_segments,
            cleaned_texts=cleaned_texts,
            section_dir=section_dir,
            total_duration=total_duration
        )
    
    # Should only use first N-1 pauses (1 pause for 2 segments)
    assert len(segments) == 2
    assert segments[0]["end_time"] == 5.0  # First pause
    assert segments[1]["start_time"] == 5.0


@pytest.mark.asyncio
async def test_generate_audio_whole_section_with_pauses(tmp_path):
    """Test whole-section audio generation with pause markers"""
    
    section_dir = tmp_path / "section_0"
    section_dir.mkdir()
    
    narration_segments = [
        {"text": "First segment with some content."},
        {"text": "Second segment with more content."},
        {"text": "Third segment with final content."}
    ]
    
    # Mock TTS engine
    mock_tts = MagicMock()
    
    async def mock_generate_speech(text, output_path, voice):
        # Verify pause markers are inserted
        assert ". . . . . . . . . ." in text
        # Create mock audio file
        Path(output_path).write_text("mock audio with pauses")
        return 15.0
    
    mock_tts.generate_speech = AsyncMock(side_effect=mock_generate_speech)
    
    # Mock pause detection - simulate detecting 2 pauses
    mock_pause_times = [5.5, 10.5]
    
    # Mock audio splitting
    async def mock_split(section_audio_path, pause_times, **kwargs):
        assert len(pause_times) == 2
        return [
            {
                "segment_index": 0,
                "text": "First segment with some content.",
                "audio_path": str(section_dir / "seg_0" / "audio.mp3"),
                "duration": 5.5,
                "start_time": 0.0,
                "end_time": 5.5,
                "seg_dir": str(section_dir / "seg_0")
            },
            {
                "segment_index": 1,
                "text": "Second segment with more content.",
                "audio_path": str(section_dir / "seg_1" / "audio.mp3"),
                "duration": 5.0,
                "start_time": 5.5,
                "end_time": 10.5,
                "seg_dir": str(section_dir / "seg_1")
            },
            {
                "segment_index": 2,
                "text": "Third segment with final content.",
                "audio_path": str(section_dir / "seg_2" / "audio.mp3"),
                "duration": 4.5,
                "start_time": 10.5,
                "end_time": 15.0,
                "seg_dir": str(section_dir / "seg_2")
            }
        ]
    
    with patch("app.services.pipeline.assembly.sections._detect_silence_boundaries", 
               return_value=mock_pause_times), \
         patch("app.services.pipeline.assembly.sections._split_audio_at_pauses", 
               side_effect=mock_split), \
         patch("app.services.pipeline.assembly.sections.get_audio_duration", 
               return_value=15.0):
        
        segments, total_duration = await _generate_audio_whole_section(
            tts_engine=mock_tts,
            narration_segments=narration_segments,
            section_dir=section_dir,
            section_index=0,
            voice="Charon"
        )
    
    # Verify results
    assert len(segments) == 3
    assert total_duration == 15.0
    
    # Verify exact timings from pause detection
    assert segments[0]["duration"] == 5.5
    assert segments[1]["duration"] == 5.0
    assert segments[2]["duration"] == 4.5
    
    # Verify TTS was called once with pause markers
    mock_tts.generate_speech.assert_called_once()


@pytest.mark.asyncio
async def test_generate_audio_whole_section_fallback_to_proportional(tmp_path):
    """Test fallback to proportional timing when pause detection fails"""
    
    section_dir = tmp_path / "section_0"
    section_dir.mkdir()
    
    narration_segments = [
        {"text": "First segment."},
        {"text": "Second segment."},
        {"text": "Third segment."}
    ]
    
    mock_tts = AsyncMock()
    mock_tts.generate_speech = AsyncMock(return_value=15.0)
    
    # Mock pause detection finding too few pauses (only 1 for 3 segments)
    mock_pause_times = [7.5]
    
    with patch("app.services.pipeline.assembly.sections._detect_silence_boundaries", 
               return_value=mock_pause_times), \
         patch("app.services.pipeline.assembly.sections.get_audio_duration", 
               return_value=15.0):
        
        segments, total_duration = await _generate_audio_whole_section(
            tts_engine=mock_tts,
            narration_segments=narration_segments,
            section_dir=section_dir,
            section_index=0,
            voice="Charon"
        )
    
    # Should fall back to proportional distribution
    assert len(segments) == 3
    assert abs(total_duration - 15.0) < 0.1
    
    # All segments should point to the same audio file
    assert all(s["audio_path"] == str(section_dir / "section_audio.mp3") for s in segments)
    
    # Durations should be proportional (equal since text lengths are similar)
    total_seg_duration = sum(s["duration"] for s in segments)
    assert abs(total_seg_duration - 15.0) < 0.1
