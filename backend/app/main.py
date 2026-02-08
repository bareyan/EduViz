"""
MathViz Backend API
FastAPI application for generating 3Blue1Brown-style educational videos

This is the main entry point that wires together all routes and services.
"""

import asyncio
import os
import uuid
import shutil
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from time import monotonic
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from .config import (
    API_TITLE,
    API_DESCRIPTION,
    API_VERSION,
    CORS_ORIGINS,
    OUTPUT_DIR,
    UPLOAD_DIR,
    STATIC_DIR,
)
from .routes import (
    auth_router,
    upload_router,
    analysis_router,
    generation_router,
    jobs_router,
    sections_router,
    translation_router,

)
from .core import (
    setup_logging,
    get_logger,
    set_request_id,
    clear_context,
    parse_bool_env,
    run_startup_runtime_checks,
    is_auth_enabled,
    is_public_path,
    is_request_authenticated,
    list_public_paths,
)

# Initialize logging
log_level = os.getenv("LOG_LEVEL", "INFO")
log_file = os.getenv("LOG_FILE")
use_json_logs = os.getenv("JSON_LOGS", "false").lower() == "true"
pipeline_log_file = os.getenv("PIPELINE_LOG_FILE", "logs/animation_pipeline.jsonl")

setup_logging(
    level=log_level,
    log_file=Path(log_file) if log_file else None,
    use_json=use_json_logs,
    pipeline_log_file=Path(pipeline_log_file) if pipeline_log_file else None
)

logger = get_logger(__name__, service="api")
logger.info("Starting MathViz Backend API", extra={
    "log_level": log_level,
    "json_logs": use_json_logs
})

logger.info("Authentication mode", extra={
    "auth_enabled": is_auth_enabled(),
    "public_paths": list_public_paths(),
})

# Runtime protection controls
MAX_REQUEST_BODY_BYTES = int(os.getenv("MAX_REQUEST_BODY_BYTES", str(2 * 1024 * 1024)))
RATE_LIMIT_ENABLED = parse_bool_env(os.getenv("RATE_LIMIT_ENABLED"), default=True)
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS_PER_MINUTE", "600"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "60"))
RATE_LIMIT_EXEMPT_PATHS = {"/", "/health"}
_rate_limit_buckets: dict[str, deque[float]] = defaultdict(deque)

async def _run_startup() -> None:
    """Handle startup tasks like resuming interrupted jobs."""
    from .services.infrastructure.orchestration import get_job_manager
    from .services.infrastructure.storage import OutputCleanupService
    from .services.pipeline.assembly import VideoGenerator
    from app.models.status import JobStatus

    job_manager = get_job_manager()
    video_generator = VideoGenerator(str(OUTPUT_DIR))
    cleanup_service = OutputCleanupService(OUTPUT_DIR, job_manager, upload_dir=UPLOAD_DIR)

    strict_runtime = parse_bool_env(
        os.getenv("STARTUP_STRICT_RUNTIME_CHECKS"),
        default=os.getenv("ENV", "").lower() == "production",
    )
    runtime_report = run_startup_runtime_checks(
        output_dir=OUTPUT_DIR,
        upload_dir=UPLOAD_DIR,
        strict_tools=strict_runtime,
        strict_dirs=True,
    )
    app.state.runtime_report = runtime_report
    logger.info("Startup runtime checks complete", extra={"runtime_report": runtime_report})

    app.state.output_cleanup_task = None
    try:
        cleanup_service.run_once()
        app.state.output_cleanup_task = asyncio.create_task(cleanup_service.run_periodic())
    except Exception as exc:
        logger.error("Failed to initialize output cleanup", extra={"error": str(exc)}, exc_info=True)

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


async def _run_shutdown() -> None:
    """Stop background services gracefully."""
    cleanup_task = getattr(app.state, "output_cleanup_task", None)
    if cleanup_task:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await _run_startup()
    try:
        yield
    finally:
        await _run_shutdown()


# Create FastAPI app
app = FastAPI(
    title=API_TITLE,
    description=API_DESCRIPTION,
    version=API_VERSION,
    lifespan=lifespan,
)


