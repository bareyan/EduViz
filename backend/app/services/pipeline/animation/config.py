"""
Animation Pipeline Configuration

Centralized configuration for animation generation constants and settings.
"""

# =============================================================================
# GENERATION SETTINGS
# =============================================================================

# Maximum iterations for surgical fixes
MAX_SURGICAL_FIX_ATTEMPTS = 5

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

# Choreography planning temperature (lower for structured JSON)
CHOREOGRAPHY_TEMPERATURE = 0.3

# Surgical fix temperature (keep low to reduce JSON drift)
FIX_TEMPERATURE = 0.2

# Chunked choreography: max segments per call
CHOREOGRAPHY_MAX_SEGMENTS_PER_CALL = 3

# Output token limits (32k to reduce truncation)
CHOREOGRAPHY_MAX_OUTPUT_TOKENS = 32768
IMPLEMENTATION_MAX_OUTPUT_TOKENS = 32768


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

# Minimum duration padding at end of animation (seconds)
MIN_DURATION_PADDING = 0.5

# Duration padding percentage (disabled)
DURATION_PADDING_PERCENTAGE = 0.0

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
