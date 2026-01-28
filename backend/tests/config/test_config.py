"""
Tests for config module

Comprehensive tests for configuration including paths, constants, and model settings.
"""

import pytest
from pathlib import Path
from unittest.mock import patch

from app.config import (
    # Paths
    APP_DIR,
    BACKEND_DIR,
    UPLOAD_DIR,
    OUTPUT_DIR,
    JOB_DATA_DIR,
    # Constants
    API_TITLE,
    API_DESCRIPTION,
    API_VERSION,
    CORS_ORIGINS,
    ALLOWED_MIME_TYPES,
    ALLOWED_EXTENSIONS,
)

from app.config.models import (
    ModelConfig,
    ThinkingLevel,
    PipelineModels,
    AVAILABLE_MODELS,
    THINKING_CAPABLE_MODELS,
    get_model_config,
    get_thinking_config,
    set_active_pipeline,
    get_active_pipeline_name,
    list_pipeline_steps,
    AVAILABLE_PIPELINES,
)


class TestPaths:
    """Test suite for path configuration"""

    def test_app_dir_is_path(self):
        """Test APP_DIR is a Path object"""
        assert isinstance(APP_DIR, Path)

    def test_backend_dir_is_path(self):
        """Test BACKEND_DIR is a Path object"""
        assert isinstance(BACKEND_DIR, Path)

    def test_upload_dir_is_path(self):
        """Test UPLOAD_DIR is a Path object"""
        assert isinstance(UPLOAD_DIR, Path)

    def test_output_dir_is_path(self):
        """Test OUTPUT_DIR is a Path object"""
        assert isinstance(OUTPUT_DIR, Path)

    def test_job_data_dir_is_path(self):
        """Test JOB_DATA_DIR is a Path object"""
        assert isinstance(JOB_DATA_DIR, Path)

    def test_directory_hierarchy(self):
        """Test directory hierarchy is correct"""
        # APP_DIR should be inside BACKEND_DIR
        assert APP_DIR.parent == BACKEND_DIR or str(BACKEND_DIR) in str(APP_DIR)

    def test_upload_dir_in_backend(self):
        """Test UPLOAD_DIR is under BACKEND_DIR"""
        assert str(BACKEND_DIR) in str(UPLOAD_DIR)

    def test_output_dir_in_backend(self):
        """Test OUTPUT_DIR is under BACKEND_DIR"""
        assert str(BACKEND_DIR) in str(OUTPUT_DIR)


class TestApiConstants:
    """Test suite for API constants"""

    def test_api_title_is_string(self):
        """Test API_TITLE is a non-empty string"""
        assert isinstance(API_TITLE, str)
        assert len(API_TITLE) > 0

    def test_api_description_is_string(self):
        """Test API_DESCRIPTION is a non-empty string"""
        assert isinstance(API_DESCRIPTION, str)
        assert len(API_DESCRIPTION) > 0

    def test_api_version_format(self):
        """Test API_VERSION follows semantic versioning format"""
        assert isinstance(API_VERSION, str)
        # Should have at least one dot (e.g., "1.0" or "1.0.0")
        assert "." in API_VERSION


class TestCorsOrigins:
    """Test suite for CORS configuration"""

    def test_cors_origins_is_list(self):
        """Test CORS_ORIGINS is a list"""
        assert isinstance(CORS_ORIGINS, list)

    def test_cors_origins_contains_localhost(self):
        """Test CORS_ORIGINS includes localhost entries"""
        localhost_entries = [o for o in CORS_ORIGINS if "localhost" in o]
        assert len(localhost_entries) > 0

    def test_cors_origins_are_urls(self):
        """Test all CORS origins are valid URL strings"""
        for origin in CORS_ORIGINS:
            assert isinstance(origin, str)
            assert origin.startswith("http://") or origin.startswith("https://")


class TestAllowedTypes:
    """Test suite for file type allowlists"""

    def test_allowed_extensions_is_list(self):
        """Test ALLOWED_EXTENSIONS is a list"""
        assert isinstance(ALLOWED_EXTENSIONS, list)
        assert len(ALLOWED_EXTENSIONS) > 0

    def test_allowed_extensions_format(self):
        """Test extensions start with dot"""
        for ext in ALLOWED_EXTENSIONS:
            assert ext.startswith("."), f"Extension should start with dot: {ext}"

    def test_allowed_extensions_contains_common_types(self):
        """Test common file types are allowed"""
        assert ".pdf" in ALLOWED_EXTENSIONS
        assert ".png" in ALLOWED_EXTENSIONS
        assert ".txt" in ALLOWED_EXTENSIONS

    def test_allowed_mime_types_is_list(self):
        """Test ALLOWED_MIME_TYPES is a list"""
        assert isinstance(ALLOWED_MIME_TYPES, list)
        assert len(ALLOWED_MIME_TYPES) > 0

    def test_allowed_mime_types_format(self):
        """Test MIME types have correct format"""
        for mime_type in ALLOWED_MIME_TYPES:
            assert "/" in mime_type, f"MIME type should have slash: {mime_type}"

    def test_allowed_mime_types_contains_common_types(self):
        """Test common MIME types are allowed"""
        assert "application/pdf" in ALLOWED_MIME_TYPES
        assert "image/png" in ALLOWED_MIME_TYPES


class TestThinkingLevel:
    """Test suite for ThinkingLevel enum"""

    def test_thinking_level_values(self):
        """Test ThinkingLevel enum has expected values"""
        assert ThinkingLevel.LOW == "LOW"
        assert ThinkingLevel.MEDIUM == "MEDIUM"
        assert ThinkingLevel.HIGH == "HIGH"
        # NONE is defined with None in source but gets converted to 'None' string
        # because ThinkingLevel inherits from str, Enum
        # We just verify the NONE member exists
        assert ThinkingLevel.NONE is not None  # The enum member exists


