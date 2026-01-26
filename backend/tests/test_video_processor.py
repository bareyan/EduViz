"""
Unit tests for VideoProcessor
Tests FFmpeg operations without requiring actual FFmpeg installation
"""

import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock
from app.services.video_generator.processor import VideoProcessor


@pytest.fixture
def processor():
    """Create VideoProcessor instance"""
    return VideoProcessor()


@pytest.fixture
def temp_output_dir(tmp_path):
    """Create temporary output directory"""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return output_dir


@pytest.mark.asyncio
async def test_combine_sections_validates_input_length():
    """Test that combine_sections validates videos and audios have same length"""
    processor = VideoProcessor()

    with pytest.raises(ValueError, match="Mismatch"):
        await processor.combine_sections(
            videos=["video1.mp4", "video2.mp4"],
            audios=["audio1.mp3"],  # Mismatched length
            output_path="/tmp/output.mp4",
            sections_dir="/tmp/sections"
        )


@pytest.mark.asyncio
async def test_combine_sections_raises_on_empty_videos():
    """Test that combine_sections raises error with no videos"""
    processor = VideoProcessor()

    with pytest.raises(ValueError, match="No merged videos"):
        await processor.combine_sections(
            videos=[],
            audios=[],
            output_path="/tmp/output.mp4",
            sections_dir="/tmp/sections"
        )


@pytest.mark.asyncio
@patch('asyncio.create_subprocess_exec')
async def test_merge_video_audio_success(mock_subprocess, processor, tmp_path):
    """Test successful video+audio merge"""
    # Setup mock process
    mock_process = AsyncMock()
    mock_process.returncode = 0
    mock_process.communicate = AsyncMock(return_value=(b'', b''))
    mock_subprocess.return_value = mock_process

    video_path = str(tmp_path / "video.mp4")
    audio_path = str(tmp_path / "audio.mp3")
    output_path = str(tmp_path / "merged.mp4")

    await processor._merge_video_audio(video_path, audio_path, output_path, 0)

    # Verify FFmpeg was called
    mock_subprocess.assert_called_once()
    call_args = mock_subprocess.call_args[0]
    assert call_args[0] == "ffmpeg"
    assert video_path in call_args
    assert audio_path in call_args
    assert output_path in call_args


@pytest.mark.asyncio
@patch('asyncio.create_subprocess_exec')
async def test_merge_video_audio_failure(mock_subprocess, processor, tmp_path):
    """Test video+audio merge failure handling"""
    # Setup mock process with failure
    mock_process = AsyncMock()
    mock_process.returncode = 1
    mock_process.communicate = AsyncMock(return_value=(b'', b'Error: invalid codec'))
    mock_subprocess.return_value = mock_process

    video_path = str(tmp_path / "video.mp4")
    audio_path = str(tmp_path / "audio.mp3")
    output_path = str(tmp_path / "merged.mp4")

    with pytest.raises(RuntimeError, match="FFmpeg failed"):
        await processor._merge_video_audio(video_path, audio_path, output_path, 0)


@pytest.mark.asyncio
@patch('asyncio.create_subprocess_exec')
async def test_concatenate_videos_success(mock_subprocess, processor, tmp_path):
    """Test successful video concatenation"""
    # Setup mock process
    mock_process = AsyncMock()
    mock_process.returncode = 0
    mock_process.communicate = AsyncMock(return_value=(b'', b''))
    mock_subprocess.return_value = mock_process

    video1 = str(tmp_path / "video1.mp4")
    video2 = str(tmp_path / "video2.mp4")
    output = str(tmp_path / "final.mp4")

    # Create dummy video files
    Path(video1).touch()
    Path(video2).touch()

    await processor._concatenate_videos([video1, video2], output)

    # Verify FFmpeg was called
    mock_subprocess.assert_called_once()
    call_args = mock_subprocess.call_args[0]
    assert call_args[0] == "ffmpeg"
    assert "-f" in call_args
    assert "concat" in call_args


@pytest.mark.asyncio
async def test_concatenate_videos_empty_list(processor):
    """Test concatenation with empty video list"""
    with pytest.raises(ValueError, match="No videos to concatenate"):
        await processor._concatenate_videos([], "/tmp/output.mp4")


@pytest.mark.asyncio
@patch('asyncio.create_subprocess_exec')
async def test_copy_video_success(mock_subprocess, processor, tmp_path):
    """Test successful video copy without audio"""
    mock_process = AsyncMock()
    mock_process.returncode = 0
    mock_process.communicate = AsyncMock(return_value=(b'', b''))
    mock_subprocess.return_value = mock_process

    input_path = str(tmp_path / "input.mp4")
    output_path = str(tmp_path / "output.mp4")

    await processor._copy_video(input_path, output_path)

    # Verify FFmpeg was called with audio removal flag
    mock_subprocess.assert_called_once()
    call_args = mock_subprocess.call_args[0]
    assert call_args[0] == "ffmpeg"
    assert "-an" in call_args  # Remove audio flag


def test_processor_initialization():
    """Test VideoProcessor initializes without errors"""
    processor = VideoProcessor()
    assert processor is not None


# Integration test (requires FFmpeg)
@pytest.mark.integration
@pytest.mark.asyncio
async def test_combine_sections_integration(tmp_path):
    """
    Integration test for combine_sections
    Requires FFmpeg to be installed
    """
    pytest.skip("Integration test - requires FFmpeg")

    VideoProcessor()

    # This would require actual video/audio files
    # Left as placeholder for future integration testing
