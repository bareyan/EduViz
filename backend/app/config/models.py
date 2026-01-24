"""
Model Configuration for Pipeline Steps

This module defines all AI models used throughout the video generation pipeline.
Each pipeline step has its own model configuration, allowing for easy tuning
and experimentation with different models.

=== PROVIDER CONFIGURATION ===

Set LLM_PROVIDER environment variable to switch providers:
    - "gemini" : Use Google Gemini API (requires GEMINI_API_KEY)
    - "ollama" : Use local Ollama models (default)

For Ollama, set OLLAMA_HOST if not using default (http://localhost:11434)

=== LOCAL (OLLAMA) MODEL RECOMMENDATIONS ===

For local development, the default configuration uses:
    - deepseek-r1:8b  : General purpose tasks (analysis, script generation, etc.)
    - qwen3:8b        : Code generation (Manim animation code)

These models balance quality and speed on consumer hardware (16GB+ RAM).

=== DEPRECATED/UNUSED FEATURES ===

The following features are currently DEPRECATED or NOT IN USE:
    - Visual QC: Disabled by default. Requires Gemini video analysis.
                 Set ENABLE_VISUAL_QC=true to enable (Gemini only).
    - Translation: Not currently used in the pipeline. Code is maintained
                   for future use but translation features are disabled.

Thinking Levels (for gemini-3-flash-preview and gemini-3-pro-preview):
    - LOW: Minimal reasoning, fastest responses
    - MEDIUM: Balanced reasoning and speed
    - HIGH: Deep reasoning, slower but more accurate
"""

import os
from enum import Enum
from typing import Optional
from dataclasses import dataclass, field


class LLMProviderType(str, Enum):
    """Supported LLM providers"""
    GEMINI = "gemini"
    OLLAMA = "ollama"


def get_active_provider() -> LLMProviderType:
    """Get the active LLM provider from environment
    
    Priority:
    1. Explicit LLM_PROVIDER env var
    2. If GEMINI_API_KEY is set, use Gemini
    3. Default to Ollama (local)
    
    Returns:
        LLMProviderType based on configuration
    """
    provider_env = os.getenv("LLM_PROVIDER", "").lower()
    
    if provider_env == "ollama":
        return LLMProviderType.OLLAMA
    elif provider_env == "gemini":
        return LLMProviderType.GEMINI
    
    # Auto-detect: prefer Gemini if API key exists
    if os.getenv("GEMINI_API_KEY"):
        return LLMProviderType.GEMINI
    
    # Default to local Ollama
    return LLMProviderType.OLLAMA


# Feature flags
ENABLE_VISUAL_QC = os.getenv("ENABLE_VISUAL_QC", "false").lower() == "true"
ENABLE_TRANSLATION = os.getenv("ENABLE_TRANSLATION", "false").lower() == "true"

# Current active provider
ACTIVE_PROVIDER = get_active_provider()


