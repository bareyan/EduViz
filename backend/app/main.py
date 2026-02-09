"""
MathViz Backend API
FastAPI application for generating 3Blue1Brown-style educational videos

This is the main entry point that wires together all routes and services.
"""

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
    is_auth_enabled,
    is_public_path,
    is_request_authenticated,
    list_public_paths,
)
from .services.infrastructure.orchestration.lifecycle import StartupManager

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    startup_manager = StartupManager(app)
    await startup_manager.run_startup()
    try:
        yield
    finally:
        await startup_manager.run_shutdown()


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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_excludes=["outputs/*", "job_data/*", "uploads/*", "*.pyc", "__pycache__/*"]
    )