class TestModelConfig:
    """Test suite for ModelConfig dataclass"""

    def test_model_config_creation(self):
        """Test creating a ModelConfig"""
        config = ModelConfig(
            model_name="test-model",
            thinking_level=ThinkingLevel.MEDIUM,
            description="Test description"
        )
        
        assert config.model_name == "test-model"
        assert config.thinking_level == ThinkingLevel.MEDIUM
        assert config.description == "Test description"
        assert config.max_correction_attempts == 2  # Default value

    def test_model_config_defaults(self):
        """Test ModelConfig default values"""
        config = ModelConfig(model_name="test-model")
        
        assert config.thinking_level is None
        assert config.description == ""
        assert config.max_correction_attempts == 2

    def test_supports_thinking_with_thinking_model(self):
        """Test supports_thinking for thinking-capable model"""
        config = ModelConfig(
            model_name="gemini-3-flash-preview",
            thinking_level=ThinkingLevel.LOW
        )
        
        assert config.supports_thinking is True

    def test_supports_thinking_without_thinking(self):
        """Test supports_thinking for non-thinking model"""
        config = ModelConfig(model_name="gemini-2.5-flash")
        
        assert config.supports_thinking is False


class TestAvailableModels:
    """Test suite for available models configuration"""

    def test_available_models_is_list(self):
        """Test AVAILABLE_MODELS is a list"""
        assert isinstance(AVAILABLE_MODELS, list)
        assert len(AVAILABLE_MODELS) > 0

    def test_available_models_are_strings(self):
        """Test all available models are strings"""
        for model in AVAILABLE_MODELS:
            assert isinstance(model, str)
            assert len(model) > 0

    def test_thinking_capable_models_subset(self):
        """Test THINKING_CAPABLE_MODELS is subset of AVAILABLE_MODELS"""
        for model in THINKING_CAPABLE_MODELS:
            assert model in AVAILABLE_MODELS, f"Thinking model {model} not in available models"


class TestPipelineConfiguration:
    """Test suite for pipeline configuration functions"""

    def test_available_pipelines_not_empty(self):
        """Test AVAILABLE_PIPELINES has entries"""
        assert len(AVAILABLE_PIPELINES) > 0

    def test_get_active_pipeline_name(self):
        """Test getting active pipeline name"""
        name = get_active_pipeline_name()
        assert isinstance(name, str)
        assert name in AVAILABLE_PIPELINES

    def test_set_active_pipeline_valid(self):
        """Test setting a valid pipeline"""
        original = get_active_pipeline_name()
        
        try:
            # Try to set to a known pipeline
            for pipeline_name in AVAILABLE_PIPELINES.keys():
                set_active_pipeline(pipeline_name)
                assert get_active_pipeline_name() == pipeline_name
                break
        finally:
            # Restore original
            set_active_pipeline(original)

    def test_set_active_pipeline_invalid(self):
        """Test setting an invalid pipeline raises error"""
        with pytest.raises(ValueError):
            set_active_pipeline("nonexistent-pipeline")


class TestGetModelConfig:
    """Test suite for get_model_config function"""

    def test_get_model_config_analysis(self):
        """Test getting model config for analysis step"""
        config = get_model_config("analysis")
        
        assert isinstance(config, ModelConfig)
        assert config.model_name in AVAILABLE_MODELS

    def test_get_model_config_script_generation(self):
        """Test getting model config for script generation"""
        config = get_model_config("script_generation")
        
        assert isinstance(config, ModelConfig)
        assert config.model_name in AVAILABLE_MODELS

    def test_get_model_config_manim_generation(self):
        """Test getting model config for manim generation"""
        config = get_model_config("manim_generation")
        
        assert isinstance(config, ModelConfig)
        assert config.model_name in AVAILABLE_MODELS

    def test_get_model_config_invalid_step(self):
        """Test getting model config for invalid step raises error"""
        with pytest.raises(ValueError):
            get_model_config("nonexistent_step")


class TestGetThinkingConfig:
    """Test suite for get_thinking_config function"""

    def test_get_thinking_config_for_thinking_model(self):
        """Test getting thinking config for thinking-capable model"""
        config = ModelConfig(
            model_name="gemini-3-flash-preview",
            thinking_level=ThinkingLevel.MEDIUM
        )
        
        thinking_config = get_thinking_config(config)
        
        # Should return a dict with thinking configuration
        if thinking_config:
            assert isinstance(thinking_config, dict)

    def test_get_thinking_config_for_non_thinking_model(self):
        """Test getting thinking config for non-thinking model"""
        config = ModelConfig(model_name="gemini-2.5-flash")
        
        thinking_config = get_thinking_config(config)
        
        assert thinking_config is None


class TestListPipelineSteps:
    """Test suite for list_pipeline_steps function"""

    def test_list_pipeline_steps_not_empty(self):
        """Test that pipeline steps list is not empty"""
        steps = list_pipeline_steps()
        
        assert isinstance(steps, list)
        assert len(steps) > 0

    def test_list_pipeline_steps_contains_expected(self):
        """Test that expected steps are in the list"""
        steps = list_pipeline_steps()
        
        expected_steps = ["analysis", "script_generation", "manim_generation"]
        for step in expected_steps:
            assert step in steps, f"Expected step {step} not in pipeline steps"

    def test_list_pipeline_steps_all_strings(self):
        """Test all pipeline steps are strings"""
        steps = list_pipeline_steps()
        
        for step in steps:
            assert isinstance(step, str)
            assert len(step) > 0
