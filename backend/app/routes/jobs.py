"""
Job management routes.

Routes use JobRepository to abstract job data access,
enabling easier testing and potential future database migration.

Extracted helper functions handle complex logic like building section progress
to keep routes focused on HTTP handling.
"""

import os
import shutil
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..config import OUTPUT_DIR
from ..models import JobResponse, DetailedProgress, HighQualityCompileRequest, JobUpdateRequest
from ..services.infrastructure.storage import FileBasedJobRepository
from ..services.pipeline.audio import TTSEngine
from ..core import (
    load_script,
    get_script_metadata,
    validate_job_id,
    validate_path_within_directory,
    job_intermediate_artifacts_available,
    job_is_final_only,
    assert_runtime_tools_available,
    load_video_info,
    list_all_videos,
    load_error_info,
    list_all_failures,
    save_video_info,
    save_script,
)
from .jobs_helpers import (
    get_stage_from_status,
    build_sections_progress,
    get_current_section_index,
)

router = APIRouter(tags=["jobs"])


def _load_visual_script(section: dict, section_dir: "Path") -> str:
    """
    Resolve visual script text for section details.

    Priority:
    1) section.visual_description from script.json
    2) choreography_plan.json persisted in section directory
    """
    visual_description = str(section.get("visual_description", "") or "").strip()
    if visual_description:
        return visual_description

    candidates = []
    if section.get("choreography_plan_path"):
        candidates.append(Path(str(section.get("choreography_plan_path"))).resolve())
    candidates.append((section_dir / "choreography_plan.json").resolve())

    for candidate in candidates:
        try:
            if not validate_path_within_directory(candidate, OUTPUT_DIR):
                continue
            if not candidate.exists() or not candidate.is_file():
                continue
            with open(candidate, "r", encoding="utf-8") as f:
                payload = json.load(f)
            if isinstance(payload, (dict, list)):
                return json.dumps(payload, ensure_ascii=False, indent=2)
            return str(payload)
        except Exception:
            continue

    return ""


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


