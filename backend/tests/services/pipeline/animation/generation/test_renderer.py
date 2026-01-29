"""
Tests for app.services.pipeline.animation.generation.renderer

Tests for Manim scene rendering, error correction, and validation utilities.
Uses mocked subprocess to avoid requiring Manim/FFmpeg.
"""

import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path


class TestGetQualitySubdir:
    """Test suite for get_quality_subdir function"""

    def test_low_quality(self):
        """Test low quality directory mapping"""
        from app.services.pipeline.animation.generation.renderer import get_quality_subdir
        
        assert get_quality_subdir("low") == "480p15"

    def test_medium_quality(self):
        """Test medium quality directory mapping"""
        from app.services.pipeline.animation.generation.renderer import get_quality_subdir
        
        assert get_quality_subdir("medium") == "720p30"

    def test_high_quality(self):
        """Test high quality directory mapping"""
        from app.services.pipeline.animation.generation.renderer import get_quality_subdir
        
        assert get_quality_subdir("high") == "1080p60"

    def test_4k_quality(self):
        """Test 4k quality directory mapping"""
        from app.services.pipeline.animation.generation.renderer import get_quality_subdir
        
        assert get_quality_subdir("4k") == "2160p60"

    def test_unknown_quality_defaults(self):
        """Test unknown quality returns default"""
        from app.services.pipeline.animation.generation.renderer import get_quality_subdir
        
        assert get_quality_subdir("unknown") == "480p15"


class TestInjectCommonImports:
    """Test suite for inject_common_imports function"""

    def test_injects_missing_random(self):
        """Test random module is injected when used but not imported"""
        from app.services.pipeline.animation.generation.renderer import inject_common_imports
        
        code = '''from manim import *

class Test(Scene):
    def construct(self):
        x = random.choice([1, 2, 3])
'''
        result = inject_common_imports(code)
        
        assert "import random" in result

    def test_injects_missing_math(self):
        """Test math module is injected when used but not imported"""
        from app.services.pipeline.animation.generation.renderer import inject_common_imports
        
        code = '''from manim import *

class Test(Scene):
    def construct(self):
        x = math.sin(0)
'''
        result = inject_common_imports(code)
        
        assert "import math" in result

    def test_does_not_duplicate_import(self):
        """Test existing imports are not duplicated"""
        from app.services.pipeline.animation.generation.renderer import inject_common_imports
        
        code = '''import random
from manim import *

class Test(Scene):
    def construct(self):
        x = random.choice([1, 2])
'''
        result = inject_common_imports(code)
        
        # Should only have one import random
        assert result.count("import random") == 1

    def test_handles_numpy_alias(self):
        """Test numpy is imported as np when used"""
        from app.services.pipeline.animation.generation.renderer import inject_common_imports
        
        code = '''from manim import *

class Test(Scene):
    def construct(self):
        arr = numpy.array([1, 2])
'''
        result = inject_common_imports(code)
        
        assert "import numpy as np" in result


class TestCleanupPartialMovieFiles:
    """Test suite for cleanup_partial_movie_files function"""

    def test_cleanup_removes_directory(self, tmp_path):
        """Test cleanup removes partial movie files directory"""
        from app.services.pipeline.animation.generation.renderer import cleanup_partial_movie_files
        
        # Create mock directory structure
        code_file = tmp_path / "scene_0.py"
        code_file.touch()
        
        video_base = tmp_path / "videos" / "scene_0" / "480p15"
        partial_dir = video_base / "partial_movie_files"
        partial_dir.mkdir(parents=True)
        
        # Create a file in partial_dir
        (partial_dir / "test.mp4").touch()
        
        cleanup_partial_movie_files(str(tmp_path), code_file, "low")
        
        assert not partial_dir.exists()

    def test_cleanup_removes_existing_videos(self, tmp_path):
        """Test cleanup removes existing mp4 files"""
        from app.services.pipeline.animation.generation.renderer import cleanup_partial_movie_files
        
        code_file = tmp_path / "scene_0.py"
        code_file.touch()
        
        video_base = tmp_path / "videos" / "scene_0" / "480p15"
        video_base.mkdir(parents=True)
        existing_video = video_base / "old_video.mp4"
        existing_video.touch()
        
        cleanup_partial_movie_files(str(tmp_path), code_file, "low")
        
        assert not existing_video.exists()

    def test_cleanup_handles_nonexistent_dir(self, tmp_path):
        """Test cleanup handles non-existent directories gracefully"""
        from app.services.pipeline.animation.generation.renderer import cleanup_partial_movie_files
        
        code_file = tmp_path / "scene_0.py"
        
        # Should not raise
        cleanup_partial_movie_files(str(tmp_path), code_file, "low")


