"""
MathViz Backend API
FastAPI application for generating 3Blue1Brown-style educational videos
"""

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import uuid
import asyncio
import json

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

from .services.analyzer_v2 import MaterialAnalyzer
from .services.video_generator_v2 import VideoGenerator
from .services.job_manager import JobManager, JobStatus

app = FastAPI(
    title="MathViz API",
    description="Generate 3Blue1Brown-style educational videos from any material",
    version="1.0.0"
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create directories
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "uploads")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Mount static files for video serving
app.mount("/outputs", StaticFiles(directory=OUTPUT_DIR), name="outputs")

# Initialize services
analyzer = MaterialAnalyzer()
video_generator = VideoGenerator(OUTPUT_DIR)
job_manager = JobManager()

# Track jobs being resumed to avoid duplicate processing
_resuming_jobs: set = set()


class AnalysisRequest(BaseModel):
    file_id: str


class GenerationRequest(BaseModel):
    file_id: str
    analysis_id: str
    selected_topics: List[int]  # List of topic indices to generate
    style: str = "3blue1brown"
    max_video_length: int = 20  # Max minutes per video
    voice: str = "en-US-GuyNeural"  # Edge TTS voice
    video_mode: str = "comprehensive"  # "comprehensive" or "overview"
    language: str = "en"  # Language code for narration and content (en, fr, etc.)


class TopicSuggestion(BaseModel):
    index: int
    title: str
    description: str
    estimated_duration: int  # in minutes
    complexity: str  # "beginner", "intermediate", "advanced"
    subtopics: List[str]


class AnalysisResult(BaseModel):
    analysis_id: str
    file_id: str
    material_type: str  # "pdf", "image", "mixed"
    total_content_pages: int
    detected_math_elements: int
    suggested_topics: List[TopicSuggestion]
    estimated_total_videos: int
    summary: str


class VideoChapter(BaseModel):
    title: str
    start_time: float
    duration: float  # Changed from end_time to match actual data


class GeneratedVideo(BaseModel):
    video_id: str
    title: str
    duration: float
    chapters: List[VideoChapter]
    download_url: str
    thumbnail_url: Optional[str]


class JobResponse(BaseModel):
    job_id: str
    status: str
    progress: float
    message: str
    result: Optional[List[GeneratedVideo]] = None


@app.on_event("startup")
async def startup_event():
    """Resume interrupted jobs on server startup"""
    interrupted_jobs = job_manager.get_interrupted_jobs()
    
    if interrupted_jobs:
        print(f"[Startup] Found {len(interrupted_jobs)} interrupted job(s)")
        
        for job in interrupted_jobs:
            print(f"[Startup] Attempting to resume job {job.id} (status: {job.status.value})")
            
            # Try to find the original file for the job
            # Look for any file with matching job_id prefix in uploads
            job_output_dir = os.path.join(OUTPUT_DIR, job.id)
            script_path = os.path.join(job_output_dir, "script.json")
            
            if os.path.exists(script_path):
                # Job had a script, try to resume from where it left off
                asyncio.create_task(resume_job(job))
            else:
                # No script found, mark as failed
                job_manager.update_job(
                    job.id,
                    JobStatus.FAILED,
                    message="Job interrupted before script was generated. Please restart."
                )
                print(f"[Startup] Job {job.id} marked as failed - no script found")


async def resume_job(job):
    """Resume an interrupted job from its last state"""
    import json as json_module
    
    job_id = job.id
    job_output_dir = os.path.join(OUTPUT_DIR, job_id)
    script_path = os.path.join(job_output_dir, "script.json")
    
    try:
        # Load the script
        with open(script_path, "r") as f:
            script = json_module.load(f)
        
        sections = script.get("sections", [])
        sections_dir = os.path.join(job_output_dir, "sections")
        
        # Check which sections are already completed
        completed_sections = set()
        if os.path.exists(sections_dir):
            for section_folder in os.listdir(sections_dir):
                section_path = os.path.join(sections_dir, section_folder)
                # A section is complete if it has a video file
                if os.path.isdir(section_path):
                    for f in os.listdir(section_path):
                        if f.endswith(".mp4"):
                            completed_sections.add(section_folder)
                            break
        
        print(f"[Resume] Job {job_id}: {len(completed_sections)}/{len(sections)} sections completed")
        
        # If all sections done, just need to combine
        final_video_path = os.path.join(job_output_dir, "final_video.mp4")
        
        if len(completed_sections) >= len(sections) and not os.path.exists(final_video_path):
            # All sections done, just need to combine videos
            job_manager.update_job(job_id, JobStatus.COMPOSING_VIDEO, 95, "Resuming: Combining section videos...")
            
            # Combine videos using ffmpeg
            await combine_section_videos(job_id, job_output_dir, sections_dir, len(sections))
            
        elif len(completed_sections) >= len(sections) and os.path.exists(final_video_path):
            # Everything done, mark as complete
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
            print(f"[Resume] Job {job_id} marked as completed")
        else:
            # Some sections incomplete - mark as failed for now
            # Full resume would require re-running video generator
            job_manager.update_job(
                job_id,
                JobStatus.FAILED,
                message=f"Job interrupted during generation ({len(completed_sections)}/{len(sections)} sections). Please regenerate."
            )
            print(f"[Resume] Job {job_id} marked as failed - incomplete sections")
            
    except Exception as e:
        print(f"[Resume] Error resuming job {job_id}: {e}")
        job_manager.update_job(job_id, JobStatus.FAILED, message=f"Failed to resume: {str(e)}")


