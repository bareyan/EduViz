"""
Security utilities for file handling
Implements critical security measures to prevent path traversal and injection attacks
"""

import os
import re
from pathlib import Path
from typing import Optional

from .logging import get_logger

logger = get_logger(__name__, component="security")


def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to prevent path traversal and injection attacks
    
    This function removes dangerous characters and patterns that could be used
    for path traversal, null byte injection, or other file-based attacks.
    
    Removes:
    - Directory separators (/, \\)
    - Null bytes (\x00)
    - Path traversal sequences (.., .)
    - Control characters (ASCII 0-31)
    - Hidden file prefixes (leading dots)
    
    Args:
        filename: Raw filename from user input
    
    Returns:
        Sanitized filename safe for file system operations
    
    Raises:
        ValueError: If filename is empty or invalid after sanitization
    
    Example:
        >>> sanitize_filename("../../etc/passwd")
        "passwd"
        >>> sanitize_filename("test\x00.txt")
        "test.txt"
        >>> sanitize_filename("<script>.pdf")
        "script.pdf"
    
    Security Note:
        This function is CRITICAL for preventing path traversal attacks.
        Do NOT modify without security review.
    """
    original_filename = filename

    # Remove path components (handles both / and \\ separators)
    filename = os.path.basename(filename)

    # Remove null bytes (null byte injection attack)
    filename = filename.replace('\x00', '')

    # Remove leading dots (hidden files, relative paths)
    filename = filename.lstrip('.')

    # Remove control characters (ASCII 0-31) and DEL (127)
    filename = ''.join(char for char in filename if 31 < ord(char) < 127 or ord(char) > 127)

    # Remove dangerous characters for various file systems
    dangerous_chars = '<>:"|?*'
    for char in dangerous_chars:
        filename = filename.replace(char, '')

    # Normalize unicode and remove zero-width characters
    filename = filename.encode('ascii', 'ignore').decode('ascii')

    # Limit length to reasonable value (most FS limit: 255)
    filename = filename[:255]

    # Strip whitespace
    filename = filename.strip()

    # Reject filenames that are only dots (., .., ..., etc)
    if not filename or filename.replace('.', '') == '':
        logger.warning("Filename sanitization resulted in empty string", extra={
            "original": original_filename
        })
        raise ValueError("Invalid filename after sanitization")

    if filename != original_filename:
        logger.info("Filename sanitized", extra={
            "original": original_filename,
            "sanitized": filename
        })

    return filename


def validate_job_id(job_id: str) -> bool:
    """
    Validate job ID format to prevent injection attacks
    
    Job IDs must be valid UUIDs (hexadecimal with hyphens).
    This prevents path traversal and other injection attacks.
    
    Args:
        job_id: Job identifier to validate
    
    Returns:
        True if valid, False otherwise
    
    Example:
        >>> validate_job_id("123e4567-e89b-12d3-a456-426614174000")
        True
        >>> validate_job_id("../../etc/passwd")
        False
    """
    # UUID format: 8-4-4-4-12 hexadecimal digits
    pattern = r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$'
    is_valid = bool(re.match(pattern, job_id, re.IGNORECASE))

    if not is_valid:
        logger.warning("Invalid job ID format", extra={"job_id": job_id})

    return is_valid


def validate_path_within_directory(
    path: Path,
    allowed_directory: Path,
    resolve: bool = True
) -> bool:
    """
    Validate that a path is within an allowed directory
    
    CRITICAL SECURITY FUNCTION: Prevents path traversal attacks by ensuring
    resolved paths stay within the allowed directory boundary.
    
    Args:
        path: Path to validate
        allowed_directory: Directory that path must be within
        resolve: If True, resolve symlinks and relative paths
    
    Returns:
        True if path is within allowed directory, False otherwise
    
    Example:
        >>> validate_path_within_directory(
        ...     Path("/app/uploads/file.pdf"),
        ...     Path("/app/uploads")
        ... )
        True
        >>> validate_path_within_directory(
        ...     Path("/app/uploads/../etc/passwd"),
        ...     Path("/app/uploads")
        ... )
        False
    
    Security Note:
        Always use resolve=True (default) for user-provided paths.
        This resolves symlinks and relative paths that could escape the directory.
    """
    if resolve:
        try:
            path = path.resolve()
            allowed_directory = allowed_directory.resolve()
        except (OSError, RuntimeError) as e:
            logger.warning("Path resolution failed", extra={
                "path": str(path),
                "error": str(e)
            })
            return False

    try:
        # Check if path is relative to allowed directory
        # This will raise ValueError if not relative
        path.relative_to(allowed_directory)
        return True
    except ValueError:
        logger.warning("Path traversal attempt detected", extra={
            "path": str(path),
            "allowed_directory": str(allowed_directory)
        })
        return False


def validate_section_index(section_index: int, max_sections: int = 1000) -> bool:
    """
    Validate section index to prevent array access attacks
    
    Args:
        section_index: Section index to validate
        max_sections: Maximum allowed section index
    
    Returns:
        True if valid, False otherwise
    """
    is_valid = 0 <= section_index < max_sections

    if not is_valid:
        logger.warning("Invalid section index", extra={
            "section_index": section_index,
            "max_sections": max_sections
        })

    return is_valid


def secure_file_path(
    base_dir: Path,
    *path_parts: str,
    create_dirs: bool = False
) -> Optional[Path]:
    """
    Safely construct file path within base directory
    
    Combines path parts and validates the result stays within base directory.
    
    Args:
        base_dir: Base directory (security boundary)
        *path_parts: Path components to join
        create_dirs: If True, create parent directories
    
    Returns:
        Validated Path object, or None if validation fails
    
    Example:
        >>> secure_file_path(Path("/uploads"), "job123", "video.mp4")
        Path("/uploads/job123/video.mp4")
        >>> secure_file_path(Path("/uploads"), "../etc", "passwd")
        None  # Path traversal blocked
    """
    try:
        # Sanitize each component
        sanitized_parts = []
        for part in path_parts:
            # Reject any part that contains traversal attempts
            if '..' in part or '/' in part or '\\' in part:
                logger.warning("Path traversal attempt blocked", extra={
                    "base_dir": str(base_dir),
                    "suspicious_part": part
                })
                return None
            # Skip if empty or only dots
            if part and part.replace('.', '') != '':
                sanitized_parts.append(part)

        if not sanitized_parts:
            return None

        # Construct path
        path = base_dir.joinpath(*sanitized_parts)

        # Validate within base directory
        if not validate_path_within_directory(path, base_dir):
            return None

        # Create parent directories if requested
        if create_dirs:
            path.parent.mkdir(parents=True, exist_ok=True)

        return path

    except Exception as e:
        logger.error("Failed to construct secure path", extra={
            "base_dir": str(base_dir),
            "path_parts": path_parts,
            "error": str(e)
        }, exc_info=True)
        return None
