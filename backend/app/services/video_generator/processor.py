"""
Video Processing Module
Handles all FFmpeg operations for combining and merging video/audio streams
Separated from orchestration logic for better testability and single responsibility
"""

from typing import List, Optional

from ...core import get_logger, LogTimer
from .ffmpeg import (
    combine_sections as ffmpeg_combine_sections,
    concatenate_videos as ffmpeg_concatenate_videos,
)

logger = get_logger(__name__, component="video_processor")


class VideoProcessor:
    """
    Handles FFmpeg-based video processing operations
    
    Responsibilities:
    - Combine video sections with audio
    - Concatenate multiple videos
    - Merge audio and video streams
    - Handle temporary file management for FFmpeg
    
    This class is stateless and can be safely shared across operations.
    """

    def __init__(self):
        """Initialize video processor"""
        logger.info("Initialized VideoProcessor")

    async def combine_sections(
        self,
        videos: List[str],
        audios: List[Optional[str]],
        output_path: str,
        sections_dir: str
    ) -> None:
        """
        Combine video sections with corresponding audio tracks
        
        Args:
            videos: List of video file paths
            audios: List of audio file paths (can contain None for silent sections)
            output_path: Path for the final combined video
            sections_dir: Directory for intermediate files
        
        Raises:
            ValueError: If videos and audios lists don't match in length
            RuntimeError: If FFmpeg operations fail
        
        Example:
            await processor.combine_sections(
                videos=["section1.mp4", "section2.mp4"],
                audios=["audio1.mp3", "audio2.mp3"],
                output_path="final.mp4",
                sections_dir="/tmp/sections"
            )
        """
        with LogTimer(logger, f"combine_sections ({len(videos)} sections)"):
            if len(videos) != len(audios):
                error_msg = f"Mismatch: {len(videos)} videos but {len(audios)} audios"
                logger.error(error_msg)
                raise ValueError(error_msg)

            logger.info("Combining sections with FFmpeg helpers", extra={
                "section_count": len(videos),
                "output_path": output_path
            })

            await ffmpeg_combine_sections(
                videos=videos,
                audios=audios,
                output_path=output_path,
                sections_dir=sections_dir
            )

    async def concatenate_videos(
        self,
        video_paths: List[str],
        output_path: str
    ) -> None:
        """
        Concatenate multiple video files into a single video
        
        Args:
            video_paths: List of video file paths to concatenate
            output_path: Path for the output video
        
        Raises:
            ValueError: If video_paths is empty
            RuntimeError: If FFmpeg concatenation fails
        """
        with LogTimer(logger, f"concatenate_videos ({len(video_paths)} videos)"):
            await ffmpeg_concatenate_videos(video_paths, output_path)


# Backward compatibility exports
async def combine_sections(videos: List[str], audios: List[Optional[str]],
                          output_path: str, sections_dir: str) -> None:
    """Backward compatibility wrapper"""
    processor = VideoProcessor()
    await processor.combine_sections(videos, audios, output_path, sections_dir)


async def concatenate_videos(video_paths: List[str], output_path: str) -> None:
    """Backward compatibility wrapper"""
    processor = VideoProcessor()
    await processor.concatenate_videos(video_paths, output_path)
