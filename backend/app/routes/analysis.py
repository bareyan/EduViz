"""
Analysis routes
"""

import traceback
from fastapi import APIRouter, HTTPException

from ..models import AnalysisRequest
from ..services.pipeline.content_analysis import MaterialAnalyzer
from ..core import find_uploaded_file

router = APIRouter(tags=["analysis"])

# Initialize analyzer
analyzer = MaterialAnalyzer()


@router.post("/analyze")
async def analyze_material(request: AnalysisRequest):
    """Analyze uploaded material and suggest video topics"""

    # Find the uploaded file (shared helper ensures consistent behavior)
    file_path = find_uploaded_file(request.file_id)

    try:
        result = await analyzer.analyze(file_path, request.file_id)
        return result
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
