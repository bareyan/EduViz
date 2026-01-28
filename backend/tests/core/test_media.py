
import pytest
from unittest.mock import MagicMock, patch
import asyncio
import json
from pathlib import Path
from app.core.media import get_media_duration, get_video_info

@pytest.mark.asyncio
async def test_get_media_duration():
    # Mock the asyncio subprocess
    mock_process = MagicMock()
    # communicate() is an async method, so it needs to return a coroutine
    async def mock_communicate():
        return (b"15.5\n", b"")
    mock_process.communicate = mock_communicate
    
    async def mock_create_subprocess(*args, **kwargs):
        return mock_process
    
    with patch("asyncio.create_subprocess_exec", side_effect=mock_create_subprocess) as mock_exec:
        duration = await get_media_duration("test.mp4")
        
        assert duration == 15.5
        mock_exec.assert_called_once()
        args = mock_exec.call_args[0]
        assert "ffprobe" in args
        assert "test.mp4" in args

@pytest.mark.asyncio
async def test_get_media_duration_failure():
    # Verify fallback on error
    with patch("asyncio.create_subprocess_exec", side_effect=Exception("FFmpeg missing")):
        duration = await get_media_duration("test.mp4")
        assert duration == 10.0

def test_get_video_info(tmp_path):
    video_path = tmp_path / "test.mp4"
    video_path.touch()
    
    mock_output = json.dumps({
        "format": {
            "duration": "120.5",
            "size": "1024000"
        }
    })
    
    mock_result = MagicMock()
    mock_result.returncode = 0
    mock_result.stdout = mock_output
    
    with patch("subprocess.run", return_value=mock_result):
        info = get_video_info(video_path)
        assert info["exists"] is True
        assert info["duration"] == 120.5
        assert info["size"] == 1024000

def test_get_video_info_missing_file(tmp_path):
    missing_path = tmp_path / "missing.mp4"
    info = get_video_info(missing_path)
    assert info["exists"] is False