@router.patch("/job/{job_id}", response_model=JobResponse)
async def update_job(job_id: str, request: JobUpdateRequest):
    """
    Update job metadata (e.g. title).
    
    Updates title in:
    1. Active job script (if exists)
    2. Persisted video_info.json (if exists)
    """
    if not validate_job_id(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    repo = FileBasedJobRepository()
    job = repo.get(job_id)
    
    updated_any = False
    
    # Update video_info.json (most important for Gallery)
    video_info = load_video_info(job_id)
    if video_info and request.title:
        video_info.title = request.title
        save_video_info(video_info)
        updated_any = True
        
    # Update script.json (if exists)
    try:
        script = load_script(job_id)
        if request.title:
            script["title"] = request.title
            save_script(job_id, script)
            updated_any = True
    except HTTPException:
        pass
        
    if not job and not updated_any:
        raise HTTPException(status_code=404, detail="Job not found")
        
    if not job:
        if video_info:
            # Reconstruct completed job state from video_info
            return JobResponse(
                job_id=job_id,
                status="completed",
                progress=1.0,
                message="Video ready",
                result={
                    "title": video_info.title,
                    "duration": video_info.duration,
                    "chapters": [c.to_dict() for c in video_info.chapters],
                }
            )
        else:
             raise HTTPException(status_code=404, detail="Job not found")
            
    # If job exists, return updated state
    # We might need to refresh 'result' if it was loaded from disk before we updated script
    if request.title and job.result:
        # Optimistically update result in memory for response
        if isinstance(job.result, dict):
            job.result["title"] = request.title
        elif isinstance(job.result, list) and job.result and isinstance(job.result[0], dict):
             job.result[0]["title"] = request.title

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
    if not validate_job_id(video_id):
        raise HTTPException(status_code=400, detail="Invalid video ID format")

    video_path = (OUTPUT_DIR / video_id / "final_video.mp4").resolve()
    if not validate_path_within_directory(video_path, OUTPUT_DIR):
        raise HTTPException(status_code=403, detail="Access denied")

    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video not found")

    return FileResponse(
        str(video_path),
        media_type="video/mp4",
        filename=f"{video_id}.mp4"
    )


@router.get("/job/{job_id}/section/{section_index}/video")
async def get_section_video(job_id: str, section_index: int):
    """Get completed section video"""
    if not validate_job_id(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    sections_dir = OUTPUT_DIR / job_id / "sections"
    section_dir = sections_dir / str(section_index)
    if not validate_path_within_directory(section_dir, OUTPUT_DIR):
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Check for video in order of preference
    for video_name in ["final_section.mp4", "section.mp4"]:
        video_path = section_dir / video_name
        if video_path.exists():
            return FileResponse(str(video_path), media_type="video/mp4")
    
    # Also check merged path
    merged_path = sections_dir / f"merged_{section_index}.mp4"
    if merged_path.exists():
        return FileResponse(str(merged_path), media_type="video/mp4")
    
    raise HTTPException(status_code=404, detail="Section video not found")


@router.get("/voices")
async def get_available_voices(language: str = "en"):
    """Get list of available TTS voices based on configured TTS engine"""
    from ..core.voice_catalog import (
        get_gemini_tts_voices_for_language,
        get_gemini_tts_available_languages,
        get_gemini_tts_default_voice
    )
    
    tts_engine = os.getenv("TTS_ENGINE", "edge").lower().strip()
    
    if tts_engine == "gemini":
        voices = get_gemini_tts_voices_for_language(language)
        for voice in voices:
            voice["preview_url"] = f"/static/voice_previews/{voice['id']}.mp3"
        return {
            "voices": voices,
            "languages": get_gemini_tts_available_languages(),
            "current_language": language,
            "default_voice": get_gemini_tts_default_voice(language),
            "engine": "gemini"
        }
    
    # Default: Edge TTS
    voices = TTSEngine.get_voices_for_language(language)
    for voice in voices:
        voice["preview_url"] = f"/static/voice_previews/{voice['id']}.mp3"
    return {
        "voices": voices,
        "languages": TTSEngine.get_available_languages(),
        "current_language": language,
        "default_voice": TTSEngine.get_default_voice_for_language(language),
        "engine": "edge"
    }


@router.get("/jobs")
async def list_all_jobs():
    """
    List all jobs and completed videos.
    
    Combines:
    - Active jobs from job_data (in-progress work)
    - Completed videos from outputs/ (persisted video_info.json)
    """
    repo = FileBasedJobRepository()
    jobs_list = repo.list_all()
    seen_ids = set()
    jobs = []

    # Process active jobs from job_data
    for job in jobs_list:
        seen_ids.add(job.id)
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

        # Try video_info.json first (survives cleanup), fallback to script.json
        video_info = load_video_info(job.id)
        if video_info:
            job_dict["title"] = video_info.title
            job_dict["total_duration"] = video_info.duration
            job_dict["sections_count"] = len(video_info.chapters)
        else:
            try:
                script = load_script(job.id)
                job_dict.update(get_script_metadata(script))
            except HTTPException:
                pass

        jobs.append(job_dict)

    # Add completed videos without job_data (orphaned after cleanup)
    for video_info in list_all_videos():
        if video_info.video_id in seen_ids:
            continue
        
        video_path = OUTPUT_DIR / video_info.video_id / "final_video.mp4"
        if not video_path.exists():
            continue
        
        jobs.append({
            "id": video_info.video_id,
            "status": "completed",
            "progress": 100,
            "message": "Video ready",
            "created_at": video_info.created_at or "",
            "updated_at": video_info.created_at or "",
            "result": None,
            "error": None,
            "video_exists": True,
            "video_url": f"/outputs/{video_info.video_id}/final_video.mp4",
            "title": video_info.title,
            "total_duration": video_info.duration,
            "sections_count": len(video_info.chapters),
        })
        seen_ids.add(video_info.video_id)

    # Add persistent failures (job data cleaned but error persisted)
    for error_info in list_all_failures():
        if error_info.job_id in seen_ids:
            continue

        jobs.append({
            "id": error_info.job_id,
            "status": "failed",
            "progress": 0,
            "message": error_info.error_message,
            "created_at": error_info.timestamp,
            "updated_at": error_info.timestamp,
            "result": None,
            "error": error_info.error_message,
            "video_exists": False,
            "video_url": None,
            "title": error_info.title or f"Failed Job ({error_info.job_id[:8]})",
        })

    return {"jobs": jobs}


@router.get("/jobs/completed")
async def list_completed_jobs():
    """
    List only completed jobs with videos.
    
    Combines:
    - Completed jobs from job_data
    - Orphaned videos (where job_data was cleaned but video exists)
    """
    repo = FileBasedJobRepository()
    jobs_list = repo.list_completed()
    seen_ids = set()
    completed = []

    for job in jobs_list:
        seen_ids.add(job.id)
        video_path = OUTPUT_DIR / job.id / "final_video.mp4"
        if not video_path.exists():
            continue

        job_dict = {
            "id": job.id,
            "status": job.status,
            "progress": job.progress,
            "message": job.message,
            "created_at": job.created_at,
            "updated_at": job.updated_at,
            "result": job.result,
            "error": job.error,
            "video_url": f"/outputs/{job.id}/final_video.mp4",
        }

        # Try video_info.json first (survives cleanup), fallback to script.json
        video_info = load_video_info(job.id)
        if video_info:
            job_dict["title"] = video_info.title
            job_dict["total_duration"] = video_info.duration
            job_dict["sections_count"] = len(video_info.chapters)
        else:
            try:
                script = load_script(job.id)
                job_dict.update(get_script_metadata(script))
            except HTTPException:
                pass

        completed.append(job_dict)

    # Add orphaned videos (video exists but job_data cleaned)
    for video_info in list_all_videos():
        if video_info.video_id in seen_ids:
            continue
        
        video_path = OUTPUT_DIR / video_info.video_id / "final_video.mp4"
        if not video_path.exists():
            continue
        
        completed.append({
            "id": video_info.video_id,
            "status": "completed",
            "progress": 100,
            "message": "Video ready",
            "created_at": video_info.created_at or "",
            "updated_at": video_info.created_at or "",
            "result": None,
            "error": None,
            "video_url": f"/outputs/{video_info.video_id}/final_video.mp4",
            "title": video_info.title,
            "total_duration": video_info.duration,
            "sections_count": len(video_info.chapters),
        })

    return {"jobs": completed}


@router.delete("/job/{job_id}")
async def delete_job(job_id: str):
    """Delete a job and its associated files"""
    if not validate_job_id(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    repo = FileBasedJobRepository()
    deleted = repo.delete(job_id)

    output_path = (OUTPUT_DIR / job_id).resolve()
    if validate_path_within_directory(output_path, OUTPUT_DIR) and output_path.exists():
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

            output_path = (OUTPUT_DIR / job.id).resolve()
            if validate_path_within_directory(output_path, OUTPUT_DIR) and output_path.exists():
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

    if not validate_job_id(job_id):
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    script = load_script(job_id)

    sections = script.get("sections", [])
    if section_index < 0 or section_index >= len(sections):
        raise HTTPException(status_code=404, detail="Section not found")

    section = sections[section_index]
    section_id = section.get("id", f"section_{section_index}")
    sections_dir = OUTPUT_DIR / job_id / "sections"
    if not validate_path_within_directory(sections_dir, OUTPUT_DIR):
        raise HTTPException(status_code=403, detail="Access denied")
    # Section directories use index, not section_id
    section_dir = sections_dir / str(section_index)

    # Get full narration
    narration = section.get("tts_narration") or section.get("narration", "")

    # Get visual script from script metadata or persisted choreography plan
    visual_description = _load_visual_script(section, section_dir)

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
        video_path = f"/outputs/{job_id}/sections/{section_index}/final_section.mp4"

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
    assert_runtime_tools_available(("manim", "ffmpeg"), context="high-quality recompilation")

    import asyncio
    from ..services.infrastructure.orchestration import get_job_manager, JobStatus
    from ..services.pipeline.animation import ManimGenerator
    from ..services.pipeline.animation.generation.core import render_scene, extract_scene_name
    from ..services.pipeline.assembly.ffmpeg import concatenate_videos

    repo = FileBasedJobRepository()
    job = repo.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job_is_final_only(job_id):
        raise HTTPException(
            status_code=409,
            detail=(
                "This job was cleaned to final-video-only retention. "
                "High-quality recompilation requires script and section artifacts."
            ),
        )

    if not job_intermediate_artifacts_available(job_id):
        raise HTTPException(
            status_code=400,
            detail="Required script/section artifacts are missing for high-quality recompilation",
        )

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
                section_dir = sections_dir / str(idx)  # Use index, not section_id

                job_manager.update_job(
                    hq_job_id,
                    JobStatus.CREATING_ANIMATIONS,
                    int((idx / total_sections) * 90),
                    f"Rendering section {idx + 1}/{total_sections} in {request.quality} quality..."
                )

                # Find the code file
                code_files = list(section_dir.glob("scene_*.py"))
                if not code_files:
                    code_files = list(section_dir.glob("*.py"))
                if not code_files:
                    print(f"[HighQuality] No code file found for section {idx}, skipping")
                    continue

                code_file = code_files[0]

                # Copy code to HQ output directory
                hq_section_dir = hq_sections_dir / str(idx)  # Use index, not section_id
                hq_section_dir.mkdir(exist_ok=True)
                hq_code_file = hq_section_dir / code_file.name
                shutil.copy(code_file, hq_code_file)

                # Render with high quality
                with open(hq_code_file, "r", encoding="utf-8", errors="ignore") as f:
                    code_content = f.read()
                scene_name = extract_scene_name(code_content) or f"Section{section_id.title().replace('_', '')}"
                output_video = await render_scene(
                    manim_generator,
                    hq_code_file,
                    scene_name,
                    str(hq_section_dir),
                    idx,
                    file_manager=manim_generator.file_manager,
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

    asyncio.create_task(recompile_high_quality())

    return {
        "message": "High quality compilation started",
        "hq_job_id": hq_job_id,
        "quality": request.quality
    }
