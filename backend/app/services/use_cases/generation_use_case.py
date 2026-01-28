"""
GenerationUseCase - orchestrates job creation/resume and video generation.

Keeps HTTP routes thin by handling pipeline selection, job lifecycle, and
background task wiring. Pure business logic lives here; routes just translate
HTTP to request objects and schedule work.
"""

import uuid
import traceback
from typing import Callable, Optional, Dict, Any

from fastapi import HTTPException, BackgroundTasks

from app.config import OUTPUT_DIR
from app.config.models import AVAILABLE_PIPELINES
from app.models import GenerationRequest, JobResponse, ResumeInfo
from app.services.pipeline.assembly import VideoGenerator
from app.services.infrastructure.orchestration import get_job_manager, JobStatus
from app.core import find_uploaded_file


class GenerationUseCase:
    """Handle generation job lifecycle and background execution."""

    def __init__(self):
        self.job_manager = get_job_manager()

    def _validate_pipeline(self, pipeline_name: str) -> str:
        name = pipeline_name or "default"
        if name not in AVAILABLE_PIPELINES:
            raise HTTPException(status_code=400, detail=f"Unknown pipeline: {name}")
        return name

    def _select_job(self, resume_job_id: Optional[str]) -> tuple[str, bool]:
        """Create or reuse a job id; returns (job_id, resume_mode)."""
        resume_mode = False
        if resume_job_id:
            existing_job = self.job_manager.get_job(resume_job_id)
            if existing_job:
                self.job_manager.update_job(resume_job_id, JobStatus.ANALYZING, 0, "Resuming generation...")
                return resume_job_id, True
        job_id = str(uuid.uuid4())
        self.job_manager.create_job(job_id)
        return job_id, resume_mode

    def start_generation(self, request: GenerationRequest, background_tasks: BackgroundTasks) -> JobResponse:
        """Validate input, enqueue generation work, and return initial response."""
        pipeline_name = self._validate_pipeline(request.pipeline)

        # Resolve uploaded file path (raises HTTPException if missing)
        file_path = find_uploaded_file(request.file_id)

        # Instantiate video generator (pipeline-scoped)
        video_generator = VideoGenerator(str(OUTPUT_DIR), pipeline_name=pipeline_name)

        job_id, resume_mode = self._select_job(request.resume_job_id)

        def update_progress_callback(job_id: str) -> Callable[[Dict[str, Any]], None]:
            """Create a progress callback for the video generator."""
            def _update(p: Dict[str, Any]):
                stage = p.get("stage", "")
                message = p.get("message", "Processing...")
                stage_progress = p.get("progress", 0)

                if stage == "script":
                    status = JobStatus.GENERATING_SCRIPT
                    # Script generation: 0-10%
                    overall = stage_progress * 0.1
                elif stage == "sections":
                    status = JobStatus.CREATING_ANIMATIONS
                    # Section processing: 10-90%
                    overall = 10 + (stage_progress * 0.8)
                elif stage == "combining":
                    status = JobStatus.COMPOSING_VIDEO
                    # Final combination: 90-100%
                    overall = 90 + (stage_progress * 0.1)
                else:
                    status = JobStatus.CREATING_ANIMATIONS
                    overall = stage_progress

                self.job_manager.update_job(job_id, status, overall, message)

            return _update

        async def run_generation():
            try:
                print(f"[Generation] Using pipeline: {pipeline_name} (video_mode: {request.video_mode})")

                if resume_mode:
                    self.job_manager.update_job(job_id, JobStatus.ANALYZING, 0, "Checking existing progress...")
                else:
                    self.job_manager.update_job(job_id, JobStatus.ANALYZING, 0, "Analyzing material...")

                # Note: selected_topics is used for UI display but the video generator
                # processes the entire document. The selection filters what gets analyzed.
                # For now, we generate a single comprehensive video from the document.
                
                self.job_manager.update_job(
                    job_id,
                    JobStatus.GENERATING_SCRIPT,
                    0,
                    f"{'Resuming' if resume_mode else 'Generating'} {request.video_mode} video..."
                )

                result = await video_generator.generate_video(
                    job_id=job_id,
                    material_path=file_path,
                    voice=request.voice,
                    style=request.style,
                    language=request.language,
                    video_mode=request.video_mode,
                    resume=resume_mode,
                    progress_callback=update_progress_callback(job_id),
                )

                if result.get("status") == "completed":
                    script = result.get("script", {})
                    video_result = {
                        "video_id": job_id,
                        "title": script.get("title", "Educational Video"),
                        "duration": result.get("total_duration") or sum(c.get("duration", 0) for c in result.get("chapters", [])),
                        "chapters": result.get("chapters", []),
                        "download_url": f"/outputs/{job_id}/final_video.mp4",
                        "thumbnail_url": None,
                    }
                    
                    self.job_manager.update_job(
                        job_id,
                        JobStatus.COMPLETED,
                        100,
                        "Video generated successfully!",
                        result=[video_result],
                    )
                else:
                    error_msg = result.get("error", "Video generation failed")
                    self.job_manager.update_job(
                        job_id,
                        JobStatus.FAILED,
                        0,
                        error_msg,
                    )

            except Exception as e:  # noqa: BLE001
                traceback.print_exc()
                self.job_manager.update_job(job_id, JobStatus.FAILED, 0, f"Error: {str(e)}")

        background_tasks.add_task(run_generation)

        return JobResponse(
            job_id=job_id,
            status="pending" if not resume_mode else "resuming",
            progress=0.0,
            message="Resuming video generation..." if resume_mode else "Video generation started",
        )

    def get_resume_info(self, job_id: str) -> ResumeInfo:
        job = self.job_manager.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        vg = VideoGenerator(str(OUTPUT_DIR))
        progress = vg.check_existing_progress(job_id)

        can_resume = (
            job.status in [JobStatus.FAILED, JobStatus.INTERRUPTED]
            and progress["has_script"]
            and not progress["has_final_video"]
        )

        return ResumeInfo(
            can_resume=can_resume,
            completed_sections=len(progress["completed_sections"]),
            total_sections=progress["total_sections"],
            failed_sections=[],
            last_completed_section=None,
        )
