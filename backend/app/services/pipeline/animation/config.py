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

# Base output token budgets (used for ~1 minute sections)
CHOREOGRAPHY_MAX_OUTPUT_TOKENS = 32768
IMPLEMENTATION_MAX_OUTPUT_TOKENS = 32768
OVERVIEW_CHOREOGRAPHY_MAX_OUTPUT_TOKENS = 16384
OVERVIEW_IMPLEMENTATION_MAX_OUTPUT_TOKENS = 16384

# Duration-aware output token scaling
TOKEN_SCALING_BASE_DURATION_SECONDS = 60.0
CHOREOGRAPHY_TOKENS_PER_EXTRA_MINUTE = 8192
IMPLEMENTATION_TOKENS_PER_EXTRA_MINUTE = 8192
OVERVIEW_CHOREOGRAPHY_TOKENS_PER_EXTRA_MINUTE = 4096
OVERVIEW_IMPLEMENTATION_TOKENS_PER_EXTRA_MINUTE = 4096
CHOREOGRAPHY_MAX_OUTPUT_TOKENS_CAP = 65536
IMPLEMENTATION_MAX_OUTPUT_TOKENS_CAP = 65536
OVERVIEW_CHOREOGRAPHY_MAX_OUTPUT_TOKENS_CAP = 32768
OVERVIEW_IMPLEMENTATION_MAX_OUTPUT_TOKENS_CAP = 32768

OVERVIEW_CHOREOGRAPHY_TIMEOUT = 180.0
OVERVIEW_IMPLEMENTATION_TIMEOUT = 180.0


def scale_tokens_for_duration(
    *,
    duration_seconds: float,
    base_tokens: int,
    tokens_per_extra_minute: int,
    max_tokens_cap: int,
    base_duration_seconds: float = TOKEN_SCALING_BASE_DURATION_SECONDS,
) -> int:
    """Scale output tokens based on section duration with a hard cap."""
    safe_duration = max(0.0, float(duration_seconds))
    if safe_duration <= base_duration_seconds:
        return base_tokens

    extra_minutes = (safe_duration - base_duration_seconds) / 60.0
    scaled_tokens = base_tokens + int(round(extra_minutes * tokens_per_extra_minute))
    return min(max_tokens_cap, max(base_tokens, scaled_tokens))


def get_choreography_max_output_tokens(duration_seconds: float, is_overview: bool) -> int:
    """Get duration-aware token budget for choreography generation."""
    if is_overview:
        return scale_tokens_for_duration(
            duration_seconds=duration_seconds,
            base_tokens=OVERVIEW_CHOREOGRAPHY_MAX_OUTPUT_TOKENS,
            tokens_per_extra_minute=OVERVIEW_CHOREOGRAPHY_TOKENS_PER_EXTRA_MINUTE,
            max_tokens_cap=OVERVIEW_CHOREOGRAPHY_MAX_OUTPUT_TOKENS_CAP,
        )

    return scale_tokens_for_duration(
        duration_seconds=duration_seconds,
        base_tokens=CHOREOGRAPHY_MAX_OUTPUT_TOKENS,
        tokens_per_extra_minute=CHOREOGRAPHY_TOKENS_PER_EXTRA_MINUTE,
        max_tokens_cap=CHOREOGRAPHY_MAX_OUTPUT_TOKENS_CAP,
    )


def get_implementation_max_output_tokens(duration_seconds: float, is_overview: bool) -> int:
    """Get duration-aware token budget for implementation generation."""
    if is_overview:
        return scale_tokens_for_duration(
            duration_seconds=duration_seconds,
            base_tokens=OVERVIEW_IMPLEMENTATION_MAX_OUTPUT_TOKENS,
            tokens_per_extra_minute=OVERVIEW_IMPLEMENTATION_TOKENS_PER_EXTRA_MINUTE,
            max_tokens_cap=OVERVIEW_IMPLEMENTATION_MAX_OUTPUT_TOKENS_CAP,
        )

    return scale_tokens_for_duration(
        duration_seconds=duration_seconds,
        base_tokens=IMPLEMENTATION_MAX_OUTPUT_TOKENS,
        tokens_per_extra_minute=IMPLEMENTATION_TOKENS_PER_EXTRA_MINUTE,
        max_tokens_cap=IMPLEMENTATION_MAX_OUTPUT_TOKENS_CAP,
    )


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