@pytest.mark.asyncio
class TestValidateVideoFile:
    """Test suite for validate_video_file function"""

    async def test_returns_false_for_nonexistent_file(self, tmp_path):
        """Test validation fails for non-existent file"""
        from app.services.pipeline.animation.generation.renderer import validate_video_file
        
        fake_path = str(tmp_path / "nonexistent.mp4")
        
        result = await validate_video_file(fake_path)
        
        assert result is False

    async def test_returns_false_for_tiny_file(self, tmp_path):
        """Test validation fails for files smaller than 1KB"""
        from app.services.pipeline.animation.generation.renderer import validate_video_file
        
        tiny_file = tmp_path / "tiny.mp4"
        tiny_file.write_bytes(b"too small")  # Less than 1000 bytes
        
        result = await validate_video_file(str(tiny_file))
        
        assert result is False

    async def test_calls_ffprobe_for_validation(self, tmp_path):
        """Test validation uses ffprobe to check video"""
        from app.services.pipeline.animation.generation.renderer import validate_video_file
        
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
            
            result = await validate_video_file(str(video_file))
            
            # Should have been called (at least for ffprobe)
            assert mock_thread.called


@pytest.mark.asyncio
class TestRenderScene:
    """Test suite for render_scene function"""

    @pytest.fixture
    def mock_generator(self):
        """Create mock ManimGenerator"""
        gen = MagicMock()
        gen.MAX_CORRECTION_ATTEMPTS = 3
        gen.MAX_CLEAN_RETRIES = 2
        gen.correction_handler = MagicMock()
        gen.correction_handler.fix = AsyncMock()
        return gen
        
@pytest.mark.asyncio
class TestRenderFallbackScene:
    """Test suite for render_fallback_scene function"""

    async def test_creates_fallback_code(self, tmp_path):
        """Test fallback scene creates valid code file"""
        from app.services.pipeline.animation.generation.renderer import render_fallback_scene
        
        # Mock subprocess
        mock_result = MagicMock()
        mock_result.returncode = 0
        
        # Create expected output video
        video_dir = tmp_path / "videos" / "fallback_0" / "480p15"
        video_dir.mkdir(parents=True)
        (video_dir / "section_0.mp4").write_bytes(b"0" * 100)
        
        with patch("asyncio.to_thread", new_callable=AsyncMock, return_value=mock_result):
            result = await render_fallback_scene(
                section_index=0,
                output_dir=str(tmp_path),
                code_dir=tmp_path
            )
        
        # Fallback file should exist
        fallback_file = tmp_path / "fallback_0.py"
        assert fallback_file.exists()
        
        content = fallback_file.read_text()
        assert "FallbackSection0" in content
        assert "from manim import *" in content


@pytest.mark.asyncio
class TestCorrectManimCode:
    """Test suite for correct_manim_code function"""

    async def test_returns_corrected_code_on_success(self):
        """Test correct_manim_code returns fixed code"""
        from app.services.pipeline.animation.generation.renderer import correct_manim_code
        
        mock_generator = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.code = '''from manim import *

class TestScene(Scene):
    def construct(self):
        self.wait(1)
'''
        mock_generator.correction_handler.fix = AsyncMock(return_value=mock_result)
        
        result = await correct_manim_code(
            mock_generator,
            "original code",
            "error message",
            {"title": "Test"},
            attempt=0
        )
        
        assert result is not None
        assert "def construct" in result

    async def test_returns_none_on_failure(self):
        """Test correct_manim_code returns None on failure"""
        from app.services.pipeline.animation.generation.renderer import correct_manim_code
        
        mock_generator = MagicMock()
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error = "Could not fix"
        mock_generator.correction_handler.fix = AsyncMock(return_value=mock_result)
        
        result = await correct_manim_code(
            mock_generator,
            "original code",
            "error message",
            {"title": "Test"},
            attempt=0
        )
        
        assert result is None

    async def test_returns_none_on_exception(self):
        """Test correct_manim_code returns None on exception"""
        from app.services.pipeline.animation.generation.renderer import correct_manim_code
        
        mock_generator = MagicMock()
        mock_generator.correction_handler.fix = AsyncMock(side_effect=Exception("Test error"))
        
        result = await correct_manim_code(
            mock_generator,
            "original code",
            "error message",
            {"title": "Test"},
            attempt=0
        )
        
        assert result is None
