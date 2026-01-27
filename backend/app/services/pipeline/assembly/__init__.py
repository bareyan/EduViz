"""
Video Generator Package

Orchestrates complete video generation pipeline from analysis to final output.

Modules:
    - video_generator: Main VideoGenerator orchestrator
    - processor: FFmpeg video operations
    - progress: Job progress tracking
    - orchestrator: Parallel section processing
    - sections: Individual section processing
    - ffmpeg: Low-level FFmpeg utilities
"""

from .video_generator import VideoGenerator
from .processor import VideoProcessor
from .progress import ProgressTracker, JobProgress
from .orchestrator import SectionOrchestrator
from .ffmpeg import concatenate_videos, combine_sections

__all__ = [
    'VideoGenerator',
    'VideoProcessor',
    'ProgressTracker',
    'JobProgress',
    'SectionOrchestrator',
    'concatenate_videos',
    'combine_sections',
]
