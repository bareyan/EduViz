
import pytest
from unittest.mock import AsyncMock, Mock, patch

from app.services.pipeline.animation.generation.core.renderer import (
    render_scene,
    validate_video_file,
    cleanup_output_artifacts,
    RenderingError
)

@pytest.mark.asyncio
async def test_validate_video_file_success():
    with patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.stat") as mock_stat, \
         patch("subprocess.run") as mock_run:
        
        mock_stat.return_value.st_size = 2000
        mock_run.return_value.returncode = 0
        
        assert await validate_video_file("video.mp4") is True

@pytest.mark.asyncio
async def test_validate_video_file_too_small():
    with patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.stat") as mock_stat:
        
        mock_stat.return_value.st_size = 500
        assert await validate_video_file("video.mp4") is False

@pytest.mark.asyncio
async def test_render_scene_success():
    mock_file_manager = Mock()
    mock_file_manager.get_expected_video_path.return_value = "video.mp4"
    
    with patch("subprocess.run") as mock_run, \
         patch("app.services.pipeline.animation.generation.core.renderer.validate_video_file", new_callable=AsyncMock) as mock_val:
        
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "Done"
        mock_val.return_value = True
        
        result = await render_scene(
            generator=None,
            code_file="scene.py",
            scene_name="Scene",
            output_dir="/tmp",
            section_index=1,
            file_manager=mock_file_manager
        )
        
        assert result == "video.mp4"
        mock_file_manager.cleanup_artifacts.assert_called_once()

@pytest.mark.asyncio
async def test_render_scene_manim_failure():
    mock_file_manager = Mock()
    
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = "Error"
        
        with pytest.raises(RenderingError):
            await render_scene(
                generator=None,
                code_file="scene.py",
                scene_name="Scene",
                output_dir="/tmp",
                section_index=1,
                file_manager=mock_file_manager
            )

@pytest.mark.asyncio
async def test_render_scene_video_not_found():
    mock_file_manager = Mock()
    # Returns None or validator returns False
    mock_file_manager.get_expected_video_path.return_value = None
    
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        
        with pytest.raises(RenderingError):
            await render_scene(
                generator=None,
                code_file="scene.py",
                scene_name="Scene",
                output_dir="/tmp",
                section_index=1,
                file_manager=mock_file_manager
            )
