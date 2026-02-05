"""
Configuration constants for spatial validation.
"""

SAFETY_MARGIN = 0.2  # How close to the edge is "too close"?
OVERLAP_MARGIN = 0.05  # Overlap buffer
OCCLUSION_MIN_AREA = 0.02  # Minimum overlap area to consider occlusion

MAX_FONT_SIZE = 48
RECOMMENDED_FONT_SIZE = 36
MAX_TEXT_CHARS = 60

PLOT_TYPES = {
    'Axes', 'NumberPlane', 'BarChart', 'Graph', 'Plot',
    'FunctionGraph', 'ParametricFunction'
}

TEXT_TYPES = {
    'Text', 'MathTex', 'Tex', 'Paragraph', 'MarkupText',
    'Title', 'BulletedList', 'Code'
}

CONNECTOR_TYPES = {
    'Arrow', 'DoubleArrow', 'CurvedArrow', 'CurvedDoubleArrow',
    'Line', 'DashedLine', 'Vector', 'Brace', 'Arc', 'ArcBetweenPoints'
}

CONNECTOR_TYPE_HINTS = ("Arrow", "Line", "Vector", "Brace", "Arc")

# Text fully contained within a shape is likely an intentional label.
TEXT_SHAPE_LABEL_CONTAINMENT = 0.75
