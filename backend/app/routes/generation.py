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
    from ..config.models import list_available_pipelines

    available = list_available_pipelines()
    active = "default"
    pipelines = []
    for name, pipeline in available.items():
        pipelines.append(
            {
                "name": name,
                "description": "Pipeline configuration for generation",
                "is_active": name == active,
                "models": {
                    # Frontend-compatible keys
                    "script_generation": pipeline.script_generation.model_name,
                    "visual_script_generation": pipeline.animation_choreography.model_name,
                    "manim_generation": pipeline.animation_implementation.model_name,
                    # Extended detail keys (optional for UI)
                    "analysis": pipeline.analysis.model_name,
                    "animation_refinement": pipeline.animation_refinement.model_name,
                },
            }
        )

    return {
        "pipelines": pipelines,
        "active": active,
    }
