"""
Animation Renderer - Handles the execution of Manim code to produce video files.

Following Google-quality standards:
- Clear separation of concerns: Rendering only, no logic for fixing code.
- Robust validation: Verifies output video integrity.
- Fail-fast: No silent fallbacks to "title-only" videos.
"""

import asyncio
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, Optional, TYPE_CHECKING

from app.core import get_logger
from ...config import QUALITY_DIR_MAP, QUALITY_FLAGS, RENDER_TIMEOUT

if TYPE_CHECKING:
    from ..generator import ManimGenerator

logger = get_logger(__name__, component="animation_renderer")

def get_quality_subdir(quality: str) -> str:
    """Gets the Manim output subdirectory for a quality setting."""
    return QUALITY_DIR_MAP.get(quality, "480p15")

def cleanup_output_artifacts(output_dir: str, code_file: Path, quality: str = "low") -> None:
    """Cleans up partial movie files and existing videos before rendering.
    
    Prevents stale fragments from contaminating the final video concatenation.
    """
    quality_subdir = get_quality_subdir(quality)
    video_base = Path(output_dir) / "videos" / code_file.stem / quality_subdir
    partial_dir = video_base / "partial_movie_files"

    if partial_dir.exists():
        logger.debug(f"Cleaning partial movie files: {partial_dir}")
        try:
            shutil.rmtree(partial_dir)
        except Exception as e:
            logger.warning(f"Failed to clean partial movie files: {e}")

    for existing_video in video_base.glob("*.mp4"):
        try:
            existing_video.unlink()
        except Exception as e:
            logger.warning(f"Failed to remove existing video {existing_video}: {e}")

async def validate_video_file(video_path: str, min_duration: float = 0.5) -> bool:
    """Validates that a video file is functional and has reasonable content.
    
    Checks file existence, minimum size, and basic integrity via FFprobe.
    """
    video_file = Path(video_path)
    if not video_file.exists():
        return False
    
    if video_file.stat().st_size < 1000:
        logger.error(f"Video file too small: {video_path}")
        return False
    
    try:
        cmd = [
            "ffprobe", "-v", "error", "-select_streams", "v:0",
            "-show_entries", "format=duration", "-of", "json",
            video_path
        ]
        result = await asyncio.to_thread(
            subprocess.run, cmd, capture_output=True, text=True, timeout=30
        )
        return result.returncode == 0
    except Exception as e:
        logger.error(f"FFprobe validation failed: {e}")
        return False

async def render_scene(
    generator: "ManimGenerator",
    code_file: Path,
    scene_name: str,
    output_dir: str,
    section_index: int,
    section: Dict[str, Any] = None,
    quality: str = "low",
    **kwargs
) -> Optional[str]:
    """Renders a Manim scene to an MP4 video file.
    
    This is a pure production stage. It executes the provided code and 
    verifies the result. It does NOT attempt to fix code errors.
    
    Args:
        generator: The orchestrating ManimGenerator.
        code_file: Path to the .py file containing the Scene.
        scene_name: Name of the Scene class to render.
        output_dir: Root directory for media outputs.
        section_index: Index for file naming.
        section: Metadata for logging context.
        quality: Manim quality setting ('low', 'medium', 'high').
        
    Returns:
        The absolute path to the rendered .mp4 file or None if it fails.
    """
    logger.info(f"Rendering section {section_index} Scene: {scene_name}")
    
    # 1. Clean environment
    cleanup_output_artifacts(output_dir, code_file, quality)
    
    # 2. Build Command (use sys.executable -m manim for cross-platform compatibility)
    quality_flag = QUALITY_FLAGS.get(quality, "-ql")
    cmd = [
        sys.executable, "-m", "manim", quality_flag, "--format=mp4",
        f"--output_file=section_{section_index}",
        f"--media_dir={output_dir}",
        str(code_file), scene_name
    ]

    # 3. Execution
    try:
        result = await asyncio.to_thread(
            subprocess.run, cmd, capture_output=True, text=True, timeout=RENDER_TIMEOUT
        )
        
        if result.returncode != 0:
            logger.error(f"Manim render process failed for section {section_index}")
            # Log the tail of the error for context
            error_output = result.stderr[-1000:]
            logger.error(f"Manim Stderr: {error_output}")
            return None

        # 4. Locate and Validate Output
        quality_subdir = get_quality_subdir(quality)
        video_dir = Path(output_dir) / "videos" / code_file.stem / quality_subdir
        
        rendered_video = None
        if video_dir.exists():
            videos = list(video_dir.glob("*.mp4"))
            if videos:
                rendered_video = str(videos[0])

        if not rendered_video:
            # Fallback search in entire output_dir
            videos = list(Path(output_dir).rglob(f"section_{section_index}.mp4"))
            if videos:
                rendered_video = str(videos[0])

        if rendered_video and await validate_video_file(rendered_video):
            logger.info(f"Successfully rendered video: {rendered_video}")
            return rendered_video
            
        logger.error(f"Video file not found or invalid after rendering section {section_index}")
        return None

    except subprocess.TimeoutExpired:
        logger.error(f"Manim rendering timed out for section {section_index} (Limit: {RENDER_TIMEOUT}s)")
        return None
    except Exception as e:
        logger.error(f"Unexpected error during render: {e}")
        return None
