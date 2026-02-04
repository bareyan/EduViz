"""
Core animation utilities and infrastructure
"""

from .exceptions import (
    AnimationError, ChoreographyError, ImplementationError, 
    RefinementError, RenderingError
)
from .code_helpers import clean_code, create_scene_file, extract_scene_name
from .scaffolder import ManimScaffolder
from .renderer import render_scene, validate_video_file, cleanup_output_artifacts
from .file_manager import AnimationFileManager

__all__ = [
    # Exceptions
    "AnimationError", "ChoreographyError", "ImplementationError",
    "RefinementError", "RenderingError", "AnimationError",
    # Code utilities
    "clean_code", "create_scene_file", "extract_scene_name",
    # Scaffolding
    "ManimScaffolder",
    # Rendering
    "render_scene", "validate_video_file", "cleanup_output_artifacts",
    # File Management
    "AnimationFileManager"
]
