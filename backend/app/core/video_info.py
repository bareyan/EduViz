"""
Video information persistence.

Handles reading and writing video metadata (title, duration, chapters)
to outputs directory. This metadata persists after job cleanup.

Single Responsibility: Only manages video_info.json I/O operations.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import OUTPUT_DIR


@dataclass
class VideoChapter:
    """A chapter marker in a video."""
    title: str
    start_time: float
    duration: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "start_time": self.start_time,
            "duration": self.duration,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VideoChapter":
        return cls(
            title=data.get("title", ""),
            start_time=data.get("start_time", 0.0),
            duration=data.get("duration", 0.0),
        )


@dataclass
class VideoInfo:
    """Metadata for a completed video."""
    video_id: str
    title: str
    duration: float
    chapters: List[VideoChapter] = field(default_factory=list)
    created_at: Optional[str] = None
    thumbnail_url: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "video_id": self.video_id,
            "title": self.title,
            "duration": self.duration,
            "chapters": [ch.to_dict() for ch in self.chapters],
            "created_at": self.created_at,
            "thumbnail_url": self.thumbnail_url,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VideoInfo":
        chapters = [
            VideoChapter.from_dict(ch)
            for ch in data.get("chapters", [])
        ]
        return cls(
            video_id=data.get("video_id", ""),
            title=data.get("title", "Untitled"),
            duration=data.get("duration", 0.0),
            chapters=chapters,
            created_at=data.get("created_at"),
            thumbnail_url=data.get("thumbnail_url"),
        )


@dataclass
class ErrorInfo:
    """Metadata for a failed video generation job."""
    job_id: str
    error_message: str
    stage: str
    timestamp: str
    title: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "error_message": self.error_message,
            "stage": self.stage,
            "timestamp": self.timestamp,
            "title": self.title,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ErrorInfo":
        return cls(
            job_id=data.get("job_id", ""),
            error_message=data.get("error_message", "Unknown error"),
            stage=data.get("stage", "unknown"),
            timestamp=data.get("timestamp", ""),
            title=data.get("title"),
        )


def _video_info_path(video_id: str) -> Path:
    """Get path to video_info.json for a video."""
    return OUTPUT_DIR / video_id / "video_info.json"


def _error_info_path(job_id: str) -> Path:
    """Get path to error_info.json for a failed job."""
    return OUTPUT_DIR / job_id / "error_info.json"


def save_video_info(info: VideoInfo) -> Path:
    """
    Save video metadata to outputs directory.
    
    Args:
        info: VideoInfo object to save
        
    Returns:
        Path to saved file
    """
    path = _video_info_path(info.video_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(info.to_dict(), f, indent=2, ensure_ascii=False)
    
    return path


def load_video_info(video_id: str) -> Optional[VideoInfo]:
    """
    Load video metadata from outputs directory.
    
    Args:
        video_id: ID of the video
        
    Returns:
        VideoInfo if found, None otherwise
    """
    path = _video_info_path(video_id)
    
    if not path.exists():
        return None
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return VideoInfo.from_dict(data)
    except (json.JSONDecodeError, OSError):
        return None


def video_info_exists(video_id: str) -> bool:
    """Check if video_info.json exists for a video."""
    return _video_info_path(video_id).exists()


def list_all_videos() -> List[VideoInfo]:
    """
    List all videos with video_info.json in outputs directory.
    
    Returns:
        List of VideoInfo objects for all completed videos
    """
    videos = []
    
    if not OUTPUT_DIR.exists():
        return videos
    
    for video_dir in OUTPUT_DIR.iterdir():
        if not video_dir.is_dir():
            continue
        
        info = load_video_info(video_dir.name)
        if info:
            videos.append(info)
    
    return videos


def create_video_info_from_result(video_id: str, result: Dict[str, Any], created_at: Optional[str] = None) -> VideoInfo:
    """
    Create VideoInfo from job result data.
    
    This is a factory function to convert the job result format
    to a VideoInfo object.
    
    Args:
        video_id: ID of the video
        result: Job result dict containing title, duration, chapters
        created_at: ISO timestamp of creation
        
    Returns:
        VideoInfo object
    """
    chapters = [
        VideoChapter(
            title=ch.get("title", ""),
            start_time=ch.get("start_time", 0.0),
            duration=ch.get("duration", 0.0),
        )
        for ch in result.get("chapters", [])
    ]
    
    return VideoInfo(
        video_id=video_id,
        title=result.get("title", "Untitled"),
        duration=result.get("duration", 0.0),
        chapters=chapters,
        created_at=created_at,
        thumbnail_url=result.get("thumbnail_url"),
    )


def save_error_info(info: ErrorInfo) -> Path:
    """Save error metadata to outputs directory."""
    path = _error_info_path(info.job_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(info.to_dict(), f, indent=2, ensure_ascii=False)
    
    return path


def load_error_info(job_id: str) -> Optional[ErrorInfo]:
    """Load error metadata from outputs directory."""
    path = _error_info_path(job_id)
    
    if not path.exists():
        return None
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return ErrorInfo.from_dict(data)
    except (json.JSONDecodeError, OSError):
        return None


def list_all_failures() -> List[ErrorInfo]:
    """List all persistent failures."""
    failures = []
    
    if not OUTPUT_DIR.exists():
        return failures
    
    for job_dir in OUTPUT_DIR.iterdir():
        if not job_dir.is_dir():
            continue
        
        info = load_error_info(job_dir.name)
        if info:
            failures.append(info)
    
    return failures
