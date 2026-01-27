"""
Video generation routes
"""

from fastapi import APIRouter, BackgroundTasks

from ..models import GenerationRequest, JobResponse, ResumeInfo
from ..services.use_cases import GenerationUseCase

router = APIRouter(tags=["generation"])


@router.post("/generate", response_model=JobResponse)
async def generate_videos(request: GenerationRequest, background_tasks: BackgroundTasks):
    """Start video generation job (or resume an existing one)"""
    use_case = GenerationUseCase()
    return use_case.start_generation(request, background_tasks)


@router.get("/job/{job_id}/resume-info", response_model=ResumeInfo)
async def get_resume_info(job_id: str):
    """Get resume information for a job"""
    use_case = GenerationUseCase()
    return use_case.get_resume_info(job_id)


@router.get("/pipelines")
async def get_available_pipelines():
    """Get available pipeline configurations"""
    from ..config.models import AVAILABLE_PIPELINES, get_active_pipeline_name

    pipelines = []
    for name, pipeline in AVAILABLE_PIPELINES.items():
        description = ""
        if name == "default":
            description = "Balanced quality and speed - best for comprehensive videos"
        elif name == "high_quality":
            description = "Maximum quality with stronger models and deeper thinking"
        elif name == "cost_optimized":
            description = "Budget-friendly with fastest models"
        elif name == "overview":
            description = "Optimized for overview videos - 85% cheaper than default"

        pipelines.append({
            "name": name,
            "description": description,
            "is_active": name == get_active_pipeline_name(),
            "auto_selected_for": "overview" if name == "overview" else None,
            "models": {
                "script_generation": pipeline.script_generation.model_name,
                "manim_generation": pipeline.manim_generation.model_name,
                "visual_script_generation": pipeline.visual_script_generation.model_name,
            }
        })

    return {
        "pipelines": pipelines,
        "active": get_active_pipeline_name()
    }
