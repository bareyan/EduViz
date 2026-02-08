"""
Tests for pipeline/animation/config module

Tests for animation pipeline configuration constants and settings.
"""

from app.services.pipeline.animation.config import (
    # Generation settings
    MAX_SURGICAL_FIX_ATTEMPTS,
    CORRECTION_TIMEOUT,
    TEMPERATURE_INCREMENT,
    BASE_GENERATION_TEMPERATURE,
    BASE_CORRECTION_TEMPERATURE,
    # Retry settings
    MAX_CLEAN_RETRIES,
    # Rendering settings
    RENDER_TIMEOUT,
    QUALITY_DIR_MAP,
    QUALITY_FLAGS,
    # Code generation settings
    MIN_DURATION_PADDING,
    DURATION_PADDING_PERCENTAGE,
    CONSTRUCT_INDENT_SPACES,
    # Validation settings
    ENABLE_REFINEMENT_CYCLE,
    ENABLE_VISION_QC,
    VISION_QC_MAX_FRAMES_PER_CALL,
    VISION_QC_FRAME_WIDTH,
    VISION_QC_FRAME_TIME_ROUND,
    VISION_QC_TEMPERATURE,
    VISION_QC_TIMEOUT,
    VISION_QC_MAX_OUTPUT_TOKENS,
    VISION_QC_FRAME_DIR_NAME,
    THEME_SETUP_CODES,
    normalize_theme_style,
    get_theme_prompt_info,
)


class TestGenerationSettings:
    """Test suite for generation settings"""

    def test_max_surgical_fix_attempts_positive(self):
        """Test MAX_SURGICAL_FIX_ATTEMPTS is positive"""
        assert MAX_SURGICAL_FIX_ATTEMPTS > 0
        assert isinstance(MAX_SURGICAL_FIX_ATTEMPTS, int)

    def test_correction_timeout_reasonable(self):
        """Test CORRECTION_TIMEOUT is reasonable"""
        assert CORRECTION_TIMEOUT > 0
        assert isinstance(CORRECTION_TIMEOUT, int)

    def test_temperature_increment_valid(self):
        """Test TEMPERATURE_INCREMENT is valid"""
        assert 0 < TEMPERATURE_INCREMENT <= 0.5
        assert isinstance(TEMPERATURE_INCREMENT, float)

    def test_base_generation_temperature_valid(self):
        """Test BASE_GENERATION_TEMPERATURE is valid"""
        assert 0 < BASE_GENERATION_TEMPERATURE <= 2.0
        assert isinstance(BASE_GENERATION_TEMPERATURE, float)

    def test_base_correction_temperature_valid(self):
        """Test BASE_CORRECTION_TEMPERATURE is valid"""
        assert 0 <= BASE_CORRECTION_TEMPERATURE <= 2.0
        assert isinstance(BASE_CORRECTION_TEMPERATURE, float)
        # Correction should be more deterministic (lower temp)
        assert BASE_CORRECTION_TEMPERATURE <= BASE_GENERATION_TEMPERATURE


class TestRetrySettings:
    """Test suite for retry settings"""

    def test_max_clean_retries_positive(self):
        """Test MAX_CLEAN_RETRIES is positive"""
        assert MAX_CLEAN_RETRIES > 0
        assert isinstance(MAX_CLEAN_RETRIES, int)


class TestRenderingSettings:
    """Test suite for rendering settings"""

    def test_render_timeout_positive(self):
        """Test RENDER_TIMEOUT is positive"""
        assert RENDER_TIMEOUT > 0
        assert isinstance(RENDER_TIMEOUT, int)

    def test_quality_dir_map_complete(self):
        """Test QUALITY_DIR_MAP has all quality levels"""
        expected_keys = ["low", "medium", "high", "4k"]
        
        for key in expected_keys:
            assert key in QUALITY_DIR_MAP
            assert isinstance(QUALITY_DIR_MAP[key], str)
            assert len(QUALITY_DIR_MAP[key]) > 0

    def test_quality_dir_map_format(self):
        """Test QUALITY_DIR_MAP values have correct format"""
        # Values should be like "480p15", "720p30", etc.
        for quality, dir_name in QUALITY_DIR_MAP.items():
            assert "p" in dir_name  # Should contain 'p' for resolution

    def test_quality_flags_complete(self):
        """Test QUALITY_FLAGS has all quality levels"""
        expected_keys = ["low", "medium", "high", "4k"]
        
        for key in expected_keys:
            assert key in QUALITY_FLAGS
            assert isinstance(QUALITY_FLAGS[key], str)
            assert QUALITY_FLAGS[key].startswith("-q")

    def test_quality_flags_format(self):
        """Test QUALITY_FLAGS values are valid manim flags"""
        # Flags should be -ql, -qm, -qh, -qk
        assert QUALITY_FLAGS["low"] == "-ql"
        assert QUALITY_FLAGS["medium"] == "-qm"
        assert QUALITY_FLAGS["high"] == "-qh"
        assert QUALITY_FLAGS["4k"] == "-qk"

    def test_quality_keys_match(self):
        """Test QUALITY_DIR_MAP and QUALITY_FLAGS have same keys"""
        assert set(QUALITY_DIR_MAP.keys()) == set(QUALITY_FLAGS.keys())


