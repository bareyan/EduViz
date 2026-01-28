"""
Tests for app.services.pipeline.assembly.ffmpeg
"""

import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from pathlib import Path
from app.services.pipeline.assembly.ffmpeg import (
    get_media_duration,
    generate_silence,
    concatenate_audio_files,
    build_retime_merge_cmd,
    build_merge_no_cut_cmd,
    concatenate_videos,
    combine_sections
)

class TestFFmpegUtils:
    """Test pure utility functions."""

    def test_build_retime_merge_cmd_equal(self):
        """Test merge command when durations match."""
        cmd = build_retime_merge_cmd("v.mp4", "a.mp3", 10.0, 10.0, "out.mp4")
        assert "-shortest" in cmd
        assert "-filter_complex" not in cmd

    def test_build_retime_merge_cmd_video_shorter(self):
        """Test merge command when video is shorter (should pad)."""
        video_dur = 5.0
        audio_dur = 10.0
        cmd = build_retime_merge_cmd("v.mp4", "a.mp3", video_dur, audio_dur, "out.mp4")
        
        # Expect tpad filter
        assert any("tpad" in arg for arg in cmd)
        # Check padding calculation: 10 - 5 = 5
        assert any("stop_duration=5.0" in arg for arg in cmd)

    def test_build_retime_merge_cmd_video_longer(self):
        """Test merge command when video is longer (should trim)."""
        video_dur = 15.0
        audio_dur = 10.0
        cmd = build_retime_merge_cmd("v.mp4", "a.mp3", video_dur, audio_dur, "out.mp4")
        
        # Expect trim via -t audio_dur
        assert "-t" in cmd
        idx = cmd.index("-t")
        assert cmd[idx+1] == "10.000"
        # Ensure no tpad
        assert not any("tpad" in arg for arg in cmd)

    def test_build_merge_no_cut_cmd_video_longer(self):
        """Test merge no-cut when video is longer (pad audio)."""
        video_dur = 15.0
        audio_dur = 10.0
        cmd = build_merge_no_cut_cmd("v.mp4", "a.mp3", video_dur, audio_dur, "out.mp4")
        
        # Expect apad filter
        assert any("apad" in arg for arg in cmd)
        assert any("whole_dur=15.0" in arg for arg in cmd)


@pytest.mark.asyncio
class TestFFmpegAsync:
    """Test async FFmpeg wrappers."""

    async def test_get_media_duration_success(self):
        mock_result = MagicMock()
        mock_result.stdout = "42.5\n"
        
        with patch("subprocess.run", return_value=mock_result) as mock_run:
            duration = await get_media_duration("test.mp4")
            assert duration == 42.5
            args = mock_run.call_args[0][0]
            assert "ffprobe" in args

    async def test_get_media_duration_failure(self):
        with patch("subprocess.run", side_effect=Exception("Failed")):
            duration = await get_media_duration("test.mp4")
            assert duration == 0.0

    async def test_generate_silence(self):
        with patch("subprocess.run") as mock_run:
            await generate_silence("silence.mp3", 5.0)
            args = mock_run.call_args[0][0]
            assert "ffmpeg" in args
            assert "-t" in args
            assert "5.0" in args

    async def test_concatenate_audio_files(self, tmp_path):
        out_file = tmp_path / "out.mp3"
        in_files = ["a.mp3", "b.mp3"]
        
        process_mock = AsyncMock()
        process_mock.returncode = 0
        process_mock.communicate.return_value = (b"", b"")
        
        # Mock file existence verify and prevent unlink
        with patch("asyncio.create_subprocess_exec", return_value=process_mock), \
             patch("pathlib.Path.exists", return_value=True), \
             patch("pathlib.Path.unlink") as mock_unlink:
            
            result = await concatenate_audio_files(in_files, str(out_file))
            assert result is True
            
            # Verify concat list was created
            concat_list = tmp_path / "concat_audio_list.txt"
            assert concat_list.exists()
            content = concat_list.read_text(encoding="utf-8")
            assert "file 'a.mp3'" in content
            assert "file 'b.mp3'" in content

    async def test_combine_sections(self, tmp_path):
        """Test orchestration of section combining."""
        videos = ["v1.mp4", "v2.mp4"]
        audios = ["a1.mp3", "a2.mp3"] # Equal length
        
        with patch("app.services.pipeline.assembly.ffmpeg.get_media_duration", side_effect=[10.0, 10.0, 10.0, 10.0]), \
             patch("subprocess.run") as mock_run, \
             patch("app.services.pipeline.assembly.ffmpeg.concatenate_videos") as mock_concat, \
             patch("pathlib.Path.exists", return_value=True):
             
             mock_run_result = MagicMock()
             mock_run_result.returncode = 0
             mock_run.return_value = mock_run_result
             
             await combine_sections(videos, audios, "final.mp4", str(tmp_path))
             
             # Should have called subprocess.run 2 times (once per section)
             assert mock_run.call_count == 2
             
             # Should have concatenated
             mock_concat.assert_called_once()
             
