"""
Media utilities - Duration, video info, and media processing
"""

import asyncio
import subprocess
import json
from typing import Dict, Any
from pathlib import Path


async def get_media_duration(file_path: str) -> float:
    """Get duration of media file in seconds using ffprobe
    
    Args:
        file_path: Path to media file
        
    Returns:
        Duration in seconds, or 10.0 as default fallback
    """
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
    except Exception:
        return 10.0  # Default fallback


def get_video_info(video_path: Path) -> Dict[str, Any]:
    """Get basic info about a video file
    
    Args:
        video_path: Path to video file
        
    Returns:
        Dictionary with video information (exists, duration, size)
    """
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
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return {
                "exists": True,
                "duration": float(data.get("format", {}).get("duration", 0)),
                "size": int(data.get("format", {}).get("size", 0)),
            }
    except Exception:
        pass

    return {"exists": True, "duration": 0, "size": 0}
