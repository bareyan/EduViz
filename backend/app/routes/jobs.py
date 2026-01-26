"""
Job management routes.

Routes use JobRepository to abstract job data access,
enabling easier testing and potential future database migration.

Extracted helper functions handle complex logic like building section progress
to keep routes focused on HTTP handling.
"""

import shutil
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..config import OUTPUT_DIR
from ..models import JobResponse, DetailedProgress, HighQualityCompileRequest
from ..services.repositories import FileBasedJobRepository
from ..services.tts_engine import TTSEngine
from ..core import load_script, get_script_metadata
from .jobs_helpers import (
    get_stage_from_status,
    build_sections_progress,
    get_current_section_index,
)

router = APIRouter(tags=["jobs"])


@router.get("/job/{job_id}", response_model=JobResponse)
async def get_job_status(job_id: str):
    """
    Get the status of a video generation job.
    
    Args:
        job_id: Unique job identifier
        
    Returns:
        JobResponse with status, progress, and message
        
    Raises:
        HTTPException: 404 if job not found
    """
    repo = FileBasedJobRepository()
    job = repo.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Normalize progress to 0-1 range for API consistency
    normalized_progress = min(job.progress / 100.0, 1.0) if job.progress else 0.0

    return JobResponse(
        job_id=job_id,
        status=job.status,
        progress=normalized_progress,
        message=job.message,
        result=job.result
    )


@router.get("/video/{video_id}")
async def get_video(video_id: str):
    """Stream or download a generated video"""

    video_path = OUTPUT_DIR / f"{video_id}.mp4"
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video not found")

    return FileResponse(
        str(video_path),
        media_type="video/mp4",
        filename=f"{video_id}.mp4"
    )


@router.get("/voices")
async def get_available_voices(language: str = "en"):
    """Get list of available TTS voices"""

    return {
        "voices": TTSEngine.get_voices_for_language(language),
        "languages": TTSEngine.get_available_languages(),
        "current_language": language,
        "default_voice": TTSEngine.get_default_voice_for_language(language)
    }


@router.get("/jobs")
async def list_all_jobs():
    """List all jobs from job_data directory"""
    repo = FileBasedJobRepository()
    jobs_list = repo.list_all()

    jobs = []
    for job in jobs_list:
        job_dict = {
            "id": job.id,
            "status": job.status,
            "progress": job.progress,
            "message": job.message,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
            "result": job.result,
            "error": job.error,
        }

        video_path = OUTPUT_DIR / job.id / "final_video.mp4"
        job_dict["video_exists"] = video_path.exists()
        job_dict["video_url"] = f"/outputs/{job.id}/final_video.mp4" if job_dict["video_exists"] else None

        try:
            script = load_script(job.id)
            job_dict.update(get_script_metadata(script))
        except HTTPException:
            pass

        jobs.append(job_dict)

    return {"jobs": jobs}


@router.get("/jobs/completed")
async def list_completed_jobs():
    """List only completed jobs with videos"""
    repo = FileBasedJobRepository()
    jobs_list = repo.list_completed()

    completed = []
    for job in jobs_list:
        job_dict = {
            "id": job.id,
            "status": job.status,
            "progress": job.progress,
            "message": job.message,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
            "result": job.result,
            "error": job.error,
        }

        video_path = OUTPUT_DIR / job.id / "final_video.mp4"
        if video_path.exists():
            job_dict["video_url"] = f"/outputs/{job.id}/final_video.mp4"
            try:
                script = load_script(job.id)
                job_dict.update(get_script_metadata(script))
            except HTTPException:
                pass
            completed.append(job_dict)

    return {"jobs": completed}


@router.delete("/job/{job_id}")
async def delete_job(job_id: str):
    """Delete a job and its associated files"""

    repo = FileBasedJobRepository()
    deleted = repo.delete(job_id)

    output_path = OUTPUT_DIR / job_id
    if output_path.exists():
        shutil.rmtree(output_path)

    return {"message": f"Job {job_id} deleted successfully", "deleted": deleted}


