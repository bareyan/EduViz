"""
Utility functions for the backend
"""

import os
import asyncio
from pathlib import Path
from typing import Optional


async def get_media_duration(file_path: str) -> float:
    """Get duration of media file in seconds using ffprobe"""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        file_path
    ]
    
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await process.communicate()
        return float(stdout.decode().strip())
    except:
        return 10.0  # Default fallback


def find_file_by_id(file_id: str, upload_dir: Path, extensions: list) -> Optional[Path]:
    """Find an uploaded file by its ID, trying different extensions"""
    for ext in extensions:
        potential_path = upload_dir / f"{file_id}{ext}"
        if potential_path.exists():
            return potential_path
    return None


def get_video_info(video_path: Path) -> dict:
    """Get basic info about a video file"""
    import subprocess
    
    if not video_path.exists():
        return {"exists": False}
    
    try:
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            import json
            data = json.loads(result.stdout)
            return {
                "exists": True,
                "duration": float(data.get("format", {}).get("duration", 0)),
                "size": int(data.get("format", {}).get("size", 0)),
            }
    except:
        pass
    
    return {"exists": True, "duration": 0, "size": 0}
