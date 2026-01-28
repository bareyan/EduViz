"""
Visual Script Generation Configuration

Centralized configuration for visual script generation constants and settings.
"""

# =============================================================================
# GENERATION SETTINGS
# =============================================================================

# Timeout for visual script generation requests (seconds)
GENERATION_TIMEOUT = 120.0  # 2 minutes

# Temperature for generation (lower = more deterministic)
GENERATION_TEMPERATURE = 0.3

# Max retries for generation
MAX_GENERATION_RETRIES = 3


# =============================================================================
# TIMING SETTINGS
# =============================================================================

# Default post-narration pause (seconds)
# Used when the visual description is simple and matches audio timing
DEFAULT_POST_PAUSE = 0.0

# Minimum post-narration pause (seconds)
MIN_POST_PAUSE = 0.0

# Maximum post-narration pause (seconds)
# Prevents excessively long pauses
MAX_POST_PAUSE = 5.0

# Threshold for "complex" animations that need extra pause (seconds)
# If estimated animation time exceeds audio + this threshold, add pause
COMPLEX_ANIMATION_THRESHOLD = 2.0


# =============================================================================
# VISUAL STYLE GUIDELINES
# =============================================================================

# Default animation style keywords
SUPPORTED_VISUAL_ELEMENTS = [
    # Geometric shapes
    "Circle", "Square", "Rectangle", "Triangle", "Polygon", "Line", "Arrow",
    "Dot", "Ellipse", "Arc", "Sector", "Annulus",
    
    # Text and Math
    "Text", "MathTex", "Tex", "Title", "BulletList", "Paragraph",
    
    # Graphs and plots
    "NumberLine", "Axes", "NumberPlane", "ParametricCurve", "FunctionGraph",
    "BarChart", "PieChart", "Table",
    
    # Special objects
    "Brace", "SurroundingRectangle", "BackgroundRectangle", "Cross",
    "VGroup", "ImageMobject", "SVGMobject",
]

# Animation types for guidance
SUPPORTED_ANIMATIONS = [
    # Creation
    "Create", "Write", "DrawBorderThenFill", "ShowCreation", "GrowFromCenter",
    "GrowFromEdge", "GrowFromPoint", "SpinInFromNothing",
    
    # Fading
    "FadeIn", "FadeOut", "FadeInFrom", "FadeOutAndShift",
    
    # Transforms
    "Transform", "ReplacementTransform", "TransformFromCopy", "MoveToTarget",
    "ApplyMethod", "Rotate", "ScaleInPlace",
    
    # Indication
    "Indicate", "Flash", "Circumscribe", "ShowPassingFlash", "Wiggle",
    "FocusOn", "ApplyWave",
    
    # Movement
    "MoveAlongPath", "Homotopy", "ApplyPointwiseFunction",
    
    # Updaters
    "UpdateFromFunc", "UpdateFromAlphaFunc",
]

# Color palette for visual elements
SUPPORTED_COLORS = [
    "RED", "BLUE", "GREEN", "YELLOW", "ORANGE", "PURPLE", "PINK",
    "TEAL", "GOLD", "MAROON", "WHITE", "GREY", "BLACK",
    "LIGHT_GREY", "DARK_GREY", "LIGHT_BLUE", "DARK_BLUE",
]

# Position keywords
POSITION_KEYWORDS = [
    "UP", "DOWN", "LEFT", "RIGHT", "UL", "UR", "DL", "DR",
    "ORIGIN", "CENTER", "to_edge", "to_corner", "next_to",
]
