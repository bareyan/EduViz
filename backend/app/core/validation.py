"""
File validation and discovery helpers.

Provides centralized file validation, security checks, and file discovery
to keep routes thin and DRY. All functions handle validation errors with
appropriate HTTP exceptions for route layer integration.

Security Features:
    - Path traversal prevention using Path.resolve()
    - MIME type and extension validation against whitelist
    - Strict directory containment checks

Functions:
    validate_file_type: Check if file type is allowed
    validate_upload_path: Prevent path traversal in uploads
    validate_job_path: Prevent path traversal in job outputs
    find_uploaded_file: Locate uploaded file by ID
"""

import os
from pathlib import Path

from fastapi import HTTPException

from app.config import (
    UPLOAD_DIR,
    OUTPUT_DIR,
    ALLOWED_EXTENSIONS,
    ALLOWED_MIME_TYPES,
)
from app.core.security import validate_path_within_directory


def validate_file_type(filename: str, content_type: str) -> str:
    """
    Validate that a file's type is allowed for upload.
    
    Checks both file extension and MIME type against configured whitelists.
    Returns the validated, lowercase file extension for consistent handling.
    
    Args:
        filename: The uploaded filename (may contain path separators)
        content_type: MIME type from upload request (e.g., "application/pdf")
        
    Returns:
        Lowercase file extension (e.g., ".pdf")
        
    Raises:
        HTTPException: 400 if file type is not in whitelist
        
    Example:
        >>> ext = validate_file_type("document.pdf", "application/pdf")
        >>> assert ext == ".pdf"
    """
    file_ext = os.path.splitext(filename)[1].lower() if filename else ""
    if file_ext not in ALLOWED_EXTENSIONS and content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"File type {content_type} not supported. Use PDF, images, LaTeX, or text files.",
        )
    return file_ext


def validate_upload_path(file_id: str) -> Path:
    """
    Prevent directory traversal attacks in upload paths.
    
    Resolves the full path and validates that it remains within UPLOAD_DIR.
    Protects against attacks like "../../../etc/passwd".
    
    Args:
        file_id: User-provided file identifier
        
    Returns:
        Safe Path object within UPLOAD_DIR
        
    Raises:
        HTTPException: 400 if path would escape UPLOAD_DIR
        
    Example:
        >>> path = validate_upload_path("safe-id-123")
        >>> assert path.parent == UPLOAD_DIR
    """
    safe_path = UPLOAD_DIR / file_id
    if not validate_path_within_directory(safe_path, UPLOAD_DIR):
        raise HTTPException(status_code=400, detail="Invalid file path")
    return safe_path.resolve()


def validate_job_path(job_id: str) -> Path:
    """
    Prevent directory traversal attacks in job output paths.
    
    Resolves the full path and validates that it remains within OUTPUT_DIR.
    Similar to validate_upload_path but for job output directory.
    
    Args:
        job_id: User-provided job identifier
        
    Returns:
        Safe Path object within OUTPUT_DIR
        
    Raises:
        HTTPException: 400 if path would escape OUTPUT_DIR
        
    Example:
        >>> path = validate_job_path("job-456")
        >>> assert path.parent == OUTPUT_DIR
    """
    safe_path = OUTPUT_DIR / job_id
    if not validate_path_within_directory(safe_path, OUTPUT_DIR):
        raise HTTPException(status_code=400, detail="Invalid job path")
    return safe_path.resolve()


def find_uploaded_file(file_id: str) -> str:
    """
    Locate an uploaded file by trying all allowed extensions.
    
    Given a file ID without extension, searches for the file with any
    allowed extension. Useful since the extension is stripped during storage
    for flexibility (e.g., "file-123" might be "file-123.pdf").
    
    Args:
        file_id: The file identifier (without extension)
        
    Returns:
        Full path to the found file as string
        
    Raises:
        HTTPException: 404 if file not found with any allowed extension
        
    Example:
        >>> path = find_uploaded_file("file-123")
        >>> assert Path(path).exists()
        >>> assert Path(path).suffix in ALLOWED_EXTENSIONS
    """
    for ext in ALLOWED_EXTENSIONS:
        potential_path = UPLOAD_DIR / f"{file_id}{ext}"
        if potential_path.exists():
            return str(potential_path)
    raise HTTPException(status_code=404, detail="File not found")
