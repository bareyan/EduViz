"""
Animation File Manager

Centralizes all file system operations for the animation pipeline.
Follows SRP by handling:
1. Path validation and construction
2. File writing/reading
3. Cleanup of temporary artifacts
"""

import shutil
import json
from pathlib import Path
from typing import Optional

from app.core import get_logger
from app.services.pipeline.animation.config import QUALITY_DIR_MAP

logger = get_logger(__name__, component="animation_file_manager")


class AnimationFileManager:
    """Manages file I/O and paths for animation generation."""

    def ensure_output_directory(self, output_dir: str) -> None:
        """Ensure the output directory exists."""
        Path(output_dir).mkdir(parents=True, exist_ok=True)

    def prepare_scene_file(
        self, 
        output_dir: str, 
        section_index: int, 
        code_content: str
    ) -> Path:
        """Save the Manim scene code to a file.
        
        Args:
            output_dir: Base output directory
            section_index: Section index for naming
            code_content: Complete Python code content
            
        Returns:
            Path object of the written file
        """
        self.ensure_output_directory(output_dir)
        filename = f"scene_{section_index}.py"
        file_path = Path(output_dir) / filename
        
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(code_content)
            
            logger.info(f"Code file written: {file_path} ({file_path.stat().st_size} bytes)")
            return file_path
        except IOError as e:
            logger.error(f"Failed to write scene file {file_path}: {e}")
            raise

    def prepare_choreography_plan_file(
        self,
        output_dir: str,
        plan_content: str,
    ) -> Path:
        """Persist choreography output in section directory.

        Stores JSON when parseable, otherwise wraps raw text in a JSON envelope.
        """
        self.ensure_output_directory(output_dir)
        file_path = Path(output_dir) / "choreography_plan.json"

        try:
            payload = json.loads(plan_content)
        except (TypeError, json.JSONDecodeError):
            payload = {"plan_text": str(plan_content or "")}

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            logger.info(f"Choreography plan written: {file_path}")
            return file_path
        except IOError as e:
            logger.error(f"Failed to write choreography plan file {file_path}: {e}")
            raise

    def get_quality_subdir(self, quality: str) -> str:
        """Get the Manim output subdirectory name for a quality setting."""
        return QUALITY_DIR_MAP.get(quality, "480p15")

    def get_expected_video_path(
        self, 
        output_dir: str, 
        code_file: Path, 
        quality: str, 
        section_index: int
    ) -> Optional[Path]:
        """Locate the generated video file.
        
        Checks standard Manim output locations.
        """
        # 1. Check strict structure: media/videos/{file_stem}/{quality}/{file_stem}.mp4
        quality_subdir = self.get_quality_subdir(quality)
        video_dir = Path(output_dir) / "videos" / code_file.stem / quality_subdir
        
        if video_dir.exists():
            # Usually strict naming like section_X.mp4
            strict_match = video_dir / f"section_{section_index}.mp4"
            if strict_match.exists():
                return strict_match
                
            # Fallback: look for any MP4
            videos = list(video_dir.glob("*.mp4"))
            if videos:
                return videos[0]
                
        # 2. Fallback: Search recursively in output dir
        # Be careful not to pick up partials from other runs if names collide
        candidates = list(Path(output_dir).rglob(f"section_{section_index}.mp4"))
        if candidates:
            return candidates[0]
            
        return None

    def cleanup_artifacts(self, output_dir: str, code_file: Path, quality: str) -> None:
        """Clean up partial movie files and previous renders."""
        quality_subdir = self.get_quality_subdir(quality)
        video_base = Path(output_dir) / "videos" / code_file.stem / quality_subdir
        partial_dir = video_base / "partial_movie_files"

        if partial_dir.exists():
            logger.debug(f"Cleaning partial movie files: {partial_dir}")
            try:
                shutil.rmtree(partial_dir)
            except Exception as e:
                logger.warning(f"Failed to clean partial artifacts: {e}")

        # Clean existing videos to ensure we don't return stale ones
        if video_base.exists():
            for video in video_base.glob("*.mp4"):
                try:
                    video.unlink()
                except Exception as e:
                    logger.warning(f"Failed to remove stale video {video}: {e}")
