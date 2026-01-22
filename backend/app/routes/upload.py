"""
Upload and analysis routes
"""

import os
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException

from ..config import UPLOAD_DIR, ALLOWED_MIME_TYPES, ALLOWED_EXTENSIONS
from ..models import AnalysisRequest
from ..services.analyzer import MaterialAnalyzer

router = APIRouter(tags=["upload"])

# Initialize analyzer
analyzer = MaterialAnalyzer()


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a PDF, image, or text file for analysis"""
    
    # Validate file type
    file_ext = os.path.splitext(file.filename)[1].lower() if file.filename else ""
    
    if file.content_type not in ALLOWED_MIME_TYPES and file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type {file.content_type} not supported. Use PDF, images, LaTeX, or text files."
        )
    
    # Generate unique file ID
    file_id = str(uuid.uuid4())
    file_extension = os.path.splitext(file.filename)[1]
    saved_path = UPLOAD_DIR / f"{file_id}{file_extension}"
    
    # Save file
    content = await file.read()
    with open(saved_path, "wb") as f:
        f.write(content)
    
    return {
        "file_id": file_id,
        "filename": file.filename,
        "size": len(content),
        "type": file.content_type
    }


@router.delete("/file/{file_id}")
async def delete_file(file_id: str):
    """Delete an uploaded file"""
    
    for ext in ALLOWED_EXTENSIONS:
        potential_path = UPLOAD_DIR / f"{file_id}{ext}"
        if potential_path.exists():
            potential_path.unlink()
            return {"status": "deleted", "file_id": file_id}
    
    raise HTTPException(status_code=404, detail="File not found")