@router.delete("/jobs/failed")
async def delete_failed_jobs():
    """Delete all failed jobs and their directories"""

    repo = FileBasedJobRepository()
    all_jobs = repo.list_all()
    deleted_count = 0

    for job in all_jobs:
        if job.status == "failed":
            repo.delete(job.id)

            output_path = OUTPUT_DIR / job.id
            if output_path.exists():
                shutil.rmtree(output_path)

            deleted_count += 1

    return {"message": f"Deleted {deleted_count} failed jobs", "deleted_count": deleted_count}


@router.get("/job/{job_id}/script")
async def get_job_script(job_id: str):
    """Get the script for a job"""
    return load_script(job_id)


@router.get("/job/{job_id}/details", response_model=DetailedProgress)
async def get_job_details(job_id: str):
    """
    Get detailed progress information for a job including all sections.
    
    Returns comprehensive job details including:
    - Current job status and progress percentage
    - Current processing stage
    - Script metadata (title, duration, section count)
    - Per-section progress with video/audio/code status
    
    Args:
        job_id: Unique job identifier
        
    Returns:
        DetailedProgress with complete job and section information
        
    Raises:
        HTTPException: 404 if job not found
    """
    # Fetch job metadata
    repo = FileBasedJobRepository()
    job = repo.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Map status to processing stage
    current_stage = get_stage_from_status(job.status)

    # Load script if available (optional - may not exist yet)
    script_ready = False
    script_title = None
    total_sections = 0

    try:
        script = load_script(job_id)
        script_ready = True
        script_title = script.get("title", "Untitled")
        total_sections = len(script.get("sections", []))
    except HTTPException:
        # Script not found or not ready - continue with defaults
        script = None

    # Build per-section progress information
    sections, completed_sections = build_sections_progress(job_id, current_stage)

    # Determine which section is currently being processed
    current_section_index = get_current_section_index(
        sections, completed_sections, total_sections, current_stage
    )

    # Normalize progress to 0-1 range
    normalized_progress = min(job.progress / 100.0, 1.0) if job.progress else 0.0

    return DetailedProgress(
        job_id=job_id,
        status=job.status,
        progress=normalized_progress,
        message=job.message,
        current_stage=current_stage,
        current_section_index=current_section_index,
        script_ready=script_ready,
        script_title=script_title,
        total_sections=total_sections,
        completed_sections=completed_sections,
        sections=sections
    )


@router.get("/job/{job_id}/section/{section_index}")
async def get_section_details(job_id: str, section_index: int):
    """Get full details for a specific section including full narration and code"""

    script = load_script(job_id)

    sections = script.get("sections", [])
    if section_index < 0 or section_index >= len(sections):
        raise HTTPException(status_code=404, detail="Section not found")

    section = sections[section_index]
    section_id = section.get("id", f"section_{section_index}")
    sections_dir = OUTPUT_DIR / job_id / "sections"
    section_dir = sections_dir / section_id

    # Get full narration
    narration = section.get("tts_narration") or section.get("narration", "")

    # Get visual description from script OR from visual script file
    visual_description = section.get("visual_description", "")

    # Try to read the visual script file (markdown format)
    visual_script_file = section_dir / f"visual_script_{section_index}.md"
    if visual_script_file.exists():
        try:
            with open(visual_script_file, "r") as f:
                visual_description = f.read()
        except Exception as e:
            print(f"Error reading visual script: {e}")

    # Get narration segments if available
    narration_segments = section.get("narration_segments", [])

    # Get code files if they exist
    code_content = None
    if section_dir.exists():
        code_files = list(section_dir.glob("*.py"))
        if code_files:
            try:
                with open(code_files[0], "r") as f:
                    code_content = f.read()
            except:
                pass

    # Check for video/audio
    merged_path = sections_dir / f"merged_{section_index}.mp4"
    final_section_path = section_dir / "final_section.mp4"
    audio_path = section_dir / "section_audio.mp3"

    video_path = None
    if merged_path.exists():
        video_path = f"/outputs/{job_id}/sections/merged_{section_index}.mp4"
    elif final_section_path.exists():
        video_path = f"/outputs/{job_id}/sections/{section_id}/final_section.mp4"

    return {
        "index": section_index,
        "id": section_id,
        "title": section.get("title", f"Section {section_index + 1}"),
        "duration_seconds": section.get("duration_seconds"),
        "narration": narration,
        "visual_description": visual_description,
        "narration_segments": narration_segments,
        "code": code_content,
        "video_url": video_path,
        "has_audio": audio_path.exists(),
        "has_video": video_path is not None
    }


