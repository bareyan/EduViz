"""
Animation Pipeline Configuration

Centralized configuration for animation generation constants and settings.
"""

# =============================================================================
# GENERATION SETTINGS
# =============================================================================

# Maximum iterations for surgical fixes
MAX_SURGICAL_FIX_ATTEMPTS = 3

# Timeout for generation requests (seconds)
GENERATION_TIMEOUT = 300  # 5 minutes

# Timeout for correction requests (seconds)
CORRECTION_TIMEOUT = 90  # 1.5 minutes

# Temperature increase per retry attempt
TEMPERATURE_INCREMENT = 0.1

# Base temperature for generation
BASE_GENERATION_TEMPERATURE = 0.7

# Base temperature for correction
BASE_CORRECTION_TEMPERATURE = 0.1

# Temperature bump per correction retry
CORRECTION_TEMPERATURE_STEP = 0.05

# Maximum tokens for refinement responses
MAX_REFINEMENT_OUTPUT_TOKENS = 8192

# Prompt sizing and snippet extraction limits
MAX_PROMPT_CODE_CHARS = 8000
SNIPPET_CONTEXT_RADIUS = 6
SNIPPET_MAX_LINES = 220
HEAD_TAIL_LINES = 120

# LLM retry policy for JSON responses
MAX_JSON_RETRIES = 2


# =============================================================================
# RETRY SETTINGS
# =============================================================================

# Maximum times to retry section generation with clean start
MAX_CLEAN_RETRIES = 2


# =============================================================================
# RENDERING SETTINGS
# =============================================================================

# Manim render timeout per section (seconds)
RENDER_TIMEOUT = 300  # 5 minutes

# Quality settings to Manim output directory mapping
QUALITY_DIR_MAP = {
    "low": "480p15",
    "medium": "720p30",
    "high": "1080p60",
    "4k": "2160p60"
}

# Quality flags for Manim CLI
QUALITY_FLAGS = {
    "low": "-ql",
    "medium": "-qm",
    "high": "-qh",
    "4k": "-qk"
}


# =============================================================================
# CODE GENERATION SETTINGS
# =============================================================================

# Minimum duration padding at end of animation (seconds or percentage)
MIN_DURATION_PADDING = 3.0

# Duration padding percentage (25% of total duration)
DURATION_PADDING_PERCENTAGE = 0.25

# Base indentation level for construct() method body (spaces)
CONSTRUCT_INDENT_SPACES = 8


# =============================================================================
# VALIDATION SETTINGS
# =============================================================================

# Master switch to enable/disable refinement cycle validation
ENABLE_REFINEMENT_CYCLE = True

# Timeout for validation operations (seconds)
VALIDATION_TIMEOUT = 30

# Tool availability flags (set to False to skip specific tools)
REQUIRE_PYRIGHT = False  # Pyright is optional (requires Node.js: npm install -g pyright)
REQUIRE_RUFF = True  # Ruff is required for syntax validation

# Enable/disable specific validators
ENABLE_SYNTAX_VALIDATION = True
ENABLE_STRUCTURE_VALIDATION = True
ENABLE_IMPORTS_VALIDATION = True
ENABLE_SPATIAL_VALIDATION = True

# Theme setup code blocks for code injection
THEME_SETUP_CODES = {
    "light": '        self.camera.background_color = "#FFFFFF"\n',
    "3b1b": '        self.camera.background_color = "#171717"  # Slate dark\n',
    "dark": '        self.camera.background_color = "#171717"  # Slate dark\n'
}

# Fast configuration for validation engine (no video output)
VALIDATION_RENDER_CONFIG = {
    "write_to_movie": False,
    "save_last_frame": False,
    "preview": False,
    "verbosity": "CRITICAL",
    "renderer": "cairo",
    "frame_rate": 1,
    "pixel_width": 320,
    "pixel_height": 180,
    "quality": "low_quality",
    "skip_animations": True
}
