"""
MathViz Backend API
FastAPI application for generating 3Blue1Brown-style educational videos

This is the main entry point that wires together all routes and services.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import (
    API_TITLE, 
    API_DESCRIPTION, 
    API_VERSION, 
    CORS_ORIGINS, 
    OUTPUT_DIR
)
from .routes import (
    upload_router,
    analysis_router,
    generation_router,
    jobs_router,
    sections_router,
    translation_router,
)

# Create FastAPI app
app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    version=API_VERSION
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files for video serving
app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")

# Include routers
app.include_router(upload_router)
app.include_router(analysis_router)
app.include_router(generation_router)
app.include_router(jobs_router)
app.include_router(sections_router)
app.include_router(translation_router)


@app.get("/")
async def root():
    """Root endpoint - API info"""
    return {
        "message": "MathViz API - Generate educational math videos",
        "version": API_VERSION
    }


@app.on_event("startup")
async def startup_event():
    """Handle startup tasks like resuming interrupted jobs"""
    from .services.job_manager import JobStatus, get_job_manager
    from .services.video_generator import VideoGenerator
    
    job_manager = get_job_manager()
    video_generator = VideoGenerator(str(OUTPUT_DIR))
    
    # Track jobs being resumed to avoid duplicate processing
    resuming_jobs = set()
    
    # Find and resume interrupted jobs
    interrupted_jobs = job_manager.get_interrupted_jobs()
    
    for job in interrupted_jobs:
        job_id = job.id
        
        if job_id in resuming_jobs:
            continue
        resuming_jobs.add(job_id)
        
        # Check what progress exists
        progress = video_generator.check_existing_progress(job_id)
        
        if progress["has_script"] and progress["completed_sections"]:
            print(f"[Startup] Found interrupted job {job_id} with {len(progress['completed_sections'])}/{progress['total_sections']} sections")
            
            # Check if all sections are complete
            if len(progress["completed_sections"]) == progress["total_sections"] and progress["total_sections"] > 0:
                # All sections done, just need to combine
                print(f"[Startup] Job {job_id} has all sections, attempting to combine...")
                await _try_combine_job(job_id, job_manager, video_generator, progress)
            else:
                # Some sections incomplete - mark for manual resume
                job_manager.update_job(
                    job_id,
                    JobStatus.FAILED,
                    message=f"Interrupted: {len(progress['completed_sections'])}/{progress['total_sections']} sections complete. Use resume to continue."
                )


async def _try_combine_job(job_id: str, job_manager, video_generator, progress):
    """Try to combine completed sections into final video"""
    import os
    import json
    import asyncio
    from .services.job_manager import JobStatus
    
    job_output_dir = OUTPUT_DIR / job_id
    sections_dir = job_output_dir / "sections"
    
    try:
        # Create concat list
        concat_list_path = job_output_dir / "concat_list.txt"
        script = progress["script"]
        sections = script.get("sections", [])
        
        with open(concat_list_path, "w") as f:
            for i, section in enumerate(sections):
                section_id = section.get("id", f"section_{i}")
                section_path = sections_dir / section_id
                if section_path.exists():
                    for file in os.listdir(section_path):
                        if file.endswith(".mp4"):
                            video_path = section_path / file
                            f.write(f"file '{video_path}'\n")
                            break
        
        # Run ffmpeg
        final_video_path = job_output_dir / "final_video.mp4"
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(concat_list_path), "-c", "copy", str(final_video_path)
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        await process.wait()
        
        if final_video_path.exists():
            # Calculate total duration and chapters
            total_duration = sum(s.get("duration_seconds", 0) for s in sections)
            chapters = []
            current_time = 0
            for section in sections:
                chapters.append({
                    "title": section.get("title", ""),
                    "start_time": current_time,
                    "duration": section.get("duration_seconds", 0)
                })
                current_time += section.get("duration_seconds", 0)
            
            job_manager.update_job(
                job_id,
                JobStatus.COMPLETED,
                100,
                "Video generation complete!",
                result=[{
                    "video_id": job_id,
                    "title": script.get("title", "Math Video"),
                    "duration": total_duration,
                    "chapters": chapters,
                    "download_url": f"/outputs/{job_id}/final_video.mp4",
                    "thumbnail_url": None
                }]
            )
            print(f"[Startup] Job {job_id} combined and completed")
        else:
            job_manager.update_job(job_id, JobStatus.FAILED, message="Failed to combine section videos")
            
    except Exception as e:
        print(f"[Startup] Error combining job {job_id}: {e}")
        job_manager.update_job(job_id, JobStatus.FAILED, message=f"Failed to combine: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        reload=True,
        reload_excludes=["outputs/*", "job_data/*", "uploads/*", "*.pyc", "__pycache__/*"]
    )
