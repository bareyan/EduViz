"""
Analysis routes
"""

import os
import traceback
from fastapi import APIRouter, HTTPException

from ..config import UPLOAD_DIR, ALLOWED_EXTENSIONS
from ..models import AnalysisRequest
from ..services.analyzer import MaterialAnalyzer

router = APIRouter(tags=["analysis"])

# Initialize analyzer
analyzer = MaterialAnalyzer()


@router.post("/analyze")
async def analyze_material(request: AnalysisRequest):
    """Analyze uploaded material and suggest video topics"""
    
    # Find the uploaded file
    file_path = None
    for ext in ALLOWED_EXTENSIONS:
        potential_path = UPLOAD_DIR / f"{request.file_id}{ext}"
        if potential_path.exists():
            file_path = str(potential_path)
            break
    
    if not file_path:
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        result = await analyzer.analyze(file_path, request.file_id)
        return result
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