class ThinkingLevel(str, Enum):
    """Thinking budget levels for Gemini 3 models"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    NONE = None  # For models that don't support thinking


@dataclass
class ModelConfig:
    """Configuration for a single model
    
    Supports both Gemini and Ollama models. When using Ollama, the model_name
    will be automatically mapped to an equivalent local model.
    """
    model_name: str  # Primary model name (Gemini)
    ollama_model: Optional[str] = None  # Override for Ollama (if different mapping needed)
    thinking_level: Optional[ThinkingLevel] = None
    description: str = ""
    
    @property
    def supports_thinking(self) -> bool:
        """Check if this model supports thinking configuration"""
        return self.model_name in THINKING_CAPABLE_MODELS
    
    def get_model_for_provider(self, provider: LLMProviderType) -> str:
        """Get the appropriate model name for the given provider
        
        Args:
            provider: The LLM provider type
            
        Returns:
            Model name for the specified provider
        """
        if provider == LLMProviderType.OLLAMA:
            if self.ollama_model:
                return self.ollama_model
            # Use default mapping
            return GEMINI_TO_OLLAMA_MAP.get(self.model_name, "gemma3:12b")
        return self.model_name


# Models that support thinking configuration
THINKING_CAPABLE_MODELS = [
    "gemini-3-flash-preview",
    "gemini-3-pro-preview",
]

# Available Gemini models
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

# Available Ollama models (common choices)
AVAILABLE_OLLAMA_MODELS = [
    # Gemma 3 (Google's open model)
    "gemma3:4b",
    "gemma3:12b",
    "gemma3:27b",
    
    # DeepSeek R1 (strong reasoning)
    "deepseek-r1:1.5b",
    "deepseek-r1:7b",
    "deepseek-r1:8b",   # Recommended: good balance
    "deepseek-r1:14b",
    "deepseek-r1:32b",
    "deepseek-r1:70b",
    
    # Qwen 3 (code-focused, good for Manim)
    "qwen3:8b",         # Recommended for code generation
    "qwen3:14b",
    "qwen3:32b",
    
    # Qwen 2.5 Coder (alternative code models)
    "qwen2.5-coder:7b",
    "qwen2.5-coder:14b",
    "qwen2.5-coder:32b",
    
    # Llama
    "llama3.3:70b",
    
    # Mistral
    "mistral:7b",
]

# Default Ollama models for local usage
# These are the recommended models for running locally
DEFAULT_OLLAMA_GENERAL = "deepseek-r1:8b"   # General purpose tasks
DEFAULT_OLLAMA_CODE = "qwen3:8b"             # Code generation (Manim)

# Mapping from Gemini models to Ollama equivalents
GEMINI_TO_OLLAMA_MAP = {
    # Fast/lite models -> deepseek-r1:8b (general purpose)
    "gemini-flash-lite-latest": DEFAULT_OLLAMA_GENERAL,
    "gemini-2.0-flash-lite": DEFAULT_OLLAMA_GENERAL,
    
    # Flash models -> deepseek-r1:8b (still use 8b for speed)
    "gemini-2.0-flash": DEFAULT_OLLAMA_GENERAL,
    "gemini-2.5-flash": DEFAULT_OLLAMA_GENERAL,
    "gemini-3-flash-preview": DEFAULT_OLLAMA_GENERAL,
    
    # Pro models -> qwen3:8b for code, deepseek for others
    # (code-specific mapping is handled in PipelineModels)
    "gemini-2.5-pro": DEFAULT_OLLAMA_GENERAL,
    "gemini-3-pro-preview": DEFAULT_OLLAMA_CODE,  # Manim generation uses Pro
}


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
    
    # Step 5: Manim Code Generation
    # Generate Manim animation code from script
    manim_generation: ModelConfig = field(default_factory=lambda: ModelConfig(
        model_name="gemini-3-pro-preview",
        thinking_level=ThinkingLevel.HIGH,
        description="Generate Manim animation code"
    ))
    
    # Step 6a: Code Correction (Primary)
    # Fix errors in generated Manim code - first attempts
    code_correction: ModelConfig = field(default_factory=lambda: ModelConfig(
        model_name="gemini-flash-lite-latest",
        thinking_level=None,
        description="Fast code error correction"
    ))
    
    # Step 6b: Code Correction (Strong Fallback)
    # Fix errors when primary correction fails - final attempts
    code_correction_strong: ModelConfig = field(default_factory=lambda: ModelConfig(
        model_name="gemini-3-flash-preview",
        thinking_level=ThinkingLevel.MEDIUM,
        description="Stronger model for complex code fixes"
    ))
    
    # Step 7: Visual Quality Control
    # Analyze rendered videos for visual issues
    visual_qc: ModelConfig = field(default_factory=lambda: ModelConfig(
        model_name="gemini-flash-lite-latest",
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
    manim_generation=ModelConfig(
        model_name="gemini-3-pro-preview",
        thinking_level=ThinkingLevel.MEDIUM,
        description="High quality Manim generation"
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
        thinking_level=None,
        description="Budget analysis"
    ),
    script_generation=ModelConfig(
        model_name="gemini-2.5-flash",
        thinking_level=None,
        description="Cost-effective script generation"
    ),
    language_detection=ModelConfig(
        model_name="gemini-flash-lite-latest",
        thinking_level=None,
        description="Quick language detection"
    ),
    translation=ModelConfig(
        model_name="gemini-flash-lite-latest",
        thinking_level=None,
        description="Budget translation"
    ),
    manim_generation=ModelConfig(
        model_name="gemini-2.5-flash",
        thinking_level=None,
        description="Budget Manim generation"
    ),
    code_correction=ModelConfig(
        model_name="gemini-flash-lite-latest",
        thinking_level=None,
        description="Budget code correction"
    ),
    code_correction_strong=ModelConfig(
        model_name="gemini-2.5-flash",
        thinking_level=None,
        description="Fallback code correction"
    ),
    visual_qc=ModelConfig(
        model_name="gemini-flash-lite-latest",
        thinking_level=None,
        description="Budget visual QC"
    ),
    manual_code_fix=ModelConfig(
        model_name="gemini-2.5-flash",
        thinking_level=None,
        description="Budget code fixes"
    ),
)


def _get_active_pipeline() -> PipelineModels:
    """Get the appropriate pipeline config based on active provider.
    
    Returns:
        OLLAMA_PIPELINE if using Ollama, DEFAULT_PIPELINE_MODELS otherwise
    """
    # Check if OLLAMA_PIPELINE is defined (it's defined later in the file)
    # Use a simple check based on provider
    if ACTIVE_PROVIDER == LLMProviderType.OLLAMA:
        # Return a modified default that will use ollama_model mappings
        return DEFAULT_PIPELINE_MODELS
    return DEFAULT_PIPELINE_MODELS


# Current active configuration
# The actual model selection happens via get_model_for_provider() which
# respects the ollama_model field when ACTIVE_PROVIDER is OLLAMA
ACTIVE_PIPELINE = DEFAULT_PIPELINE_MODELS


def get_model_config(step: str) -> ModelConfig:
    """
    Get the model configuration for a specific pipeline step.
    
    Args:
        step: Pipeline step name (e.g., 'analysis', 'script_generation')
        
    Returns:
        ModelConfig for the specified step
        
    Note:
        For deprecated features (visual_qc, translation), this will still
        return a config but those features should be disabled via
        ENABLE_VISUAL_QC and ENABLE_TRANSLATION flags.
    """
    # Use OLLAMA_PIPELINE if Ollama is active for better local model defaults
    pipeline = OLLAMA_PIPELINE if ACTIVE_PROVIDER == LLMProviderType.OLLAMA else ACTIVE_PIPELINE
    
    if hasattr(pipeline, step):
        return getattr(pipeline, step)
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


def get_model_name(step: str, provider: Optional[LLMProviderType] = None) -> str:
    """
    Get the model name for a pipeline step and provider.
    
    Args:
        step: Pipeline step name
        provider: LLM provider (defaults to ACTIVE_PROVIDER)
        
    Returns:
        Model name appropriate for the provider
    """
    if provider is None:
        provider = ACTIVE_PROVIDER
    
    config = get_model_config(step)
    return config.get_model_for_provider(provider)


# Alias for backwards compatibility
get_model_for_provider = get_model_name


def list_pipeline_steps() -> list[str]:
    """List all available pipeline step names"""
    return [
        "analysis",
        "script_generation", 
        "language_detection",
        "translation",          # DEPRECATED: Not currently in use
        "manim_generation",
        "code_correction",
        "code_correction_strong",
        "visual_qc",            # DEPRECATED: Disabled by default
        "manual_code_fix",
    ]


# Ollama-specific pipeline configuration (RECOMMENDED FOR LOCAL)
# Uses smaller models that run well on consumer hardware (16GB+ RAM)
# - deepseek-r1:8b for general tasks (analysis, scripts, correction)
# - qwen3:8b for code generation (Manim)
OLLAMA_PIPELINE = PipelineModels(
    analysis=ModelConfig(
        model_name="gemini-flash-lite-latest",
        ollama_model="deepseek-r1:8b",
        thinking_level=None,
        description="Fast local analysis with DeepSeek"
    ),
    script_generation=ModelConfig(
        model_name="gemini-3-flash-preview",
        ollama_model="deepseek-r1:8b",
        thinking_level=ThinkingLevel.MEDIUM,
        description="Local script generation with DeepSeek"
    ),
    language_detection=ModelConfig(
        model_name="gemini-flash-lite-latest",
        ollama_model="deepseek-r1:8b",
        thinking_level=None,
        description="Quick language detection"
    ),
    # DEPRECATED: Translation not currently used
    translation=ModelConfig(
        model_name="gemini-flash-lite-latest",
        ollama_model="deepseek-r1:8b",
        thinking_level=None,
        description="[DEPRECATED] Translation - not in use"
    ),
    manim_generation=ModelConfig(
        model_name="gemini-3-pro-preview",
        ollama_model="qwen3:8b",  # Qwen is better for code
        thinking_level=ThinkingLevel.HIGH,
        description="Manim code generation with Qwen (code-optimized)"
    ),
    code_correction=ModelConfig(
        model_name="gemini-flash-lite-latest",
        ollama_model="qwen3:8b",  # Use Qwen for code fixes too
        thinking_level=None,
        description="Fast code correction with Qwen"
    ),
    code_correction_strong=ModelConfig(
        model_name="gemini-3-flash-preview",
        ollama_model="qwen3:8b",
        thinking_level=ThinkingLevel.MEDIUM,
        description="Strong code fixes with Qwen"
    ),
    # DEPRECATED: Visual QC disabled by default
    visual_qc=ModelConfig(
        model_name="gemini-flash-lite-latest",
        ollama_model="deepseek-r1:8b",
        thinking_level=None,
        description="[DEPRECATED] Visual QC - disabled, requires Gemini"
    ),
    manual_code_fix=ModelConfig(
        model_name="gemini-3-flash-preview",
        ollama_model="qwen3:8b",
        thinking_level=ThinkingLevel.LOW,
        description="Interactive code fixing with Qwen"
    ),
)
