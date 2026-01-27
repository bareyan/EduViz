"""
Unit tests for VideoProcessor
Tests FFmpeg operations without requiring actual FFmpeg installation
"""

import pytest
from unittest.mock import patch, AsyncMock
from app.services.pipeline.assembly.processor import VideoProcessor


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

    with pytest.raises(ValueError, match="No videos to combine"):
        await processor.combine_sections(
            videos=[],
            audios=[],
            output_path="/tmp/output.mp4",
            sections_dir="/tmp/sections"
        )


@pytest.mark.asyncio
@patch("app.services.video_generator.processor.ffmpeg_combine_sections", new_callable=AsyncMock)
async def test_combine_sections_delegates_to_ffmpeg(mock_combine, processor):
    """Test combine_sections delegates to ffmpeg helper."""
    videos = ["video1.mp4"]
    audios = ["audio1.mp3"]
    output_path = "/tmp/output.mp4"
    sections_dir = "/tmp/sections"

    await processor.combine_sections(videos, audios, output_path, sections_dir)

    mock_combine.assert_awaited_once_with(
        videos=videos,
        audios=audios,
        output_path=output_path,
        sections_dir=sections_dir
    )


@pytest.mark.asyncio
async def test_concatenate_videos_empty_list(processor):
    """Test concatenation with empty video list"""
    with pytest.raises(ValueError, match="No videos to concatenate"):
        await processor.concatenate_videos([], "/tmp/output.mp4")


@pytest.mark.asyncio
@patch("app.services.video_generator.processor.ffmpeg_concatenate_videos", new_callable=AsyncMock)
async def test_concatenate_videos_delegates_to_ffmpeg(mock_concat, processor):
    """Test concatenate_videos delegates to ffmpeg helper."""
    video_paths = ["video1.mp4", "video2.mp4"]
    output_path = "/tmp/final.mp4"

    await processor.concatenate_videos(video_paths, output_path)

    mock_concat.assert_awaited_once_with(video_paths, output_path)


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