# Theme prompt specs for LLM stages (choreographer + implementer)
THEME_PROMPT_SPECS = {
    "3b1b": {
        "display_name": "3Blue1Brown Dark",
        "background": "#171717",
        "primary_text": "#FFFFFF",
        "secondary_text": "#AFC6FF",
        "accents": ["#58C4DD", "#83C167", "#FFC857", "#FF6B6B"],
        "notes": "High-contrast dark style with vibrant accents.",
    },
    "clean": {
        "display_name": "Clean White",
        "background": "#FFFFFF",
        "primary_text": "#111111",
        "secondary_text": "#334155",
        "accents": ["#1D4ED8", "#0F766E", "#D97706", "#DC2626"],
        "notes": "Light theme. Never use white/light text on white background.",
    },
    "dracula": {
        "display_name": "Dracula",
        "background": "#282A36",
        "primary_text": "#F8F8F2",
        "secondary_text": "#BD93F9",
        "accents": ["#8BE9FD", "#50FA7B", "#FFB86C", "#FF5555"],
        "notes": "Dark purple style with bright readable foreground colors.",
    },
    "solarized": {
        "display_name": "Solarized Dark",
        "background": "#002B36",
        "primary_text": "#EEE8D5",
        "secondary_text": "#93A1A1",
        "accents": ["#268BD2", "#2AA198", "#B58900", "#DC322F"],
        "notes": "Warm professional dark style; maintain strong text contrast.",
    },
    "nord": {
        "display_name": "Nord",
        "background": "#2E3440",
        "primary_text": "#ECEFF4",
        "secondary_text": "#D8DEE9",
        "accents": ["#88C0D0", "#A3BE8C", "#EBCB8B", "#BF616A"],
        "notes": "Cool arctic dark style with soft but readable contrast.",
    },
}

# Scene-level text defaults to enforce readability regardless of generated code.
THEME_TEXT_DEFAULT_CODES = {
    "3b1b": (
        '        Text.set_default(color="#FFFFFF")\n'
        '        Tex.set_default(color="#FFFFFF")\n'
        '        MathTex.set_default(color="#FFFFFF")\n'
    ),
    "clean": (
        '        Text.set_default(color="#111111")\n'
        '        Tex.set_default(color="#111111")\n'
        '        MathTex.set_default(color="#111111")\n'
    ),
    "dracula": (
        '        Text.set_default(color="#F8F8F2")\n'
        '        Tex.set_default(color="#F8F8F2")\n'
        '        MathTex.set_default(color="#F8F8F2")\n'
    ),
    "solarized": (
        '        Text.set_default(color="#EEE8D5")\n'
        '        Tex.set_default(color="#EEE8D5")\n'
        '        MathTex.set_default(color="#EEE8D5")\n'
    ),
    "nord": (
        '        Text.set_default(color="#ECEFF4")\n'
        '        Tex.set_default(color="#ECEFF4")\n'
        '        MathTex.set_default(color="#ECEFF4")\n'
    ),
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


def get_theme_prompt_info(style: str) -> str:
    """Return explicit theme instructions for LLM prompts."""
    normalized = normalize_theme_style(style)
    spec = THEME_PROMPT_SPECS.get(normalized, THEME_PROMPT_SPECS["3b1b"])
    accents = ", ".join(spec["accents"])
    return (
        f'{spec["display_name"]}; '
        f'background={spec["background"]}; '
        f'primary_text={spec["primary_text"]}; '
        f'secondary_text={spec["secondary_text"]}; '
        f'accents=[{accents}]; '
        f'notes={spec["notes"]}'
    )
