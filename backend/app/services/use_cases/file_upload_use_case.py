"""
File upload use case.

Encapsulates the complete file upload business logic:
    - Validates file type against allowed types
    - Generates unique file ID if not provided
    - Saves file to persistent storage
    - Returns file metadata

This use case is independent of HTTP and can be used from CLI, webhooks,
or other contexts by instantiating directly and calling execute().

Classes:
    FileUploadRequest: Input model for file upload requests
    FileUploadResponse: Output model for file upload responses
    FileUploadUseCase: Main use case implementation
"""

import uuid
from dataclasses import dataclass
from typing import Optional
from fastapi import UploadFile, HTTPException

from app.config import UPLOAD_DIR
from .base import UseCase
from app.core import validate_file_type


@dataclass
class FileUploadRequest:
    """
    Request object for file upload operation.
    
    Attributes:
        file: FastAPI UploadFile from form upload
        file_id: Optional pre-generated file ID (if None, UUID will be generated)
    """
    file: UploadFile
    file_id: Optional[str] = None  # If None, generates new ID


@dataclass
class FileUploadResponse:
    """
    Response object containing file upload results.
    
    Attributes:
        file_id: Unique identifier for the uploaded file
        filename: Original filename provided by user
        file_path: Full filesystem path to stored file
        size: File size in bytes
        content_type: MIME type of the file
    """
    file_id: str
    filename: str
    file_path: str
    size: int
    content_type: str


class FileUploadUseCase(UseCase[FileUploadRequest, FileUploadResponse]):
    """
    Use case for handling file uploads.
    
    Responsibilities:
        1. Validate file type against configured whitelist
        2. Generate unique file ID if not provided
        3. Create parent directories as needed
        4. Save file to disk
        5. Return complete file metadata
    
    Business Logic Notes:
        - File IDs are UUIDs by default for uniqueness
        - Extensions are preserved from original filename
        - File content is read entirely into memory (suitable for up to ~100MB)
        - Parent directories are created if they don't exist
    
    Error Handling:
        - HTTPException with 400 for invalid file type
        - HTTPException with 500 for IO errors during save
    """

    async def execute(self, request: FileUploadRequest) -> FileUploadResponse:
        """
        Execute the file upload operation.
        
        Process:
            1. Validate that the file type is allowed
            2. Generate or use provided file ID
            3. Construct target path with original extension
            4. Create upload directory if needed
            5. Write file content to disk
            6. Return metadata about the uploaded file
        
        Args:
            request: FileUploadRequest with file and optional file_id
            
        Returns:
            FileUploadResponse with file metadata
            
        Raises:
            HTTPException: 400 if file type invalid, 500 if write fails
        """

        # Step 1: Validate file type
        # This raises HTTPException if not allowed
        file_ext = validate_file_type(request.file.filename, request.file.content_type)

        # Step 2: Generate or use provided file ID
        file_id = request.file_id or str(uuid.uuid4())

        # Step 3: Construct target path with extension
        # Extensions are preserved so files can be opened correctly
        saved_path = UPLOAD_DIR / f"{file_id}{file_ext}"

        # Step 4: Ensure upload directory exists
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

        try:
            # Step 5: Save file to disk
            # Read entire content and write to target location
            content = await request.file.read()
            with open(saved_path, "wb") as f:
                f.write(content)
        except IOError as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to save file: {str(e)}"
            )

        # Step 6: Return complete metadata
        return FileUploadResponse(
            file_id=file_id,
            filename=request.file.filename,
            file_path=str(saved_path),
            size=len(content),
            content_type=request.file.content_type,
        )
