"""
Tests for app.services.pipeline.animation.generation.renderer

Tests for Manim scene rendering, error correction, and validation utilities.
Uses mocked subprocess to avoid requiring Manim/FFmpeg.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock


class TestGetQualitySubdir:
    """Test suite for get_quality_subdir function"""

    def test_low_quality(self):
        """Test low quality directory mapping"""
        from app.services.pipeline.animation.generation.core.renderer import get_quality_subdir
        
        assert get_quality_subdir("low") == "480p15"

    def test_medium_quality(self):
        """Test medium quality directory mapping"""
        from app.services.pipeline.animation.generation.core.renderer import get_quality_subdir
        
        assert get_quality_subdir("medium") == "720p30"

    def test_high_quality(self):
        """Test high quality directory mapping"""
        from app.services.pipeline.animation.generation.core.renderer import get_quality_subdir
        
        assert get_quality_subdir("high") == "1080p60"

    def test_4k_quality(self):
        """Test 4k quality directory mapping"""
        from app.services.pipeline.animation.generation.core.renderer import get_quality_subdir
        
        assert get_quality_subdir("4k") == "2160p60"

    def test_unknown_quality_defaults(self):
        """Test unknown quality returns default"""
        from app.services.pipeline.animation.generation.core.renderer import get_quality_subdir
        
        assert get_quality_subdir("unknown") == "480p15"


@pytest.mark.asyncio
class TestValidateVideoFile:
    """Test suite for validate_video_file function"""

    async def test_returns_false_for_nonexistent_file(self, tmp_path):
        """Test validation fails for non-existent file"""
        from app.services.pipeline.animation.generation.core.renderer import validate_video_file
        
        fake_path = str(tmp_path / "nonexistent.mp4")
        
        result = await validate_video_file(fake_path)
        
        assert result is False

    async def test_returns_false_for_tiny_file(self, tmp_path):
        """Test validation fails for files smaller than 1KB"""
        from app.services.pipeline.animation.generation.core.renderer import validate_video_file
        
        tiny_file = tmp_path / "tiny.mp4"
        tiny_file.write_bytes(b"too small")  # Less than 1000 bytes
        
        result = await validate_video_file(str(tiny_file))
        
        assert result is False

    async def test_calls_ffprobe_for_validation(self, tmp_path):
        """Test validation uses ffprobe to check video"""
        from app.services.pipeline.animation.generation.core.renderer import validate_video_file
        
        # Create file large enough to pass size check
        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"0" * 2000)
        
        # Mock subprocess to simulate ffprobe success
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = '{"format": {"duration": "5.0"}, "streams": [{"codec_name": "h264"}]}'
        mock_result.stderr = ""
        
        with patch("asyncio.to_thread", new_callable=AsyncMock) as mock_thread:
            mock_thread.return_value = mock_result
            
            await validate_video_file(str(video_file))
            
            # Should have been called (at least for ffprobe)
            assert mock_thread.called


@pytest.mark.asyncio
class TestRenderScene:
    """Test suite for render_scene function"""

    @pytest.fixture
    def mock_generator(self):
        """Create mock ManimGenerator"""
        gen = MagicMock()
        gen.MAX_SURGICAL_FIX_ATTEMPTS = 3
        gen.MAX_CLEAN_RETRIES = 2
        return gen

    async def test_render_scene_success(self, tmp_path, mock_generator):
        """Test successful rendering"""
        from app.services.pipeline.animation.generation.core.renderer import render_scene
        
        code_file = tmp_path / "test.py"
        code_file.touch()
        
        # Mock subprocess
        mock_result = MagicMock()
        mock_result.returncode = 0
        
        # Create expected output video
        video_dir = tmp_path / "videos" / "test" / "480p15"
        video_dir.mkdir(parents=True)
        expected_video = video_dir / "section_0.mp4"
        expected_video.write_bytes(b"0" * 2000)

        mock_file_manager = MagicMock()
        mock_file_manager.get_expected_video_path.return_value = expected_video
        
        with patch("asyncio.to_thread", new_callable=AsyncMock, return_value=mock_result), \
             patch("app.services.pipeline.animation.generation.core.renderer.validate_video_file", new_callable=AsyncMock, return_value=True):
            
            result = await render_scene(
                generator=mock_generator,
                code_file=code_file,
                scene_name="TestScene",
                output_dir=str(tmp_path),
                section_index=0,
                file_manager=mock_file_manager
            )
            
            assert result is not None
            assert "section_0.mp4" in result
