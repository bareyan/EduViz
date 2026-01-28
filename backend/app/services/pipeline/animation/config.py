"""
Animation Pipeline Configuration

Centralized configuration for animation generation constants and settings.
"""

# =============================================================================
# GENERATION SETTINGS
# =============================================================================

# Maximum iterations for tool-based code generation/fixing
MAX_GENERATION_ITERATIONS = 5

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


# =============================================================================
# RETRY SETTINGS
# =============================================================================

# Maximum times to retry section generation with clean start
MAX_CLEAN_RETRIES = 2

# Maximum correction attempts before clean retry
MAX_CORRECTION_ATTEMPTS = 3


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

# Enable/disable specific validators
ENABLE_SYNTAX_VALIDATION = True
ENABLE_STRUCTURE_VALIDATION = True
ENABLE_IMPORTS_VALIDATION = True
ENABLE_SPATIAL_VALIDATION = True
