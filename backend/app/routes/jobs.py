"""
Job management routes
"""

import os
import json
import shutil
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..config import OUTPUT_DIR
from ..models import JobResponse, DetailedProgress, SectionProgress
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


@router.get("/job/{job_id}/details", response_model=DetailedProgress)
async def get_job_details(job_id: str):
    """Get detailed progress information for a job including sections"""
    
    job_manager = get_job_manager()
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Get current stage from status
    status_to_stage = {
        "pending": "analyzing",
        "analyzing": "analyzing", 
        "generating_script": "script",
        "creating_animations": "sections",
        "synthesizing_audio": "sections",
        "composing_video": "combining",
        "completed": "completed",
        "failed": "failed"
    }
    current_stage = status_to_stage.get(job.status.value, "unknown")
    
    # Load script if available
    script_path = OUTPUT_DIR / job_id / "script.json"
    script = None
    script_ready = False
    script_title = None
    sections = []
    total_sections = 0
    completed_sections = 0
    
    if script_path.exists():
        try:
            with open(script_path, "r") as f:
                script = json.load(f)
                script_ready = True
                script_title = script.get("title", "Untitled")
                total_sections = len(script.get("sections", []))
        except Exception:
            pass
    
    # Build section progress from script and file system
    if script:
        sections_dir = OUTPUT_DIR / job_id / "sections"
        for i, section in enumerate(script.get("sections", [])):
            section_id = section.get("id", f"section_{i}")
            section_dir = sections_dir / section_id
            
            # Check what files exist
            has_video = False
            has_audio = False
            has_code = False
            
            merged_path = sections_dir / f"merged_{i}.mp4"
            final_section_path = section_dir / "final_section.mp4"
            audio_path = section_dir / "section_audio.mp3"
            
            # Look for manim code files
            code_files = list(section_dir.glob("*.py")) if section_dir.exists() else []
            has_code = len(code_files) > 0
            
            if merged_path.exists() or final_section_path.exists():
                has_video = True
                completed_sections += 1
                status = "completed"
            elif has_code:
                # Code exists but no video - could be in progress or failed
                status = "generating_manim"
            elif audio_path.exists():
                has_audio = True
                status = "generating_manim"
            else:
                # Check if we're currently working on this section
                if current_stage == "sections" and i == completed_sections:
                    status = "generating_manim"
                else:
                    status = "waiting"
            
            if audio_path.exists():
                has_audio = True
            
            # Get narration preview
            narration = section.get("tts_narration") or section.get("narration", "")
            narration_preview = narration[:200] + "..." if len(narration) > 200 else narration
            
            sections.append(SectionProgress(
                index=i,
                id=section_id,
                title=section.get("title", f"Section {i + 1}"),
                status=status,
                duration_seconds=section.get("duration_seconds"),
                narration_preview=narration_preview,
                has_video=has_video,
                has_audio=has_audio,
                has_code=has_code,
                error=None,
                fix_attempts=0,
                qc_iterations=0
            ))
    
    # Determine current section being processed
    current_section_index = None
    if current_stage == "sections" and sections:
        for section in sections:
            if section.status not in ["completed", "waiting"]:
                current_section_index = section.index
                break
        if current_section_index is None and completed_sections < total_sections:
            current_section_index = completed_sections
    
    normalized_progress = min(job.progress / 100.0, 1.0) if job.progress else 0.0
    
    return DetailedProgress(
        job_id=job_id,
        status=job.status.value,
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
    
    script_path = OUTPUT_DIR / job_id / "script.json"
    
    if not script_path.exists():
        raise HTTPException(status_code=404, detail="Script not found")
    
    with open(script_path, "r") as f:
        script = json.load(f)
    
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