@app.middleware("http")
async def add_request_correlation(request: Request, call_next):
    """Add correlation ID, enforce request limits, and attach security headers."""
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    set_request_id(request_id)
    path = request.url.path
    client_ip = request.client.host if request.client else "unknown"

    logger.info(f"{request.method} {path}", extra={
        "method": request.method,
        "path": path,
        "client": client_ip,
    })

    try:
        if request.method != "OPTIONS" and is_auth_enabled() and not is_public_path(path):
            if not is_request_authenticated(request):
                return JSONResponse(status_code=401, content={"detail": "Authentication required"})

        # Upload route has its own streaming file-size guard.
        if path != "/upload":
            content_length = request.headers.get("content-length")
            if content_length:
                try:
                    size = int(content_length)
                    if size > MAX_REQUEST_BODY_BYTES:
                        raise HTTPException(
                            status_code=413,
                            detail=(
                                f"Request body too large. Max allowed: "
                                f"{MAX_REQUEST_BODY_BYTES // (1024 * 1024)}MB"
                            ),
                        )
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid Content-Length header")

        if RATE_LIMIT_ENABLED and path not in RATE_LIMIT_EXEMPT_PATHS and not path.startswith("/outputs/"):
            now = monotonic()
            bucket = _rate_limit_buckets[client_ip]
            window_start = now - RATE_LIMIT_WINDOW_SECONDS
            while bucket and bucket[0] < window_start:
                bucket.popleft()
            if len(bucket) >= RATE_LIMIT_REQUESTS:
                raise HTTPException(status_code=429, detail="Rate limit exceeded. Please retry later.")
            bucket.append(now)

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("X-Frame-Options", "DENY")

        logger.info(f"Response: {response.status_code}", extra={
            "status_code": response.status_code,
            "method": request.method,
            "path": path,
        })

        return response
    finally:
        clear_context()

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
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Include routers
app.include_router(auth_router)
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


@app.get("/health")
async def health_check():
    """
    Health check endpoint for container orchestration.
    
    Validates all critical system dependencies:
    - External tools (manim, ffmpeg, ffprobe)
    - Backend credentials (Gemini API key OR Vertex AI project config)
    - Disk space availability
    
    Returns 200 if healthy, 503 if any check fails.
    """
    checks = {
        "status": "healthy",
        "checks": {}
    }
    
    all_healthy = True
    
    # Check external tools
    tools = {
        "manim": {"command": "manim", "required": True},
        "ffmpeg": {"command": "ffmpeg", "required": True},
        "ffprobe": {"command": "ffprobe", "required": True},
        "ruff": {"command": "ruff", "required": False},
        "pyright": {"command": "pyright", "required": False}  # Optional (requires Node.js)
    }
    
    for tool_name, config in tools.items():
        command = config["command"]
        required = config["required"]
        available = shutil.which(command) is not None
        
        checks["checks"][tool_name] = {
            "available": available,
            "required": required,
            "path": shutil.which(command) if available else None
        }
        
        if not available:
            if required:
                all_healthy = False
                logger.warning(f"Health check: {tool_name} not found in PATH (REQUIRED)")
            else:
                logger.info(f"Health check: {tool_name} not found in PATH (optional - type checking disabled)")
    
    # Check backend credentials
    use_vertex_ai = os.getenv("USE_VERTEX_AI", "false").lower() == "true"
    checks["checks"]["llm_backend"] = {
        "use_vertex_ai": use_vertex_ai,
        "backend": "vertex_ai" if use_vertex_ai else "gemini_api",
    }

    if use_vertex_ai:
        gcp_project_id = os.getenv("GCP_PROJECT_ID")
        gcp_location = os.getenv("GCP_LOCATION", "us-central1")
        checks["checks"]["vertex_ai"] = {
            "project_id_configured": bool(gcp_project_id),
            "location": gcp_location,
        }
        if not gcp_project_id:
            all_healthy = False
            logger.warning("Health check: GCP_PROJECT_ID not configured (USE_VERTEX_AI=true)")
    else:
        gemini_key_exists = bool(os.getenv("GEMINI_API_KEY"))
        checks["checks"]["gemini_api_key"] = {
            "configured": gemini_key_exists
        }
        if not gemini_key_exists:
            all_healthy = False
            logger.warning("Health check: GEMINI_API_KEY not configured (USE_VERTEX_AI=false)")
    
    # Check disk space (warn if < 1GB available) - cross-platform implementation
    try:
        disk_stats = shutil.disk_usage(OUTPUT_DIR)
        free_space_gb = disk_stats.free / (1024 ** 3)
        checks["checks"]["disk_space"] = {
            "available_gb": round(free_space_gb, 2),
            "sufficient": free_space_gb > 1.0
        }
        if free_space_gb < 1.0:
            logger.warning(f"Health check: Low disk space ({free_space_gb:.2f} GB)")
    except Exception as e:
        checks["checks"]["disk_space"] = {
            "error": str(e),
            "sufficient": False
        }
        logger.error(f"Health check: Failed to check disk space: {e}")

    runtime_report = getattr(app.state, "runtime_report", None)
    if runtime_report is not None:
        checks["checks"]["runtime_startup"] = runtime_report
    
    # Set overall status
    if not all_healthy:
        checks["status"] = "unhealthy"
        raise HTTPException(
            status_code=503,
            detail=checks
        )
    
    return checks


