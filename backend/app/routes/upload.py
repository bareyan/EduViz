"""
Upload routes with security hardening

Implements:
- Filename sanitization (path traversal prevention)
- File size limits
- Rate limiting ready
- Input validation

Delegates file handling to FileUploadUseCase (clean separation of concerns).
"""

import os
from fastapi import APIRouter, UploadFile, File, HTTPException

from ..services.use_cases import FileUploadUseCase, FileUploadRequest
from ..core import find_uploaded_file
from ..core import sanitize_filename, validate_job_id
from ..core import get_logger

logger = get_logger(__name__, component="upload_routes")

router = APIRouter(tags=["upload"])

# Security configuration
MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", 50 * 1024 * 1024))  # 50MB default


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Upload a PDF, image, or text file for analysis
    
    Security measures:
    - Filename sanitization (prevents path traversal)
    - File size limit (prevents DoS)
    - Content type validation (in use case)
    """
    try:
        # Security: Sanitize filename before processing
        original_filename = file.filename
        file.filename = sanitize_filename(file.filename)

        if file.filename != original_filename:
            logger.info("Filename sanitized for security", extra={
                "original": original_filename,
                "sanitized": file.filename
            })

        # Security: Check file size by reading in chunks
        size = 0
        chunks = []
        async for chunk in file.file:
            size += len(chunk)
            if size > MAX_UPLOAD_SIZE:
                logger.warning("File too large", extra={
                    "size": size,
                    "max_size": MAX_UPLOAD_SIZE,
                    "filename": file.filename
                })
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large. Maximum size: {MAX_UPLOAD_SIZE / (1024*1024):.0f}MB"
                )
            chunks.append(chunk)

        # Reconstruct file content
        content = b''.join(chunks)

        # Reset file for use case
        import io
        file.file = io.BytesIO(content)

        logger.info("File upload initiated", extra={
            "filename": file.filename,
            "size": size,
            "content_type": file.content_type
        })

        use_case = FileUploadUseCase()
        response = await use_case.execute(FileUploadRequest(file=file))

        logger.info("File upload completed", extra={
            "file_id": response.file_id,
            "filename": response.filename
        })

        return {
            "file_id": response.file_id,
            "filename": response.filename,
            "size": response.size,
            "type": response.content_type
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Upload failed", extra={
            "filename": file.filename,
            "error": str(e)
        }, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@router.delete("/file/{file_id}")
async def delete_file(file_id: str):
    """
    Delete an uploaded file
    
    Security: Validates file_id format before file operations
    """
    # Security: Validate file_id format (should be UUID)
    if not validate_job_id(file_id):
        logger.warning("Invalid file_id format in delete request", extra={
            "file_id": file_id
        })
        raise HTTPException(status_code=400, detail="Invalid file ID format")

    try:
        file_path = find_uploaded_file(file_id)
        os.remove(file_path)

        logger.info("File deleted", extra={"file_id": file_id})

        return {"status": "deleted", "file_id": file_id}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Delete failed", extra={
            "file_id": file_id,
            "error": str(e)
        }, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")
