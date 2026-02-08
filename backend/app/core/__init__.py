"""
Core Module - Cross-cutting concerns and shared infrastructure

This module contains foundational utilities used across the entire application.
These are not business logic, but rather infrastructure and common patterns.

Organization:
    - logging.py: Structured logging configuration and utilities
    - security.py: Security utilities (sanitization, validation)
    - files.py: File system operations and discovery
    - media.py: Media file utilities (duration, info)
    - scripts.py: Script file I/O for jobs
    - validation.py: Input validation utilities

Usage:
    from app.core import get_logger, sanitize_filename, load_script
"""

# Logging
from .logging import (
    setup_logging,
    get_logger,
    set_request_id,
    set_job_id,
    clear_context,
    LogTimer,
)

# Security
from .security import (
    sanitize_filename,
    validate_job_id,
    validate_path_within_directory,
    validate_section_index,
    secure_file_path,
)

# File operations
from .files import (
    find_file_by_id,
    ensure_directory,
    get_file_extension,
)

# Media utilities
from .media import (
    get_media_duration,
    get_video_info,
)

# Script I/O (adapter-backed)
from .scripts import (
    load_script,
    load_script_raw,
    save_script,
    get_script_metadata,
    load_section_script,
    unwrap_script,
)

# Validation
from .validation import (
    validate_file_type,
    validate_upload_path,
    validate_job_path,
    find_uploaded_file,
    job_intermediate_artifacts_available,
    job_is_final_only,
)

# Runtime guards
from .runtime import (
    REQUIRED_RENDER_TOOLS,
    parse_bool_env,
    missing_runtime_tools,
    assert_runtime_tools_available,
    assert_directory_writable,
    run_startup_runtime_checks,
)

# Constants
from .constants import (
    LANGUAGE_NAMES,
    get_language_name,
)

# Voice catalog
from .voice_catalog import (
    TTS_VOICES_BY_LANGUAGE,
    TRANSLATION_DEFAULT_VOICE_BY_LANGUAGE,
    get_tts_available_languages,
    get_tts_available_voices_flat,
    get_tts_default_voice_for_language,
    get_tts_voices_for_language,
    get_translation_default_voice,
    get_translation_languages,
)

# Video info persistence
from .video_info import (
    VideoInfo,
    VideoChapter,
    save_video_info,
    load_video_info,
    video_info_exists,
    list_all_videos,
    create_video_info_from_result,
    ErrorInfo,
    save_error_info,
    load_error_info,
    list_all_failures,
)

__all__ = [
    # Logging
    "setup_logging",
    "get_logger",
    "set_request_id",
    "set_job_id",
    "clear_context",
    "LogTimer",
    # Security
    "sanitize_filename",
    "validate_job_id",
    "validate_path_within_directory",
    "validate_section_index",
    "secure_file_path",
    # Files
    "find_file_by_id",
    "ensure_directory",
    "get_file_extension",
    # Media
    "get_media_duration",
    "get_video_info",
    # Scripts
    "load_script",
    "load_script_raw",
    "save_script",
    "get_script_metadata",
    "load_section_script",
    "unwrap_script",
    # Validation
    "validate_file_type",
    "validate_upload_path",
    "validate_job_path",
    "find_uploaded_file",
    "job_intermediate_artifacts_available",
    "job_is_final_only",
    # Runtime guards
    "REQUIRED_RENDER_TOOLS",
    "parse_bool_env",
    "missing_runtime_tools",
    "assert_runtime_tools_available",
    "assert_directory_writable",
    "run_startup_runtime_checks",
    # Constants
    "LANGUAGE_NAMES",
    "get_language_name",
    # Voice catalog
    "TTS_VOICES_BY_LANGUAGE",
    "TRANSLATION_DEFAULT_VOICE_BY_LANGUAGE",
    "get_tts_available_languages",
    "get_tts_available_voices_flat",
    "get_tts_default_voice_for_language",
    "get_tts_voices_for_language",
    "get_translation_default_voice",
    "get_translation_languages",
    # Video info
    "VideoInfo",
    "VideoChapter",
    "save_video_info",
    "load_video_info",
    "video_info_exists",
    "list_all_videos",
    "create_video_info_from_result",
    "ErrorInfo",
    "save_error_info",
    "load_error_info",
    "list_all_failures",
]