async def _try_combine_job(job_id: str, job_manager, video_generator, progress):
    """Try to combine completed sections into final video"""
    import os
    import asyncio
    from app.models.status import JobStatus

    job_output_dir = OUTPUT_DIR / job_id
    sections_dir = job_output_dir / "sections"

    try:
        # Create concat list
        concat_list_path = job_output_dir / "concat_list.txt"
        script = progress["script"]
        sections = script.get("sections", [])

        added_videos = 0
        with open(concat_list_path, "w", encoding="utf-8") as f:
            for i, section in enumerate(sections):
                section_id = section.get("id", f"section_{i}")
                # Section directories are index-based in the pipeline, with section_id as legacy fallback.
                candidate_dirs = [sections_dir / str(i), sections_dir / section_id]
                section_path = next((p for p in candidate_dirs if p.exists() and p.is_dir()), None)
                if not section_path:
                    continue

                video_path = None
                preferred = section_path / "final_section.mp4"
                legacy_merged = sections_dir / f"merged_{i}.mp4"

                if preferred.exists():
                    video_path = preferred
                elif legacy_merged.exists():
                    video_path = legacy_merged
                else:
                    mp4_files = sorted([p for p in section_path.iterdir() if p.suffix.lower() == ".mp4"])
                    if mp4_files:
                        video_path = mp4_files[0]

                if video_path:
                    escaped = str(video_path).replace("'", "'\\''")
                    f.write(f"file '{escaped}'\n")
                    added_videos += 1

        if added_videos == 0:
            raise RuntimeError("No section videos found for startup combine")

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

            # Generate thumbnail
            from app.services.pipeline.assembly.ffmpeg import generate_thumbnail
            thumbnail_url = None
            thumb_path = job_output_dir / "thumbnail.jpg"
            if await generate_thumbnail(str(final_video_path), str(thumb_path), time=min(total_duration/2, 5.0)):
                thumbnail_url = f"/outputs/{job_id}/thumbnail.jpg"

            video_result = {
                "video_id": job_id,
                "title": script.get("title", "Math Video"),
                "duration": total_duration,
                "chapters": chapters,
                "download_url": f"/outputs/{job_id}/final_video.mp4",
                "thumbnail_url": thumbnail_url
            }

            # Persist video_info.json for Gallery
            from app.core import save_video_info, create_video_info_from_result
            video_info = create_video_info_from_result(job_id, video_result)
            save_video_info(video_info)

            job_manager.update_job(
                job_id,
                JobStatus.COMPLETED,
                100,
                "Video generation complete!",
                result=[video_result]
            )
            print(f"[Startup] Job {job_id} combined and completed")
        else:
            job_manager.update_job(job_id, JobStatus.FAILED, message="Failed to combine section videos")

    except Exception as e:
        print(f"[Startup] Error combining job {job_id}: {e}")
        job_manager.update_job(job_id, JobStatus.FAILED, message=f"Failed to combine: {str(e)}")
    finally:
        try:
            if concat_list_path.exists():
                concat_list_path.unlink()
        except Exception:
            pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_excludes=["outputs/*", "job_data/*", "uploads/*", "*.pyc", "__pycache__/*"]
    )
