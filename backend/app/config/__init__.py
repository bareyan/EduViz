"""
Application configuration and settings

Modules:
- paths: Directory paths
- constants: API settings and constants
- models: Model and pipeline configuration
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=True)

# Re-export paths
from .paths import APP_DIR, BACKEND_DIR, UPLOAD_DIR, OUTPUT_DIR, JOB_DATA_DIR

# Re-export constants
from .constants import (
    API_TITLE,
    API_DESCRIPTION,
    API_VERSION,
    CORS_ORIGINS,
    ALLOWED_MIME_TYPES,
    ALLOWED_EXTENSIONS,
)

# Re-export model configuration
from .models import (
    ModelConfig,
    ThinkingLevel,
    PipelineModels,
    ACTIVE_PIPELINE,
    DEFAULT_PIPELINE_MODELS,
    HIGH_QUALITY_PIPELINE,
    COST_OPTIMIZED_PIPELINE,
    AVAILABLE_PIPELINES,
    AVAILABLE_MODELS,
    THINKING_CAPABLE_MODELS,
    get_model_config,
    get_thinking_config,
    set_active_pipeline,
    get_active_pipeline_name,
    list_pipeline_steps,
)

# Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

__all__ = [
    "APP_DIR",
    "BACKEND_DIR",
    "UPLOAD_DIR",
    "OUTPUT_DIR",
    "JOB_DATA_DIR",
    "API_TITLE",
    "API_DESCRIPTION",
    "API_VERSION",
    "CORS_ORIGINS",
    "ALLOWED_MIME_TYPES",
    "ALLOWED_EXTENSIONS",
    "GEMINI_API_KEY",
    "ModelConfig",
    "ThinkingLevel",
    "PipelineModels",
    "ACTIVE_PIPELINE",
    "DEFAULT_PIPELINE_MODELS",
    "HIGH_QUALITY_PIPELINE",
    "COST_OPTIMIZED_PIPELINE",
    "AVAILABLE_PIPELINES",
    "AVAILABLE_MODELS",
    "THINKING_CAPABLE_MODELS",
    "get_model_config",
    "get_thinking_config",
    "set_active_pipeline",
    "get_active_pipeline_name",
    "list_pipeline_steps",
]