async def combine_section_videos(job_id: str, job_output_dir: str, sections_dir: str, num_sections: int):
    """Combine section videos into final video"""
    import subprocess
    
    # Create concat list
    concat_list_path = os.path.join(job_output_dir, "concat_list.txt")
    with open(concat_list_path, "w") as f:
        for i in range(num_sections):
            section_folder = f"section_{i:03d}"
            section_path = os.path.join(sections_dir, section_folder)
            if os.path.exists(section_path):
                for file in os.listdir(section_path):
                    if file.endswith(".mp4"):
                        video_path = os.path.join(section_path, file)
                        f.write(f"file '{video_path}'\n")
                        break
    
    # Run ffmpeg
    final_video_path = os.path.join(job_output_dir, "final_video.mp4")
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", concat_list_path, "-c", "copy", final_video_path
    ]
    
    process = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    await process.wait()
    
    if os.path.exists(final_video_path):
        # Load script for metadata
        script_path = os.path.join(job_output_dir, "script.json")
        import json as json_module
        with open(script_path, "r") as f:
            script = json_module.load(f)
        
        sections = script.get("sections", [])
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
        print(f"[Resume] Job {job_id} video combined and completed")
    else:
        job_manager.update_job(job_id, JobStatus.FAILED, message="Failed to combine section videos")


