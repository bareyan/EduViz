"""
Job management routes.

Routes use JobService to handle business logic,
enabling easier testing and potential future database migration.
"""

import os
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import OUTPUT_DIR
from app.core import validate_path_within_directory
from app.models import JobResponse, DetailedProgress, JobUpdateRequest
from app.services.features.jobs.service import JobService
from app.services.pipeline.audio import TTSEngine

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
    """
    service = JobService()
    return service.get_job_status(job_id)


@router.patch("/job/{job_id}", response_model=JobResponse)
async def update_job(job_id: str, request: JobUpdateRequest):
    """
    Update job metadata (e.g. title).
    """
    service = JobService()
    return service.update_job(job_id, title=request.title)


@router.get("/video/{video_id}")
async def get_video(video_id: str):
    """Stream or download a generated video"""
    service = JobService()
    video_path = service.get_video_path(video_id)
    return FileResponse(
        str(video_path),
        media_type="video/mp4",
        filename=f"{video_id}.mp4"
    )


@router.get("/job/{job_id}/section/{section_index}/video")
async def get_section_video(job_id: str, section_index: int):
    """Get completed section video"""
    service = JobService()
    video_path = service.get_section_video_path(job_id, section_index)
    return FileResponse(str(video_path), media_type="video/mp4")


@router.get("/voices")
async def get_available_voices(language: str = "en"):
    """Get list of available TTS voices based on configured TTS engine"""
    from app.core.voice_catalog import (
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
    """
    service = JobService()
    return service.list_all_jobs()


@router.get("/jobs/completed")
async def list_completed_jobs():
    """
    List only completed jobs with videos.
    """
    service = JobService()
    return service.list_completed_jobs()


@router.delete("/job/{job_id}")
async def delete_job(job_id: str):
    """Delete a job and its associated files"""
    service = JobService()
    return service.delete_job(job_id)


@router.delete("/jobs/failed")
async def delete_failed_jobs():
    """Delete all failed jobs and their directories"""
    service = JobService()
    return service.delete_failed_jobs()


@router.get("/job/{job_id}/script")
async def get_job_script(job_id: str):
    """Get the script for a job"""
    # This acts as a simple pass-through to core utility, but arguably could be in service too.
    # For consistency with the pattern, let's keep it here as a direct utility usage or move it?
    # The 'service.get_job_details' handles script loading internally.
    # The original route just called 'load_script(job_id)'.
    # We'll just call the utility directly as it's a read operation, 
    # OR we could add 'get_script' to service. 
    # Given the strict rules, let's just use load_script directly since it's a 'core' utility, 
    # but to be perfectly clean, let's rely on the service if we want to centralize access.
    # However, 'load_script' is imported from core.
    from app.core import load_script
    return load_script(job_id)


@router.get("/job/{job_id}/details", response_model=DetailedProgress)
async def get_job_details(job_id: str):
    """
    Get detailed progress information for a job including all sections.
    """
    service = JobService()
    return service.get_job_details(job_id)


@router.get("/job/{job_id}/section/{section_index}")
async def get_section_details(job_id: str, section_index: int):
    """Get full details for a specific section including full narration and code"""
    service = JobService()
    return service.get_section_details(job_id, section_index)


