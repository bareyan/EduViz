"""
Video Processing Module
Handles all FFmpeg operations for combining and merging video/audio streams
Separated from orchestration logic for better testability and single responsibility
"""

import asyncio
from typing import List, Optional
from pathlib import Path

from ...core import get_logger, LogTimer

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

            sections_path = Path(sections_dir)
            merged_videos = []

            logger.info(f"Processing {len(videos)} video sections", extra={
                "section_count": len(videos),
                "output_path": output_path
            })

            # Step 1: Merge each video with its audio
            for i, (video_path, audio_path) in enumerate(zip(videos, audios)):
                merged_path = sections_path / f"merged_{i}.mp4"

                if merged_path.exists():
                    logger.debug(f"Section {i} already merged, skipping", extra={
                        "section_index": i,
                        "merged_path": str(merged_path)
                    })
                    merged_videos.append(str(merged_path))
                    continue

                try:
                    if audio_path:
                        await self._merge_video_audio(video_path, audio_path, str(merged_path), i)
                    else:
                        # No audio - just copy video
                        logger.warning(f"Section {i} has no audio, copying video only", extra={
                            "section_index": i
                        })
                        await self._copy_video(video_path, str(merged_path))

                    merged_videos.append(str(merged_path))
                    logger.debug(f"Merged section {i}/{len(videos)}", extra={
                        "section_index": i,
                        "total_sections": len(videos)
                    })

                except Exception as e:
                    logger.error(f"Failed to merge section {i}", extra={
                        "section_index": i,
                        "error": str(e),
                        "video_path": video_path,
                        "audio_path": audio_path
                    }, exc_info=True)
                    raise RuntimeError(f"Failed to merge section {i}: {e}") from e

            # Step 2: Concatenate all merged videos
            if merged_videos:
                logger.info(f"Concatenating {len(merged_videos)} merged sections")
                await self._concatenate_videos(merged_videos, output_path)
                logger.info(f"Successfully created final video at {output_path}")
            else:
                error_msg = "No merged videos to concatenate"
                logger.error(error_msg)
                raise ValueError(error_msg)

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
            await self._concatenate_videos(video_paths, output_path)

    async def _merge_video_audio(
        self,
        video_path: str,
        audio_path: str,
        output_path: str,
        section_index: int
    ) -> None:
        """
        Merge video and audio files using FFmpeg
        
        Uses copy codecs for fast processing without re-encoding.
        Ensures audio matches video duration with padding/truncation.
        """
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output
            "-i", video_path,  # Video input
            "-i", audio_path,  # Audio input
            "-c:v", "copy",  # Copy video codec (no re-encode)
            "-c:a", "aac",  # AAC audio codec
            "-b:a", "192k",  # Audio bitrate
            "-shortest",  # Match shortest stream duration
            "-loglevel", "error",
            output_path
        ]

        logger.debug(f"Merging video+audio for section {section_index}", extra={
            "command": " ".join(cmd),
            "video_path": video_path,
            "audio_path": audio_path,
            "output_path": output_path
        })

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_output = stderr.decode() if stderr else "Unknown error"
                logger.error(f"FFmpeg merge failed for section {section_index}", extra={
                    "return_code": process.returncode,
                    "stderr": error_output
                })
                raise RuntimeError(f"FFmpeg failed: {error_output}")

        except Exception as e:
            logger.error(f"Failed to execute FFmpeg merge for section {section_index}", extra={
                "error": str(e)
            }, exc_info=True)
            raise

    async def _copy_video(self, input_path: str, output_path: str) -> None:
        """Copy video file without audio"""
        cmd = [
            "ffmpeg",
            "-y",
            "-i", input_path,
            "-c", "copy",
            "-an",  # Remove audio
            "-loglevel", "error",
            output_path
        ]

        logger.debug("Copying video without audio", extra={
            "input": input_path,
            "output": output_path
        })

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()

        if process.returncode != 0:
            raise RuntimeError(f"Failed to copy video: {input_path}")

    async def _concatenate_videos(self, video_paths: List[str], output_path: str) -> None:
        """
        Concatenate videos using FFmpeg concat demuxer
        
        Creates a temporary concat file listing all videos, then uses
        FFmpeg's concat protocol for fast concatenation without re-encoding.
        """
        if not video_paths:
            raise ValueError("No videos to concatenate")

        logger.debug(f"Concatenating {len(video_paths)} videos", extra={
            "video_count": len(video_paths),
            "output": output_path
        })

        # Create concat file
        output_dir = Path(output_path).parent
        concat_file = output_dir / "concat_list.txt"

        with open(concat_file, "w", encoding="utf-8") as f:
            for video_path in video_paths:
                # FFmpeg concat requires absolute paths
                abs_path = Path(video_path).resolve()
                f.write(f"file '{abs_path}'\n")

        logger.debug(f"Created concat file with {len(video_paths)} entries", extra={
            "concat_file": str(concat_file)
        })

        cmd = [
            "ffmpeg",
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
            "-loglevel", "error",
            output_path
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_output = stderr.decode() if stderr else "Unknown error"
                logger.error("FFmpeg concatenation failed", extra={
                    "return_code": process.returncode,
                    "stderr": error_output,
                    "video_count": len(video_paths)
                })
                raise RuntimeError(f"FFmpeg concatenation failed: {error_output}")

            logger.debug("Successfully concatenated videos")

        except Exception:
            logger.error("Failed to concatenate videos", exc_info=True)
            raise

        finally:
            # Cleanup concat file
            if concat_file.exists():
                concat_file.unlink()
                logger.debug("Cleaned up concat file")


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
