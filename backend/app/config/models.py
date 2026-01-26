"""
Model Configuration for Pipeline Steps

This module defines all AI models used throughout the video generation pipeline.
Each pipeline step has its own model configuration, allowing for easy tuning
and experimentation with different models.

Thinking Levels (for gemini-3-flash-preview and gemini-3-pro-preview):
    - LOW: Minimal reasoning, fastest responses
    - MEDIUM: Balanced reasoning and speed
    - HIGH: Deep reasoning, slower but more accurate
"""

from enum import Enum
from typing import Optional
from dataclasses import dataclass, field


class ThinkingLevel(str, Enum):
    """Thinking budget levels for Gemini 3 models"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    NONE = None  # For models that don't support thinking


@dataclass
class ModelConfig:
    """Configuration for a single model"""
    model_name: str
    thinking_level: Optional[ThinkingLevel] = None
    description: str = ""
    max_correction_attempts: int = 2

    @property
    def supports_thinking(self) -> bool:
        """Check if this model supports thinking configuration"""
        return self.model_name in THINKING_CAPABLE_MODELS


# Models that support thinking configuration
THINKING_CAPABLE_MODELS = [
    "gemini-3-flash-preview",
    "gemini-3-pro-preview",
]

# Available models
AVAILABLE_MODELS = [
    # Gemini 3 Preview (with thinking support)
    "gemini-3-flash-preview",
    "gemini-3-pro-preview",

    # Gemini 2.5
    "gemini-2.5-flash",
    "gemini-2.5-pro",

    # Gemini 2.0 Flash Lite
    "gemini-flash-lite-latest",

    # Legacy
    "gemini-2.0-flash",
]


@dataclass
class PipelineModels:
    """
    Model configuration for each step of the video generation pipeline.
    
    Pipeline Steps:
    1. Analysis - Analyze uploaded documents/images
    2. Script Generation - Create video script with chapters
    3. Language Detection - Detect document language
    4. Translation - Translate content if needed
    5. Manim Generation - Generate Manim animation code
    6. Code Correction - Fix errors in generated code
    7. Visual QC - Quality control of rendered videos
    8. Code Fix (Manual) - User-requested code fixes
    """

    # Step 1: Material Analysis
    # Analyzes PDFs, images, and text files to extract content
    analysis: ModelConfig = field(default_factory=lambda: ModelConfig(
        model_name="gemini-flash-lite-latest",
        thinking_level=None,
        description="Fast analysis of uploaded materials"
    ))

    # Step 2: Script Generation (Two-phase)
    # Phase 1: Create detailed video script with chapters and narration
    script_generation: ModelConfig = field(default_factory=lambda: ModelConfig(
        model_name="gemini-3-flash-preview",
        thinking_level=ThinkingLevel.MEDIUM,
        description="Generate comprehensive video scripts"
    ))

    # Step 3: Language Detection
    # Detect the language of the source document
    language_detection: ModelConfig = field(default_factory=lambda: ModelConfig(
        model_name="gemini-flash-lite-latest",
        thinking_level=None,
        description="Quick language detection"
    ))

    # Step 4: Translation
    # Translate content between languages
    translation: ModelConfig = field(default_factory=lambda: ModelConfig(
        model_name="gemini-flash-lite-latest",
        thinking_level=None,
        description="Efficient content translation"
    ))

    # Step 4.5: Visual Script Generation
    # Generate detailed visual script (storyboard)
    visual_script_generation: ModelConfig = field(default_factory=lambda: ModelConfig(
        model_name="gemini-3-flash-preview",
        thinking_level=ThinkingLevel.HIGH,
        description="Generate visual descriptions and layout"
    ))

    # Step 5: Manim Code Generation
    # Generate Manim animation code from script
    manim_generation: ModelConfig = field(default_factory=lambda: ModelConfig(
        model_name="gemini-3-flash-preview",
        thinking_level=ThinkingLevel.MEDIUM,
        description="Generate Manim animation code",
        max_correction_attempts=5  # Increased: diff-based corrections are cheap
    ))

    # Step 6a: Code Correction (Primary - Diff-based)
    # Fix errors using SEARCH/REPLACE blocks - needs good format compliance
    code_correction: ModelConfig = field(default_factory=lambda: ModelConfig(
        model_name="gemini-2.5-flash",  # Better format compliance than flash-lite
        thinking_level=None,
        description="Diff-based code error correction"
    ))

    # Step 6b: Code Correction (Strong Fallback)
    # Fix errors when primary correction fails - final attempts
    code_correction_strong: ModelConfig = field(default_factory=lambda: ModelConfig(
        model_name="gemini-2.5-flash",  # Same model, used on retries
        thinking_level=ThinkingLevel.MEDIUM,  # Enable thinking for complex fixes
        description="Stronger model for complex code fixes"
    ))

    # Step 7: Visual Quality Control
    # Analyze rendered videos for visual issues
    visual_qc: ModelConfig = field(default_factory=lambda: ModelConfig(
        model_name="gemini-2.5-flash",
        thinking_level=None,
        description="Fast visual quality analysis"
    ))

    # Step 8: Manual Code Fix
    # User-requested code improvements via API
    manual_code_fix: ModelConfig = field(default_factory=lambda: ModelConfig(
        model_name="gemini-3-flash-preview",
        thinking_level=ThinkingLevel.LOW,
        description="Interactive code fixing"
    ))


# Default pipeline configuration
DEFAULT_PIPELINE_MODELS = PipelineModels()


# Alternative configurations for different use cases

# High Quality - Use stronger models with more thinking
HIGH_QUALITY_PIPELINE = PipelineModels(
    analysis=ModelConfig(
        model_name="gemini-2.5-flash",
        thinking_level=None,
        description="Higher quality analysis"
    ),
    script_generation=ModelConfig(
        model_name="gemini-3-pro-preview",
        thinking_level=ThinkingLevel.HIGH,
        description="Deep reasoning for script generation"
    ),
    language_detection=ModelConfig(
        model_name="gemini-flash-lite-latest",
        thinking_level=None,
        description="Quick language detection"
    ),
    translation=ModelConfig(
        model_name="gemini-2.5-flash",
        thinking_level=None,
        description="Higher quality translation"
    ),
    visual_script_generation=ModelConfig(
        model_name="gemini-3-pro-preview",
        thinking_level=ThinkingLevel.MEDIUM,
        description="Detailed visual script generation"
    ),
    manim_generation=ModelConfig(
        model_name="gemini-3-pro-preview",
        thinking_level=ThinkingLevel.MEDIUM,
        description="High quality Manim generation",
        max_correction_attempts=3
    ),
    code_correction=ModelConfig(
        model_name="gemini-2.5-flash",
        thinking_level=None,
        description="Fast code correction"
    ),
    code_correction_strong=ModelConfig(
        model_name="gemini-3-pro-preview",
        thinking_level=ThinkingLevel.HIGH,
        description="Deep reasoning for complex fixes"
    ),
    visual_qc=ModelConfig(
        model_name="gemini-2.5-flash",
        thinking_level=None,
        description="Better visual analysis"
    ),
    manual_code_fix=ModelConfig(
        model_name="gemini-3-pro-preview",
        thinking_level=ThinkingLevel.MEDIUM,
        description="High quality code fixes"
    ),
)


# Cost Optimized - Use cheapest models everywhere
COST_OPTIMIZED_PIPELINE = PipelineModels(
    analysis=ModelConfig(
        model_name="gemini-flash-lite-latest",
        description="Budget analysis"
    ),
    script_generation=ModelConfig(
        model_name="gemini-3-flash-preview",
        thinking_level=ThinkingLevel.LOW,
        description="Cost-effective script generation"
    ),
    language_detection=ModelConfig(
        model_name="gemini-flash-lite-latest",
        description="Quick language detection"
    ),
    translation=ModelConfig(
        model_name="gemini-flash-lite-latest",
        description="Budget translation"
    ),
    visual_script_generation=ModelConfig(
        model_name="gemini-2.0-flash",
        description="Budget visual script generation",
    ),
    manim_generation=ModelConfig(
        model_name="gemini-2.0-flash",
        description="Budget Manim generation",
        max_correction_attempts=3
    ),
    code_correction=ModelConfig(
        model_name="gemini-2.0-flash",
        max_correction_attempts=3,
        description="Budget code correction"
    ),
    code_correction_strong=ModelConfig(
        model_name="gemini-2.0-flash",
        description="Fallback code correction"
    ),
    visual_qc=ModelConfig(
        model_name="gemini-flash-lite-latest",
        description="Budget visual QC"
    ),
    manual_code_fix=ModelConfig(
        model_name="gemini-2.5-flash",
        description="Budget code fixes"
    ),
)


# Overview Mode Optimized - Use cheaper models for simpler overview videos
# This saves ~85% on LLM costs for overview mode while maintaining acceptable quality
OVERVIEW_OPTIMIZED_PIPELINE = PipelineModels(
    analysis=ModelConfig(
        model_name="gemini-flash-lite-latest",
        description="Fast analysis for overview"
    ),
    script_generation=ModelConfig(
        model_name="gemini-flash-lite-latest",  # Much cheaper for simpler scripts
        thinking_level=None,
        description="Cost-effective overview script generation"
    ),
    language_detection=ModelConfig(
        model_name="gemini-flash-lite-latest",
        description="Quick language detection"
    ),
    translation=ModelConfig(
        model_name="gemini-flash-lite-latest",
        description="Budget translation"
    ),
    visual_script_generation=ModelConfig(
        model_name="gemini-2.5-flash",  # Simpler visual scripts for overview
        thinking_level=None,
        description="Budget visual script generation"
    ),
    manim_generation=ModelConfig(
        model_name="gemini-2.5-flash",  # Simpler animations for overview
        thinking_level=None,
        description="Budget Manim generation",
        max_correction_attempts=3
    ),
    code_correction=ModelConfig(
        model_name="gemini-flash-lite-latest",
        description="Budget code correction"
    ),
    code_correction_strong=ModelConfig(
        model_name="gemini-2.5-flash",
        description="Fallback code correction"
    ),
    visual_qc=ModelConfig(
        model_name="gemini-flash-lite-latest",
        description="Budget visual QC"
    ),
    manual_code_fix=ModelConfig(
        model_name="gemini-2.5-flash",
        description="Budget code fixes"
    ),
)


# Current active configuration
# Change this to switch between configurations
ACTIVE_PIPELINE = DEFAULT_PIPELINE_MODELS

# Available pipeline configurations
AVAILABLE_PIPELINES = {
    "default": DEFAULT_PIPELINE_MODELS,
    "high_quality": HIGH_QUALITY_PIPELINE,
    "cost_optimized": COST_OPTIMIZED_PIPELINE,
    "overview": OVERVIEW_OPTIMIZED_PIPELINE,  # Use for overview mode videos
}


def set_active_pipeline(pipeline_name: str) -> None:
    """
    Set the active pipeline configuration.
    
    Args:
        pipeline_name: Name of pipeline configuration ('default', 'high_quality', 'cost_optimized')
    """
    global ACTIVE_PIPELINE
    if pipeline_name not in AVAILABLE_PIPELINES:
        raise ValueError(f"Unknown pipeline: {pipeline_name}. Available: {list(AVAILABLE_PIPELINES.keys())}")
    ACTIVE_PIPELINE = AVAILABLE_PIPELINES[pipeline_name]


def get_active_pipeline_name() -> str:
    """Get the name of the currently active pipeline"""
    for name, pipeline in AVAILABLE_PIPELINES.items():
        if ACTIVE_PIPELINE is pipeline:
            return name
    return "custom"


def get_model_config(step: str, pipeline: Optional[str] = None) -> ModelConfig:
    """
    Get the model configuration for a specific pipeline step.
    
    Args:
        step: Pipeline step name (e.g., 'analysis', 'script_generation')
        pipeline: Optional pipeline name to use instead of active pipeline
        
    Returns:
        ModelConfig for the specified step
    """
    target_pipeline = AVAILABLE_PIPELINES.get(pipeline, ACTIVE_PIPELINE) if pipeline else ACTIVE_PIPELINE
    if hasattr(target_pipeline, step):
        return getattr(target_pipeline, step)
    raise ValueError(f"Unknown pipeline step: {step}")


def get_thinking_config(model_config: ModelConfig):
    """
    Get the thinking configuration for Gemini API calls.
    
    Args:
        model_config: The model configuration
        
    Returns:
        ThinkingConfig dict or None if thinking is not supported
    """
    if model_config.thinking_level and model_config.supports_thinking:
        return {"thinking_level": model_config.thinking_level.value}
    return None


def list_pipeline_steps() -> list[str]:
    """List all available pipeline step names"""
    return [
        "analysis",
        "script_generation",
        "language_detection",
        "translation",
        "visual_script_generation",
        "manim_generation",
        "code_correction",
        "code_correction_strong",
        "visual_qc",
        "manual_code_fix",
    ]
