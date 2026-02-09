"""
Paths configuration

Centralized directory paths for the application.
"""

from pathlib import Path

# Base directories
APP_DIR = Path(__file__).parent.parent
BACKEND_DIR = APP_DIR.parent
STATIC_DIR = BACKEND_DIR / "static"
VOICE_PREVIEWS_DIR = STATIC_DIR / "voice_previews"
UPLOAD_DIR = BACKEND_DIR / "uploads"
OUTPUT_DIR = BACKEND_DIR / "outputs"
JOB_DATA_DIR = BACKEND_DIR / "job_data"

# Ensure directories exist
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
JOB_DATA_DIR.mkdir(parents=True, exist_ok=True)
VOICE_PREVIEWS_DIR.mkdir(parents=True, exist_ok=True)

__all__ = ["APP_DIR", "BACKEND_DIR", "UPLOAD_DIR", "OUTPUT_DIR", "JOB_DATA_DIR", "STATIC_DIR", "VOICE_PREVIEWS_DIR"]