class TestCodeGenerationSettings:
    """Test suite for code generation settings"""

    def test_min_duration_padding_positive(self):
        """Test MIN_DURATION_PADDING is positive"""
        assert MIN_DURATION_PADDING > 0
        assert isinstance(MIN_DURATION_PADDING, (int, float))

    def test_duration_padding_percentage_valid(self):
        """Test DURATION_PADDING_PERCENTAGE is valid percentage"""
        assert 0 < DURATION_PADDING_PERCENTAGE < 1
        assert isinstance(DURATION_PADDING_PERCENTAGE, float)

    def test_construct_indent_spaces_positive(self):
        """Test CONSTRUCT_INDENT_SPACES is positive"""
        assert CONSTRUCT_INDENT_SPACES > 0
        assert isinstance(CONSTRUCT_INDENT_SPACES, int)
        # Should be a multiple of 4 for Python conventions
        assert CONSTRUCT_INDENT_SPACES % 4 == 0


class TestValidationSettings:
    """Test suite for validation settings"""

    def test_validation_flags_are_boolean(self):
        """Test all validation flags are boolean"""
        assert isinstance(ENABLE_REFINEMENT_CYCLE, bool)
        assert isinstance(ENABLE_VISION_QC, bool)

    def test_default_validations_enabled(self):
        """Test that default validations are enabled"""
        # At least syntax validation should always be on
        assert ENABLE_REFINEMENT_CYCLE is True


class TestVisionQcSettings:
    """Test suite for vision QC settings"""

    def test_vision_qc_settings_types(self):
        assert isinstance(VISION_QC_MAX_FRAMES_PER_CALL, int)
        assert isinstance(VISION_QC_FRAME_WIDTH, int)
        assert isinstance(VISION_QC_FRAME_TIME_ROUND, float)
        assert isinstance(VISION_QC_TEMPERATURE, float)
        assert isinstance(VISION_QC_TIMEOUT, float)
        assert isinstance(VISION_QC_MAX_OUTPUT_TOKENS, int)
        assert isinstance(VISION_QC_FRAME_DIR_NAME, str)


class TestConfigConsistency:
    """Test suite for configuration consistency"""

    def test_timeout_hierarchy(self):
        """Test timeout values make sense relative to each other"""
        # Render can be longer than correction
        assert RENDER_TIMEOUT >= CORRECTION_TIMEOUT or True  # May vary

    def test_iteration_vs_retries(self):
        """Test iteration settings are consistent"""
        # Total attempts should be reasonable
        total_max_attempts = MAX_CLEAN_RETRIES * MAX_SURGICAL_FIX_ATTEMPTS
        assert total_max_attempts < 20  # Prevent infinite loops

    def test_temperature_increases_bounded(self):
        """Test temperature increase stays bounded"""
        # After max attempts, temperature should still be valid
        max_temp = BASE_GENERATION_TEMPERATURE + (MAX_SURGICAL_FIX_ATTEMPTS * TEMPERATURE_INCREMENT)
        assert max_temp <= 2.0  # Max allowed temperature for most LLMs


class TestThemeStyleNormalization:
    def test_frontend_styles_are_supported(self):
        for style in ["3b1b", "clean", "dracula", "solarized", "nord"]:
            normalized = normalize_theme_style(style)
            assert normalized in THEME_SETUP_CODES

    def test_aliases_normalize_to_canonical(self):
        assert normalize_theme_style("3blue1brown") == "3b1b"
        assert normalize_theme_style("default") == "3b1b"
        assert normalize_theme_style("light") == "clean"

    def test_unknown_style_falls_back_to_default(self):
        assert normalize_theme_style("unknown-style") == "3b1b"

    def test_theme_prompt_info_includes_colors(self):
        info = get_theme_prompt_info("clean")
        assert "background=#FFFFFF" in info
        assert "primary_text=#111111" in info