@router.post("/job/{job_id}/compile-high-quality")
async def compile_high_quality(job_id: str, request: HighQualityCompileRequest):
    """Recompile the video in high quality"""
    from ..services.job_manager import get_job_manager, JobStatus

    repo = FileBasedJobRepository()
    job = repo.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Check if script exists
    try:
        script = load_script(job_id)
    except HTTPException:
        raise HTTPException(status_code=404, detail="Script not found for this job")

    sections = script.get("sections", [])
    if not sections:
        raise HTTPException(status_code=404, detail="No sections found in script")

    # Create a new job for high quality compilation
    hq_job_id = f"{job_id}_hq_{request.quality}"
    job_manager = get_job_manager()  # Keep for background task updates
    job_manager.create_job(hq_job_id)

    async def recompile_high_quality():
        try:
            from ..services.manim_generator import ManimGenerator

            job_manager.update_job(hq_job_id, JobStatus.CREATING_ANIMATIONS, 0, f"Recompiling in {request.quality} quality...")

            manim_generator = ManimGenerator()
            sections_dir = OUTPUT_DIR / job_id / "sections"
            hq_output_dir = OUTPUT_DIR / hq_job_id
            hq_output_dir.mkdir(parents=True, exist_ok=True)
            hq_sections_dir = hq_output_dir / "sections"
            hq_sections_dir.mkdir(exist_ok=True)

            section_videos = []
            total_sections = len(sections)

            for idx, section in enumerate(sections):
                section_id = section.get("id", f"section_{idx}")
                section_dir = sections_dir / section_id

                job_manager.update_job(
                    hq_job_id,
                    JobStatus.CREATING_ANIMATIONS,
                    int((idx / total_sections) * 90),
                    f"Rendering section {idx + 1}/{total_sections} in {request.quality} quality..."
                )

                # Find the code file
                code_files = list(section_dir.glob("scene_*.py"))
                if not code_files:
                    print(f"[HighQuality] No code file found for section {idx}, skipping")
                    continue

                code_file = code_files[0]

                # Copy code to HQ output directory
                hq_section_dir = hq_sections_dir / section_id
                hq_section_dir.mkdir(exist_ok=True)
                hq_code_file = hq_section_dir / code_file.name
                shutil.copy(code_file, hq_code_file)

                # Render with high quality
                from ..services.manim_generator.renderer import render_scene

                scene_name = f"Section{section_id.title().replace('_', '')}"
                output_video = await render_scene(
                    manim_generator,
                    hq_code_file,
                    scene_name,
                    str(hq_section_dir),
                    idx,
                    section=section,
                    quality=request.quality
                )

                if output_video:
                    section_videos.append(output_video)
                    print(f"[HighQuality] Section {idx + 1} rendered: {output_video}")
                else:
                    print(f"[HighQuality] Section {idx + 1} failed to render")

            # Combine videos
            if section_videos:
                job_manager.update_job(hq_job_id, JobStatus.COMPOSING_VIDEO, 90, "Combining sections...")

                from ..services.video_generator.ffmpeg import concatenate_videos
                final_video_path = hq_output_dir / "final_video.mp4"

                await concatenate_videos(section_videos, str(final_video_path))

                job_manager.update_job(
                    hq_job_id,
                    JobStatus.COMPLETED,
                    100,
                    f"High quality ({request.quality}) compilation complete!",
                    result=[{
                        "video_id": hq_job_id,
                        "title": f"{script.get('title', 'Video')} ({request.quality.upper()})",
                        "download_url": f"/outputs/{hq_job_id}/final_video.mp4"
                    }]
                )
            else:
                job_manager.update_job(hq_job_id, JobStatus.FAILED, 0, "No sections were successfully rendered")

        except Exception as e:
            import traceback
            traceback.print_exc()
            job_manager.update_job(hq_job_id, JobStatus.FAILED, 0, f"Error: {str(e)}")

    # Import BackgroundTasks properly and run the task
    import asyncio
    asyncio.create_task(recompile_high_quality())

    return {
        "message": "High quality compilation started",
        "hq_job_id": hq_job_id,
        "quality": request.quality
    }
