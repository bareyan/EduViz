"""
Animation Pipeline Configuration

Centralized configuration for animation generation constants and settings.
"""

# =============================================================================
# GENERATION SETTINGS
# =============================================================================

# Maximum iterations for surgical fixes
MAX_SURGICAL_FIX_ATTEMPTS = 5

# Timeout for correction requests (seconds)
CORRECTION_TIMEOUT = 90  # 1.5 minutes

# Temperature increase per retry attempt
TEMPERATURE_INCREMENT = 0.1

# Base temperature for generation
BASE_GENERATION_TEMPERATURE = 0.7

# Base temperature for correction
BASE_CORRECTION_TEMPERATURE = 0.6

# Temperature bump per correction retry
CORRECTION_TEMPERATURE_STEP = 0.1

# Maximum tokens for refinement responses
MAX_REFINEMENT_OUTPUT_TOKENS = 16384
CHOREOGRAPHY_MAX_OUTPUT_TOKENS = 32768
IMPLEMENTATION_MAX_OUTPUT_TOKENS = 32768


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

# Spatial validation frame limits (Manim coordinate units)
SCREEN_X_LIMIT = 7.1  # Absolute max X coordinate before flagging
SCREEN_Y_LIMIT = 4.0  # Absolute max Y coordinate before flagging
SAFE_X_LIMIT = 5.5  # Recommended safe X for deterministic clamping
SAFE_Y_LIMIT = 3.0  # Recommended safe Y for deterministic clamping

# Issue verification settings
VERIFICATION_BATCH_SIZE = 5  # Max uncertain issues per LLM verification call
VERIFICATION_TEMPERATURE = 0.4  # Low temp for consistent verdicts
VERIFICATION_TIMEOUT = 30.0  # Seconds per verification batch
VERIFICATION_MAX_RETRIES = 1  # Don't waste tokens retrying

# Vision QC settings (verification-only — no auto-fix loop)
ENABLE_VISION_QC = True
VISION_QC_MAX_FRAMES_PER_CALL = 4
VISION_QC_FRAME_WIDTH = 1280
VISION_QC_FRAME_TIME_ROUND = 0.1
VISION_QC_TEMPERATURE = 0.2
VISION_QC_TIMEOUT = 60.0
VISION_QC_MAX_OUTPUT_TOKENS = 2048
VISION_QC_FRAME_DIR_NAME = "frames"

# Error message handling
MAX_ERROR_MESSAGE_LENGTH = 2000  # Max chars for runtime error messages (prevent truncation)

# Theme setup code blocks for code injection
THEME_SETUP_CODES = {
    "light": '        self.camera.background_color = "#FFFFFF"\n',
    "3b1b": '        self.camera.background_color = "#171717"  # Slate dark\n',
    "dark": '        self.camera.background_color = "#171717"  # Slate dark\n',
    # Frontend selectable styles
    "clean": '        self.camera.background_color = "#FFFFFF"\n',
    "dracula": '        self.camera.background_color = "#282A36"\n',
    "solarized": '        self.camera.background_color = "#002B36"\n',
    "nord": '        self.camera.background_color = "#2E3440"\n',
}

# Canonical style aliases to avoid accidental fallback to default theme.
STYLE_ALIASES = {
    "3blue1brown": "3b1b",
    "3b1b": "3b1b",
    "default": "3b1b",
    "dark": "3b1b",
    "light": "clean",
    "clean": "clean",
    "dracula": "dracula",
    "solarized": "solarized",
    "nord": "nord",
}


def normalize_theme_style(style: str) -> str:
    """Normalize external style IDs to canonical theme keys."""
    raw = (style or "").strip().lower()
    if not raw:
        return "3b1b"
    return STYLE_ALIASES.get(raw, raw if raw in THEME_SETUP_CODES else "3b1b")
