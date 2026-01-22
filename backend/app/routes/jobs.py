"""
Job management routes
"""

import os
import json
import shutil
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..config import OUTPUT_DIR
from ..models import JobResponse
from ..services.job_manager import get_job_manager, JobStatus
from ..services.tts_engine import TTSEngine

router = APIRouter(tags=["jobs"])


@router.get("/job/{job_id}", response_model=JobResponse)
async def get_job_status(job_id: str):
    """Get the status of a video generation job"""
    
    job_manager = get_job_manager()
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    normalized_progress = min(job.progress / 100.0, 1.0) if job.progress else 0.0
    
    return JobResponse(
        job_id=job_id,
        status=job.status.value,
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
    job_manager = get_job_manager()
    jobs = job_manager.list_all_jobs()
    
    for job in jobs:
        job_id = job.get("id", "")
        video_path = OUTPUT_DIR / job_id / "final_video.mp4"
        job["video_exists"] = video_path.exists()
        job["video_url"] = f"/outputs/{job_id}/final_video.mp4" if job["video_exists"] else None
        
        script_path = OUTPUT_DIR / job_id / "script.json"
        if script_path.exists():
            try:
                with open(script_path, "r") as f:
                    script = json.load(f)
                    job["title"] = script.get("title", "Untitled")
                    job["total_duration"] = script.get("total_duration_seconds", 0)
                    job["sections_count"] = len(script.get("sections", []))
            except:
                pass
    
    return {"jobs": jobs}


@router.get("/jobs/completed")
async def list_completed_jobs():
    """List only completed jobs with videos"""
    job_manager = get_job_manager()
    all_jobs = job_manager.list_all_jobs()
    
    completed = []
    for job in all_jobs:
        if job.get("status") == "completed":
            job_id = job.get("id", "")
            video_path = OUTPUT_DIR / job_id / "final_video.mp4"
            if video_path.exists():
                job["video_url"] = f"/outputs/{job_id}/final_video.mp4"
                script_path = OUTPUT_DIR / job_id / "script.json"
                if script_path.exists():
                    try:
                        with open(script_path, "r") as f:
                            script = json.load(f)
                            job["title"] = script.get("title", "Untitled")
                            job["total_duration"] = script.get("total_duration_seconds", 0)
                            job["sections_count"] = len(script.get("sections", []))
                    except:
                        pass
                completed.append(job)
    
    return {"jobs": completed}


@router.delete("/job/{job_id}")
async def delete_job(job_id: str):
    """Delete a job and its associated files"""
    
    job_manager = get_job_manager()
    deleted_job = job_manager.delete_job(job_id)
    
    output_path = OUTPUT_DIR / job_id
    if output_path.exists():
        shutil.rmtree(output_path)
    
    return {"message": f"Job {job_id} deleted successfully", "deleted": deleted_job is not None}


@router.delete("/jobs/failed")
async def delete_failed_jobs():
    """Delete all failed jobs and their directories"""
    
    job_manager = get_job_manager()
    all_jobs = job_manager.list_all_jobs()
    deleted_count = 0
    
    for job in all_jobs:
        if job.get("status") == "failed":
            job_id = job.get("id", "")
            job_manager.delete_job(job_id)
            
            output_path = OUTPUT_DIR / job_id
            if output_path.exists():
                shutil.rmtree(output_path)
            
            deleted_count += 1
    
    return {"message": f"Deleted {deleted_count} failed jobs", "deleted_count": deleted_count}


@router.get("/job/{job_id}/script")
async def get_job_script(job_id: str):
    """Get the script for a job"""
    script_path = OUTPUT_DIR / job_id / "script.json"
    
    if not script_path.exists():
        raise HTTPException(status_code=404, detail="Script not found")
    
    with open(script_path, "r") as f:
        script = json.load(f)
    
    return script