@app.get("/")
async def root():
    return {"message": "MathViz API - Generate educational math videos", "version": "1.0.0"}


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload a PDF, image, or text file for analysis"""
    
    # Validate file type
    allowed_types = [
        "application/pdf",
        "image/png",
        "image/jpeg",
        "image/jpg",
        "image/webp",
        "text/plain",
        "text/x-tex",
        "application/x-tex",
        "application/x-latex",
    ]
    
    # Also allow by file extension for text files (browsers may send different MIME types)
    file_ext = os.path.splitext(file.filename)[1].lower() if file.filename else ""
    allowed_extensions = [".pdf", ".png", ".jpg", ".jpeg", ".webp", ".tex", ".txt"]
    
    if file.content_type not in allowed_types and file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"File type {file.content_type} not supported. Use PDF, images, LaTeX, or text files."
        )
    
    # Generate unique file ID
    file_id = str(uuid.uuid4())
    file_extension = os.path.splitext(file.filename)[1]
    saved_path = os.path.join(UPLOAD_DIR, f"{file_id}{file_extension}")
    
    # Save file
    content = await file.read()
    with open(saved_path, "wb") as f:
        f.write(content)
    
    return {
        "file_id": file_id,
        "filename": file.filename,
        "size": len(content),
        "type": file.content_type
    }


@app.post("/analyze")
async def analyze_material(request: AnalysisRequest):
    """Analyze uploaded material and suggest video topics"""
    
    # Find the uploaded file
    file_path = None
    for ext in [".pdf", ".png", ".jpg", ".jpeg", ".webp", ".tex", ".txt"]:
        potential_path = os.path.join(UPLOAD_DIR, f"{request.file_id}{ext}")
        if os.path.exists(potential_path):
            file_path = potential_path
            break
    
    if not file_path:
        raise HTTPException(status_code=404, detail="File not found")
    
    try:
        result = await analyzer.analyze(file_path, request.file_id)
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.post("/generate", response_model=JobResponse)
async def generate_videos(request: GenerationRequest, background_tasks: BackgroundTasks):
    """Start video generation job"""
    
    # Find the uploaded file
    file_path = None
    for ext in [".pdf", ".png", ".jpg", ".jpeg", ".webp", ".tex", ".txt"]:
        potential_path = os.path.join(UPLOAD_DIR, f"{request.file_id}{ext}")
        if os.path.exists(potential_path):
            file_path = potential_path
            break
    
    if not file_path:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Create a new job
    job_id = str(uuid.uuid4())
    job_manager.create_job(job_id)
    
    # Start generation in background
    async def run_generation():
        try:
            job_manager.update_job(job_id, JobStatus.ANALYZING, 0, "Re-analyzing material...")
            
            # Re-analyze to get topic details (we need the full topic data)
            analysis = await analyzer.analyze(file_path, request.file_id)
            all_topics = analysis.get("suggested_topics", [])
            
            # Get selected topics
            selected_topics = [t for t in all_topics if t.get("index") in request.selected_topics]
            
            if not selected_topics:
                job_manager.update_job(job_id, JobStatus.FAILED, 0, "No valid topics selected")
                return
            
            all_results = []
            total_topics = len(selected_topics)
            
            for topic_idx, topic in enumerate(selected_topics):
                base_progress = (topic_idx / total_topics) * 100
                
                job_manager.update_job(
                    job_id, 
                    JobStatus.CREATING_ANIMATIONS, 
                    base_progress, 
                    f"Generating {request.video_mode} video {topic_idx + 1}/{total_topics}: {topic.get('title', 'Unknown')}"
                )
                
                result = await video_generator.generate_video(
                    file_path=file_path,
                    file_id=request.file_id,
                    topic=topic,
                    voice=request.voice,
                    progress_callback=lambda p: job_manager.update_job(
                        job_id, 
                        JobStatus.CREATING_ANIMATIONS, 
                        base_progress + (p.get("progress", 0) / total_topics), 
                        p.get("message", "Processing...")
                    ),
                    job_id=job_id,  # Pass the job_id so output folder matches
                    video_mode=request.video_mode,  # Pass the video mode
                    style=request.style,  # Pass the visual style
                    language=request.language  # Pass the language for content generation
                )
                
                if result.get("status") == "completed":
                    all_results.append({
                        "video_id": job_id,  # Use job_id directly since it's now consistent
                        "title": result["script"]["title"],
                        "duration": result["total_duration"],
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
            import traceback
            traceback.print_exc()
            job_manager.update_job(job_id, JobStatus.FAILED, 0, f"Error: {str(e)}")
    
    background_tasks.add_task(run_generation)
    
    return JobResponse(
        job_id=job_id,
        status="pending",
        progress=0.0,
        message="Video generation started"
    )


@app.get("/job/{job_id}", response_model=JobResponse)
async def get_job_status(job_id: str):
    """Get the status of a video generation job"""
    
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Normalize progress to 0-1 range for frontend (backend uses 0-100)
    normalized_progress = min(job.progress / 100.0, 1.0) if job.progress else 0.0
    
    return JobResponse(
        job_id=job_id,
        status=job.status.value,
        progress=normalized_progress,
        message=job.message,
        result=job.result
    )


@app.get("/video/{video_id}")
async def get_video(video_id: str):
    """Stream or download a generated video"""
    
    video_path = os.path.join(OUTPUT_DIR, f"{video_id}.mp4")
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail="Video not found")
    
    return FileResponse(
        video_path,
        media_type="video/mp4",
        filename=f"{video_id}.mp4"
    )


@app.get("/voices")
async def get_available_voices(language: str = "en"):
    """Get list of available TTS voices, optionally filtered by language"""
    from app.services.tts_engine import TTSEngine
    
    return {
        "voices": TTSEngine.get_voices_for_language(language),
        "languages": TTSEngine.get_available_languages(),
        "current_language": language
    }


@app.delete("/file/{file_id}")
async def delete_file(file_id: str):
    """Delete an uploaded file"""
    
    deleted = False
    for ext in [".pdf", ".png", ".jpg", ".jpeg", ".webp", ".tex", ".txt"]:
        file_path = os.path.join(UPLOAD_DIR, f"{file_id}{ext}")
        if os.path.exists(file_path):
            os.remove(file_path)
            deleted = True
            break
    
    if not deleted:
        raise HTTPException(status_code=404, detail="File not found")
    
    return {"message": "File deleted successfully"}


# ============= Gallery & Job Management Endpoints =============

@app.get("/jobs")
async def list_all_jobs():
    """List all jobs from job_data directory"""
    jobs = job_manager.list_all_jobs()
    
    # Enhance with video existence check and script info
    for job in jobs:
        job_id = job.get("id", "")
        # Check if video exists in outputs directory
        video_path = os.path.join(OUTPUT_DIR, job_id, "final_video.mp4")
        job["video_exists"] = os.path.exists(video_path)
        job["video_url"] = f"/outputs/{job_id}/final_video.mp4" if job["video_exists"] else None
        
        # Try to get script info for title, duration, sections
        script_path = os.path.join(OUTPUT_DIR, job_id, "script.json")
        if os.path.exists(script_path):
            try:
                with open(script_path, "r") as f:
                    script = json.load(f)
                    job["title"] = script.get("title", "Untitled")
                    job["total_duration"] = script.get("total_duration_seconds", 0)
                    job["sections_count"] = len(script.get("sections", []))
            except:
                pass
    
    return {"jobs": jobs}


@app.get("/jobs/completed")
async def list_completed_jobs():
    """List only completed jobs with videos"""
    all_jobs = job_manager.list_all_jobs()
    
    completed = []
    for job in all_jobs:
        if job.get("status") == "completed":
            job_id = job.get("id", "")
            video_path = os.path.join(OUTPUT_DIR, job_id, "final_video.mp4")
            if os.path.exists(video_path):
                job["video_url"] = f"/outputs/{job_id}/final_video.mp4"
                # Try to get script info
                script_path = os.path.join(OUTPUT_DIR, job_id, "script.json")
                if os.path.exists(script_path):
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


@app.delete("/job/{job_id}")
async def delete_job(job_id: str):
    """Delete a job and its associated files"""
    import shutil
    
    # Delete from job_manager
    deleted_job = job_manager.delete_job(job_id)
    
    # Delete output directory if exists
    output_path = os.path.join(OUTPUT_DIR, job_id)
    if os.path.exists(output_path):
        shutil.rmtree(output_path)
    
    return {"message": f"Job {job_id} deleted successfully", "deleted": deleted_job is not None}


@app.delete("/jobs/failed")
async def delete_failed_jobs():
    """Delete all failed jobs and their directories"""
    import shutil
    
    all_jobs = job_manager.list_all_jobs()
    deleted_count = 0
    
    for job in all_jobs:
        if job.get("status") == "failed":
            job_id = job.get("id", "")
            
            # Delete from job_manager
            job_manager.delete_job(job_id)
            
            # Delete output directory
            output_path = os.path.join(OUTPUT_DIR, job_id)
            if os.path.exists(output_path):
                shutil.rmtree(output_path)
            
            deleted_count += 1
    
    return {"message": f"Deleted {deleted_count} failed jobs", "deleted_count": deleted_count}


@app.get("/job/{job_id}/script")
async def get_job_script(job_id: str):
    """Get the script for a job"""
    script_path = os.path.join(OUTPUT_DIR, job_id, "script.json")
    
    if not os.path.exists(script_path):
        raise HTTPException(status_code=404, detail="Script not found")
    
    with open(script_path, "r") as f:
        script = json.load(f)
    
    return script


@app.get("/job/{job_id}/sections")
async def get_job_sections(job_id: str):
    """Get all section files for a job (for editing)"""
    job_dir = os.path.join(OUTPUT_DIR, job_id)
    sections_dir = os.path.join(job_dir, "sections")
    
    if not os.path.exists(sections_dir):
        raise HTTPException(status_code=404, detail="Sections not found")
    
    # Load script.json for metadata and ordering
    script_sections = []
    script_path = os.path.join(job_dir, "script.json")
    if os.path.exists(script_path):
        with open(script_path, "r") as f:
            script = json.load(f)
            script_sections = script.get("sections", [])
            # Sort by 'order' field if present, otherwise keep original order
            script_sections = sorted(script_sections, key=lambda s: s.get("order", float('inf')))
    
    # Get list of section folders that exist on disk
    existing_folders = set()
    if os.path.exists(sections_dir):
        existing_folders = {f for f in os.listdir(sections_dir) if os.path.isdir(os.path.join(sections_dir, f))}
    
    # Build sections list in script order (chronological)
    sections = []
    processed_ids = set()
    
    # First, add sections in script.json order
    for script_section in script_sections:
        section_id = script_section.get("id")
        if section_id and section_id in existing_folders:
            section_path = os.path.join(sections_dir, section_id)
            section_info = script_section.copy()
            section_info["files"] = {}
            
            # Check for files - return paths instead of content
            for f in os.listdir(section_path):
                full_path = os.path.join(section_path, f)
                if f.endswith(".py"):
                    section_info["files"][f] = full_path
                    if not section_info.get("manim_code"):
                        with open(full_path, "r") as pf:
                            section_info["manim_code"] = pf.read()
                elif f.endswith(".mp4"):
                    section_info["video"] = full_path
                elif f.endswith(".mp3"):
                    section_info["audio"] = full_path
            
            sections.append(section_info)
            processed_ids.add(section_id)
    
    # Then add any folders not in script.json (shouldn't happen, but just in case)
    for section_folder in sorted(existing_folders - processed_ids):
        section_path = os.path.join(sections_dir, section_folder)
        section_info = {"id": section_folder, "files": {}}
        
        for f in os.listdir(section_path):
            full_path = os.path.join(section_path, f)
            if f.endswith(".py"):
                section_info["files"][f] = full_path
                if not section_info.get("manim_code"):
                    with open(full_path, "r") as pf:
                        section_info["manim_code"] = pf.read()
            elif f.endswith(".mp4"):
                section_info["video"] = full_path
            elif f.endswith(".mp3"):
                section_info["audio"] = full_path
        
        sections.append(section_info)
    
    return {"sections": sections}


@app.put("/job/{job_id}/section/{section_id}/code")
async def update_section_code(job_id: str, section_id: str, request: dict):
    """Update the Manim code for a section"""
    sections_dir = os.path.join(OUTPUT_DIR, job_id, "sections", section_id)
    
    if not os.path.exists(sections_dir):
        raise HTTPException(status_code=404, detail="Section not found")
    
    # Support both 'code' and 'manim_code' field names
    code = request.get("manim_code") or request.get("code", "")
    
    # Find existing scene file or use default name
    scene_file = None
    for f in os.listdir(sections_dir):
        if f.endswith(".py") and f.startswith("scene"):
            scene_file = f
            break
    
    filename = scene_file or "scene_0.py"
    code_path = os.path.join(sections_dir, filename)
    with open(code_path, "w") as f:
        f.write(code)
    
    # Also update the script.json manim_code field
    script_path = os.path.join(OUTPUT_DIR, job_id, "script.json")
    if os.path.exists(script_path):
        with open(script_path, "r") as f:
            script = json.load(f)
        
        for section in script.get("sections", []):
            if section.get("id") == section_id:
                section["manim_code"] = code
                break
        
        with open(script_path, "w") as f:
            json.dump(script, f, indent=2)
    
    return {"message": "Code updated successfully"}


@app.get("/file-content")
async def get_file_content(path: str):
    """Get the content of a file by path"""
    from fastapi.responses import PlainTextResponse, Response
    
    # Security: Only allow files within the outputs directory
    abs_path = os.path.abspath(path)
    abs_output_dir = os.path.abspath(OUTPUT_DIR)
    
    if not abs_path.startswith(abs_output_dir):
        raise HTTPException(status_code=403, detail="Access denied - path outside outputs directory")
    
    if not os.path.exists(abs_path):
        raise HTTPException(status_code=404, detail="File not found")
    
    # Determine content type based on file extension
    ext = os.path.splitext(abs_path)[1].lower()
    
    # Custom headers for CORS with credentials (needed for canvas capture)
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "*",
    }
    
    if ext in [".mp4", ".webm", ".mov", ".avi"]:
        # Return video files as binary with proper MIME type
        return FileResponse(abs_path, media_type="video/mp4", headers=headers)
    elif ext in [".mp3", ".wav", ".ogg"]:
        # Return audio files
        return FileResponse(abs_path, media_type="audio/mpeg", headers=headers)
    elif ext in [".png", ".jpg", ".jpeg", ".gif"]:
        # Return image files
        media_type = "image/png" if ext == ".png" else "image/jpeg" if ext in [".jpg", ".jpeg"] else "image/gif"
        return FileResponse(abs_path, media_type=media_type, headers=headers)
    else:
        # Return text files
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return PlainTextResponse(content, headers=headers)


@app.post("/job/{job_id}/recompile")
async def recompile_job(job_id: str, background_tasks: BackgroundTasks):
    """Recompile a job's video from existing section files"""
    import subprocess
    
    job_dir = os.path.join(OUTPUT_DIR, job_id)
    sections_dir = os.path.join(job_dir, "sections")
    
    if not os.path.exists(sections_dir):
        raise HTTPException(status_code=404, detail="Job sections not found")
    
    async def run_recompile():
        try:
            job_manager.update_job(job_id, JobStatus.COMPOSING_VIDEO, 50, "Recompiling video...")
            
            # Read canonical section ordering from script.json (falls back to folder sort)
            script_path = os.path.join(OUTPUT_DIR, job_id, "script.json")
            ordered_sections = []
            if os.path.exists(script_path):
                try:
                    with open(script_path, "r") as sf:
                        script = json.load(sf)
                        ordered_sections = sorted(
                            script.get("sections", []),
                            key=lambda s: s.get("order", 0)
                        )
                except Exception as e:
                    print(f"Error reading script.json: {e}")
                    ordered_sections = []

            # Fallback: list directories in alphabetical order (legacy mode)
            if not ordered_sections:
                for section_folder in sorted(os.listdir(sections_dir)):
                    section_path = os.path.join(sections_dir, section_folder)
                    if os.path.isdir(section_path):
                        ordered_sections.append({"id": section_folder})

            if not ordered_sections:
                job_manager.update_job(job_id, JobStatus.FAILED, 0, "No sections found to recompile")
                return

            concat_file = os.path.join(job_dir, "concat_list.txt")
            combined_files = []

            for i, sec in enumerate(ordered_sections):
                section_id = sec.get("id")
                section_path = os.path.join(sections_dir, section_id)
                
                # Use paths from script.json if available, otherwise scan folder
                video_file = sec.get("video")
                audio_file = sec.get("audio")
                
                # Validate paths exist
                if video_file and not os.path.exists(video_file):
                    print(f"Section {section_id}: video path from script.json doesn't exist: {video_file}")
                    video_file = None
                if audio_file and not os.path.exists(audio_file):
                    print(f"Section {section_id}: audio path from script.json doesn't exist: {audio_file}")
                    audio_file = None
                
                # Fallback: scan folder for files if not in script.json or paths invalid
                if not video_file and os.path.isdir(section_path):
                    # Walk through all subdirectories to find .mp4 files
                    for root, dirs, files in os.walk(section_path):
                        for f in files:
                            if f.endswith(".mp4"):
                                video_file = os.path.join(root, f)
                                break
                        if video_file:
                            break
                
                if not audio_file and os.path.isdir(section_path):
                    for f in os.listdir(section_path):
                        if f.endswith(".mp3"):
                            audio_file = os.path.join(section_path, f)
                            break

                if not video_file:
                    print(f"Skipping section {section_id} (order {sec.get('order', '?')}): no video found")
                    continue

                print(f"Processing section {section_id} (order {sec.get('order', '?')})")
                print(f"  Video: {video_file}")
                print(f"  Audio: {audio_file}")

                combined = os.path.join(job_dir, f"combined_{i:03d}.mp4")

                if audio_file:
                    # Get durations to decide on merge strategy
                    def get_duration(file_path):
                        try:
                            probe_cmd = ["ffprobe", "-v", "error", "-show_entries", "format=duration", 
                                        "-of", "default=noprint_wrappers=1:nokey=1", file_path]
                            result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
                            return float(result.stdout.strip())
                        except:
                            return 0.0
                    
                    video_duration = get_duration(video_file)
                    audio_duration = get_duration(audio_file)
                    print(f"  Video duration: {video_duration:.1f}s, Audio duration: {audio_duration:.1f}s")
                    
                    if video_duration >= audio_duration:
                        # Video is long enough, use -shortest
                        cmd = [
                            "ffmpeg", "-y",
                            "-i", video_file,
                            "-i", audio_file,
                            "-c:v", "libx264",
                            "-c:a", "aac",
                            "-shortest",
                            combined
                        ]
                    else:
                        # Video is shorter than audio - extend with tpad (freeze last frame)
                        print(f"  Extending video by {audio_duration - video_duration:.1f}s to match audio")
                        cmd = [
                            "ffmpeg", "-y",
                            "-i", video_file,
                            "-i", audio_file,
                            "-filter_complex", "[0:v]tpad=stop=-1:stop_mode=clone,setpts=PTS-STARTPTS[v]",
                            "-map", "[v]",
                            "-map", "1:a:0",
                            "-c:v", "libx264",
                            "-c:a", "aac",
                            "-t", str(audio_duration),
                            combined
                        ]
                else:
                    # No audio: copy video into combined file (re-mux to standard container)
                    cmd = [
                        "ffmpeg", "-y",
                        "-i", video_file,
                        "-c", "copy",
                        combined
                    ]

                print(f"Running ffmpeg: {' '.join(cmd)}")
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    print(f"ffmpeg error for section {section_id}: {result.stderr}")
                
                if os.path.exists(combined):
                    combined_files.append(combined)
                    print(f"  Created: {combined}")
                else:
                    print(f"  FAILED to create: {combined}")

            if not combined_files:
                job_manager.update_job(job_id, JobStatus.FAILED, 0, "No combined section videos produced")
                return

            print(f"Concatenating {len(combined_files)} combined files in order...")
            
            # Create concat file - files are already in order because we iterate ordered_sections
            with open(concat_file, "w") as f:
                for p in combined_files:
                    f.write(f"file '{p}'\n")

            # Concatenate all combined videos
            final_video = os.path.join(job_dir, "final_video.mp4")
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", concat_file,
                "-c", "copy",
                final_video
            ]
            print(f"Running final concat: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"Final concat ffmpeg error: {result.stderr}")

            if os.path.exists(final_video):
                print(f"Successfully created final video: {final_video}")
                job_manager.update_job(job_id, JobStatus.COMPLETED, 100, "Video recompiled successfully!")
            else:
                job_manager.update_job(job_id, JobStatus.FAILED, 0, "Failed to create final video")
                
        except Exception as e:
            job_manager.update_job(job_id, JobStatus.FAILED, 0, f"Recompile error: {str(e)}")
    
    background_tasks.add_task(run_recompile)
    
    return {"message": "Recompile started", "job_id": job_id}


class FixCodeRequest(BaseModel):
    prompt: str = ""
    frames: List[str] = []  # Base64 encoded images
    current_code: str = ""


@app.post("/job/{job_id}/section/{section_id}/fix")
async def fix_section_code(job_id: str, section_id: str, request: FixCodeRequest):
    """Use Gemini to fix/improve Manim code based on prompt and optional frame context"""
    import base64
    from google import genai
    from google.genai import types
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")
    
    # Get section info
    sections_dir = os.path.join(OUTPUT_DIR, job_id, "sections", section_id)
    if not os.path.exists(sections_dir):
        raise HTTPException(status_code=404, detail="Section not found")
    
    # Load section metadata for context
    script_path = os.path.join(OUTPUT_DIR, job_id, "script.json")
    section_info = {}
    if os.path.exists(script_path):
        with open(script_path, "r") as f:
            script = json.load(f)
            for section in script.get("sections", []):
                if section.get("id") == section_id:
                    section_info = section
                    break
    
    client = genai.Client(api_key=api_key)
    
    # Determine audio duration (if any) for extra context
    audio_duration = None
    try:
        # Look for audio file in section folder
        for f in os.listdir(sections_dir):
            if f.endswith('.mp3') or f.endswith('.wav'):
                audio_path = os.path.join(sections_dir, f)
                # Use ffprobe to get audio duration if available
                try:
                    import subprocess
                    cmd = [
                        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                        '-of', 'default=noprint_wrappers=1:nokey=1', audio_path
                    ]
                    res = subprocess.run(cmd, capture_output=True, text=True)
                    if res.returncode == 0:
                        dur_str = res.stdout.strip()
                        try:
                            audio_duration = float(dur_str)
                        except Exception:
                            audio_duration = None
                except Exception:
                    audio_duration = None
                break
    except Exception:
        audio_duration = None

    # Build the prompt
    system_prompt = """You are an expert Manim animator, skilled at creating beautiful 3Blue1Brown-style mathematical animations.
Your task is to fix or improve the provided Manim code based on the user's request.

RULES:
1. Return ONLY the complete fixed Python code, no explanations
2. Keep the same class name and structure
3. Ensure the code is valid Manim CE (Community Edition) code
4. Make animations smooth and visually appealing
5. Use proper positioning, colors, and timing
6. If frames are provided, use them to understand what's currently wrong visually

Return ONLY the Python code, nothing else."""

    audio_info_text = f"Audio duration: {audio_duration:.2f} seconds" if audio_duration else "No audio"

    user_prompt = f"""Section Title: {section_info.get('title', 'Unknown')}
Section Description: {section_info.get('visual_description', 'N/A')}
Narration: {section_info.get('narration', 'N/A')}
{audio_info_text}

CURRENT MANIM CODE:
```python
{request.current_code}
```

USER REQUEST: {request.prompt if request.prompt else 'Please review and fix any issues with this code.'}

Please provide the fixed/improved Manim code."""

    # Prepare content parts (frames first, then text prompt)
    parts = []
    for i, frame_data in enumerate(request.frames[:5]):  # Max 5 frames
        try:
            if "base64," in frame_data:
                base64_data = frame_data.split("base64,")[1]
                image_bytes = base64.b64decode(base64_data)
                try:
                    parts.append(types.Part.from_bytes(data=image_bytes, mime_type="image/png"))
                except Exception:
                    # If SDK doesn't support Part.from_bytes, skip but continue
                    print(f"Warning: Could not attach frame {i} to Gemini request")
        except Exception as e:
            print(f"Error processing frame {i}: {e}")

    parts.append(types.Part.from_text(text=user_prompt))
    
    try:
        response = client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=[types.Content(role="user", parts=parts)],
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.3,
            )
        )
        
        fixed_code = response.text
        
        # Clean up the response - extract code from markdown if present
        if "```python" in fixed_code:
            fixed_code = fixed_code.split("```python")[1].split("```")[0].strip()
        elif "```" in fixed_code:
            fixed_code = fixed_code.split("```")[1].split("```")[0].strip()
        
        return {"fixed_code": fixed_code}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Gemini error: {str(e)}")


