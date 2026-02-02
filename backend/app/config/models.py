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

    # Step 5: Animation Pipeline (New)
    # Stage 5.1: Choreography Planning
    animation_choreography: ModelConfig = field(default_factory=lambda: ModelConfig(
        model_name="gemini-3-flash-preview",
        thinking_level=ThinkingLevel.HIGH,
        description="Plan visual movements and timing"
    ))

    # Stage 5.2: Manim Code Implementation
    animation_implementation: ModelConfig = field(default_factory=lambda: ModelConfig(
        model_name="gemini-3-flash-preview",
        thinking_level=ThinkingLevel.MEDIUM,
        description="Convert plan to Manim code"
    ))

    # Stage 5.3: Animation Refinement (Checks & Fixes)
    animation_refinement: ModelConfig = field(default_factory=lambda: ModelConfig(
        model_name="gemini-2.5-flash",
        thinking_level=ThinkingLevel.LOW,
        description="Refine code and fix errors"
    ))


# Default and only pipeline configuration
DEFAULT_PIPELINE_MODELS = PipelineModels()


def get_model_config(step: str) -> ModelConfig:
    """
    Get the model configuration for a specific pipeline step.
    
    Args:
        step: Pipeline step name (e.g., 'analysis', 'script_generation')
        
    Returns:
        ModelConfig for the specified step
    """
    if hasattr(DEFAULT_PIPELINE_MODELS, step):
        return getattr(DEFAULT_PIPELINE_MODELS, step)
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
        "animation_choreography",
        "animation_implementation",
        "animation_refinement",
        "visual_qc",
    ]
