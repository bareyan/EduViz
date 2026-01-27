"""
Video generation routes
"""

import uuid
import traceback
from fastapi import APIRouter, HTTPException, BackgroundTasks

from ..config import OUTPUT_DIR
from ..models import GenerationRequest, JobResponse, ResumeInfo
from ..services.analysis import MaterialAnalyzer
from ..services.video_generator import VideoGenerator
from ..services.job_manager import get_job_manager, JobStatus
from ..core import find_uploaded_file

router = APIRouter(tags=["generation"])

# Initialize services
analyzer = MaterialAnalyzer()
video_generator = VideoGenerator(str(OUTPUT_DIR))


@router.post("/generate", response_model=JobResponse)
async def generate_videos(request: GenerationRequest, background_tasks: BackgroundTasks):
    """Start video generation job (or resume an existing one)"""

    job_manager = get_job_manager()

    # Find the uploaded file using shared helper
    file_path = find_uploaded_file(request.file_id)

    # Determine if we're resuming or creating a new job
    resume_mode = False
    if request.resume_job_id:
        existing_job = job_manager.get_job(request.resume_job_id)
        if existing_job:
            job_id = request.resume_job_id
            resume_mode = True
            job_manager.update_job(job_id, JobStatus.ANALYZING, 0, "Resuming generation...")
        else:
            job_id = str(uuid.uuid4())
            job_manager.create_job(job_id)
    else:
        job_id = str(uuid.uuid4())
        job_manager.create_job(job_id)

    # Start generation in background
    async def run_generation():
        try:
            # Set the pipeline configuration
            from ..config.models import set_active_pipeline

            set_active_pipeline(request.pipeline)
            print(f"[Generation] Using pipeline: {request.pipeline} (video_mode: {request.video_mode})")

            if resume_mode:
                job_manager.update_job(job_id, JobStatus.ANALYZING, 0, "Checking existing progress...")
            else:
                job_manager.update_job(job_id, JobStatus.ANALYZING, 0, "Re-analyzing material...")

            analysis = await analyzer.analyze(file_path, request.file_id)
            all_topics = analysis.get("suggested_topics", [])

            selected_topics = [t for t in all_topics if t.get("index") in request.selected_topics]

            if not selected_topics:
                job_manager.update_job(job_id, JobStatus.FAILED, 0, "No valid topics selected")
                return

            all_results = []
            total_topics = len(selected_topics)

            def update_progress(p, base_progress):
                stage = p.get("stage", "")
                message = p.get("message", "Processing...")
                stage_progress = p.get("progress", 0)

                if stage == "script":
                    status = JobStatus.GENERATING_SCRIPT
                elif stage == "sections":
                    status = JobStatus.CREATING_ANIMATIONS
                elif stage == "combining":
                    status = JobStatus.COMPOSING_VIDEO
                else:
                    status = JobStatus.CREATING_ANIMATIONS

                if stage == "script":
                    overall = base_progress + (stage_progress * 0.1) / total_topics
                elif stage == "sections":
                    overall = base_progress + (10 + stage_progress * 0.8) / total_topics
                elif stage == "combining":
                    overall = base_progress + (90 + stage_progress * 0.1) / total_topics
                else:
                    overall = base_progress + (stage_progress / total_topics)

                job_manager.update_job(job_id, status, overall, message)

            for topic_idx, topic in enumerate(selected_topics):
                base_progress = (topic_idx / total_topics) * 100

                job_manager.update_job(
                    job_id,
                    JobStatus.GENERATING_SCRIPT,
                    base_progress,
                    f"{'Resuming' if resume_mode else 'Generating'} {request.video_mode} video {topic_idx + 1}/{total_topics}: {topic.get('title', 'Unknown')}"
                )

                result = await video_generator.generate_video(
                    job_id=job_id,
                    material_path=file_path,
                    voice=request.voice,
                    style=request.style,
                    language=request.language,
                    video_mode=request.video_mode,
                    resume=resume_mode,
                    progress_callback=lambda p, bp=base_progress: update_progress(p, bp)
                )

                print(result)
                if result.get("status") == "completed":
                    all_results.append({
                        "video_id": job_id,
                        "title": result["script"]["title"],
                        "duration": result["total_duration"] if "total_duration" in result else sum(c.get("duration", 0) for c in result["chapters"]),
                        "chapters": result["chapters"],
                        "download_url": f"/outputs/{job_id}/final_video.mp4",
                        "thumbnail_url": None
                    })

            if all_results:
                job_manager.update_job(
                    job_id,
                    JobStatus.COMPLETED,
                    100,
                    f"Generated {len(all_results)} video(s) successfully!",
                    result=all_results
                )
            else:
                job_manager.update_job(
                    job_id,
                    JobStatus.FAILED,
                    0,
                    "No videos were generated successfully"
                )

        except Exception as e:
            traceback.print_exc()
            job_manager.update_job(job_id, JobStatus.FAILED, 0, f"Error: {str(e)}")

    background_tasks.add_task(run_generation)

    return JobResponse(
        job_id=job_id,
        status="pending" if not resume_mode else "resuming",
        progress=0.0,
        message="Resuming video generation..." if resume_mode else "Video generation started"
    )


@router.get("/job/{job_id}/resume-info", response_model=ResumeInfo)
async def get_resume_info(job_id: str):
    """Get resume information for a job"""

    job_manager = get_job_manager()
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    progress = video_generator.check_existing_progress(job_id)

    can_resume = (
        job.status in [JobStatus.FAILED, JobStatus.INTERRUPTED] and
        progress["has_script"] and
        not progress["has_final_video"]
    )

    return ResumeInfo(
        can_resume=can_resume,
        completed_sections=len(progress["completed_sections"]),
        total_sections=progress["total_sections"],
        failed_sections=[],
        last_completed_section=None
    )


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