@app.post("/job/{job_id}/section/{section_id}/regenerate")
async def regenerate_section(job_id: str, section_id: str):
    """Regenerate the video for a single section using its current Manim code"""
    import subprocess
    import shutil
    
    sections_dir = os.path.join(OUTPUT_DIR, job_id, "sections", section_id)
    if not os.path.exists(sections_dir):
        raise HTTPException(status_code=404, detail="Section not found")
    
    try:
        # Find the Manim code file and determine the section index from filename
        code_file = None
        section_index = 0
        for f in os.listdir(sections_dir):
            if f.endswith(".py") and f.startswith("scene"):
                code_file = os.path.join(sections_dir, f)
                # Extract index from scene_X.py
                import re
                idx_match = re.search(r"scene_(\d+)\.py", f)
                if idx_match:
                    section_index = int(idx_match.group(1))
                break
        
        if not code_file:
            raise HTTPException(status_code=404, detail="No Manim code file found in section")
        
        # Read the code to find the class name
        with open(code_file, "r") as f:
            code = f.read()
        
        import re
        class_match = re.search(r"class\s+(\w+)\s*\(", code)
        if not class_match:
            raise HTTPException(status_code=400, detail="Could not find Scene class in code")
        
        class_name = class_match.group(1)
        
        # Find existing video file to determine naming pattern
        existing_video = None
        for f in os.listdir(sections_dir):
            if f.endswith(".mp4"):
                existing_video = f
                break
        
        # Use existing name pattern or fall back to section_X.mp4
        if existing_video:
            output_video_name = existing_video
        else:
            output_video_name = f"section_{section_index}.mp4"
        
        output_video = os.path.join(sections_dir, output_video_name)
        
        # Remove old video if exists
        if os.path.exists(output_video):
            os.remove(output_video)
        
        # Clean up old manim output directories
        for subdir in ["videos", "media", "images", "Tex", "texts"]:
            subdir_path = os.path.join(sections_dir, subdir)
            if os.path.exists(subdir_path):
                shutil.rmtree(subdir_path)
        
        # Run manim to generate new video
        # Use -ql for quick low quality, output to media_dir
        output_name = output_video_name.replace(".mp4", "")
        cmd = [
            "manim",
            "-ql",  # Low quality for faster render
            "--media_dir", sections_dir,
            "-o", output_name,  # Output filename without extension
            code_file,
            class_name
        ]
        
        print(f"Running manim: {' '.join(cmd)}")
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            cwd=sections_dir,
            timeout=120  # 2 minute timeout
        )
        
        if result.returncode != 0:
            print(f"Manim stderr: {result.stderr}")
            print(f"Manim stdout: {result.stdout}")
            raise HTTPException(status_code=500, detail=f"Manim render failed: {result.stderr[:500]}")
        
        # Find the generated video and move it to section root
        video_found = False
        media_videos_dir = os.path.join(sections_dir, "videos")
        if os.path.exists(media_videos_dir):
            for root, dirs, files in os.walk(media_videos_dir):
                for f in files:
                    if f.endswith(".mp4"):
                        src = os.path.join(root, f)
                        shutil.move(src, output_video)
                        video_found = True
                        print(f"Moved video from {src} to {output_video}")
                        break
                if video_found:
                    break
            # Clean up the videos directory
            shutil.rmtree(media_videos_dir)
        
        if not video_found and not os.path.exists(output_video):
            raise HTTPException(status_code=500, detail="Manim did not produce a video file")
        
        # Update the script.json with the new video path
        script_path = os.path.join(OUTPUT_DIR, job_id, "script.json")
        if os.path.exists(script_path):
            with open(script_path, "r") as f:
                script = json.load(f)
            
            for section in script.get("sections", []):
                if section.get("id") == section_id:
                    section["video"] = output_video
                    break
            
            with open(script_path, "w") as f:
                json.dump(script, f, indent=2)
        
        return {
            "message": "Section regenerated successfully",
            "section_id": section_id,
            "video_path": output_video
        }
                
    except HTTPException:
        raise
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Manim render timed out after 2 minutes")
    except Exception as e:
        print(f"Regenerate error: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Regeneration failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        reload=True,
        reload_excludes=["outputs/*", "job_data/*", "uploads/*", "*.pyc", "__pycache__/*"]
    )
