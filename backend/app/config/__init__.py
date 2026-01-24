"""
Application configuration and settings
"""

import os
from pathlib import Path

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# Model configuration
from .models import (
    ModelConfig,
    ThinkingLevel,
    PipelineModels,
    ACTIVE_PIPELINE,
    ACTIVE_PROVIDER,
    LLMProviderType,
    DEFAULT_PIPELINE_MODELS,
    HIGH_QUALITY_PIPELINE,
    COST_OPTIMIZED_PIPELINE,
    OLLAMA_PIPELINE,
    AVAILABLE_MODELS,
    AVAILABLE_OLLAMA_MODELS,
    GEMINI_TO_OLLAMA_MAP,
    THINKING_CAPABLE_MODELS,
    get_model_config,
    get_model_name,
    get_model_for_provider,  # Alias for get_model_name
    get_thinking_config,
    get_active_provider,
    list_pipeline_steps,
    # Feature flags
    ENABLE_VISUAL_QC,
    ENABLE_TRANSLATION,
    # Default Ollama models
    DEFAULT_OLLAMA_GENERAL,
    DEFAULT_OLLAMA_CODE,
)

# Base directories
APP_DIR = Path(__file__).parent.parent
BACKEND_DIR = APP_DIR.parent
UPLOAD_DIR = BACKEND_DIR / "uploads"
OUTPUT_DIR = BACKEND_DIR / "outputs"
JOB_DATA_DIR = BACKEND_DIR / "job_data"

# Ensure directories exist
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
JOB_DATA_DIR.mkdir(parents=True, exist_ok=True)

# API settings
API_TITLE = "MathViz API"
API_DESCRIPTION = "Generate 3Blue1Brown-style educational videos from any material"
API_VERSION = "1.0.0"

# CORS origins
CORS_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001", 
    "http://localhost:5173",
]

# LLM Provider settings
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "").lower() or None  # "gemini" or "ollama"
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# Gemini API (for backward compatibility)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# File upload settings
ALLOWED_MIME_TYPES = [
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

ALLOWED_EXTENSIONS = [".pdf", ".png", ".jpg", ".jpeg", ".webp", ".tex", ".txt"]
