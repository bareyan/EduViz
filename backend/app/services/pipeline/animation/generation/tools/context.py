"""
Manim Context - Reference material for code generation

Contains:
- Manim API reference (constants, methods)
- Style configurations (colors, themes)
- Animation type guidance
- Common patterns and examples
"""

from typing import Dict
from dataclasses import dataclass


# =============================================================================
# MANIM VERSION AND API REFERENCE
# =============================================================================

MANIM_VERSION = "0.18.1"

MANIM_API_REFERENCE = """
## MANIM CE {version} - QUICK REFERENCE

### DIRECTION CONSTANTS (NO "BOTTOM" or "TOP"):
- UP, DOWN, LEFT, RIGHT (unit vectors)
- UL, UR, DL, DR (diagonals: upper-left, upper-right, etc.)
- ORIGIN (center point)

### COLOR CONSTANTS (UPPERCASE only):
- RED, GREEN, BLUE, YELLOW, WHITE, BLACK, GRAY
- ORANGE, PURPLE, PINK, TEAL, GOLD
- Variants: BLUE_A through BLUE_E

### POSITIONING:
- obj.to_edge(UP/DOWN/LEFT/RIGHT, buff=0.5)
- obj.to_corner(UL/UR/DL/DR, buff=0.5)
- obj.next_to(other, RIGHT, buff=0.25)
- obj.move_to(ORIGIN), obj.shift(UP * 2)

### TEXT:
- Text("content", font_size=24) for regular text
- MathTex(r"\\frac{{a}}{{b}}") for LaTeX math
- Title: font_size=36 max

### ANIMATIONS:
- FadeIn, FadeOut, Write, Create, Uncreate
- Transform, ReplacementTransform
- self.play(anim, run_time=1.0)
- self.wait(1.0) - must be positive!

### TIMING RULES:
- run_time must be > 0 (use max(0.1, value))
- self.wait() must be > 0
- Total animation should match target duration

### COMMON PATTERNS:
```python
# Title at top
title = Text("Title", font_size=36).to_edge(UP)
self.play(Write(title))

# Bullet points
points = VGroup(
    Text("• Point 1", font_size=24),
    Text("• Point 2", font_size=24),
).arrange(DOWN, aligned_edge=LEFT, buff=0.3)
points.next_to(title, DOWN, buff=0.5)

# Equation with steps
eq1 = MathTex(r"x^2 + 2x + 1")
eq2 = MathTex(r"(x + 1)^2")
self.play(Write(eq1))
self.wait(0.5)
self.play(ReplacementTransform(eq1, eq2))

# Clean up before new content
self.play(FadeOut(VGroup(*self.mobjects)))
```
""".format(version=MANIM_VERSION)


# =============================================================================
# STYLE CONFIGURATIONS
# =============================================================================

@dataclass
class StyleConfig:
    """Visual style configuration"""
    name: str
    background: str
    text_color: str
    primary_color: str
    secondary_color: str
    accent_colors: list
    description: str


STYLES: Dict[str, StyleConfig] = {
    "3b1b": StyleConfig(
        name="3Blue1Brown",
        background="#1C1C1C",
        text_color="WHITE",
        primary_color="BLUE",
        secondary_color="YELLOW",
        accent_colors=["GREEN", "RED", "ORANGE"],
        description="Dark theme inspired by 3Blue1Brown videos"
    ),
    "clean": StyleConfig(
        name="Clean Light",
        background="WHITE",
        text_color="BLACK",
        primary_color="BLUE",
        secondary_color="GREEN",
        accent_colors=["RED", "ORANGE"],
        description="Light professional theme"
    ),
    "dracula": StyleConfig(
        name="Dracula",
        background="#282a36",
        text_color="#f8f8f2",
        primary_color="#bd93f9",
        secondary_color="#8be9fd",
        accent_colors=["#ff79c6", "#50fa7b"],
        description="Dracula dark purple theme"
    ),
}


def get_style_config(style: str) -> StyleConfig:
    """Get style configuration by name"""
    return STYLES.get(style, STYLES["3b1b"])


def get_style_instructions(style: str) -> str:
    """Get style instructions for prompt"""
    config = get_style_config(style)
    return f"""
STYLE: {config.name}
- Background: {config.background} (pre-configured, do NOT set)
- Text color: {config.text_color}
- Primary accent: {config.primary_color}
- Secondary accent: {config.secondary_color}
- Other accents: {', '.join(config.accent_colors)}
"""


def get_theme_setup_code(style: str = "3b1b") -> str:
    """Return scene background setup snippet for a given style"""
    config = get_style_config(style)

    if style == "3b1b" or config.background.startswith("#"):
        bg_color = config.background.replace("#", "")
        return f'''        # Theme: {config.name}
        self.camera.background_color = "#{bg_color}"'''

    if style == "clean":
        return '''        # Theme: Clean Light
        self.camera.background_color = WHITE'''

    return '''        # Theme: Default Dark
        self.camera.background_color = "#1C1C1C"'''


# =============================================================================
# ANIMATION TYPE GUIDANCE
# =============================================================================

ANIMATION_GUIDANCE = {
    "equation": """
EQUATION ANIMATION:
- Use MathTex(r"\\frac{{a}}{{b}}") for all math
- Scale equations: .scale(0.7) for normal, .scale(0.6) for long
- Transform step-by-step with ReplacementTransform
- Highlight terms with Indicate() or set_color()
- Wait between steps for narration sync
""",
    
    "text": """
TEXT ANIMATION:
- Text("content", font_size=24) - never exceed 28 for body
- Titles: font_size=36 (max 40)
- Build bullet points with VGroup + arrange(DOWN, buff=0.3)
- Fade in points one by one
- Max 4-5 lines visible at once
- FadeOut old content before adding new
""",
    
    "diagram": """
DIAGRAM ANIMATION:
- Shapes: Circle(), Square(), Rectangle(), Arrow(), Line()
- Group with VGroup, position with arrange() or next_to()
- Animate creation: Create() for shapes, GrowArrow() for arrows
- Label with Text(font_size=20).next_to(shape, DOWN)
- Keep diagrams compact: max 8 units wide
""",
    
    "graph": """
GRAPH ANIMATION:
- Axes(x_range=[-4, 4], y_range=[-3, 3], x_length=7, y_length=4)
- Keep graphs smaller than full screen!
- Plot: graph = axes.plot(lambda x: x**2, color=BLUE)
- Labels: axes.get_x_axis_label(), get_y_axis_label()
- Animate with Create(graph)
""",
    
    "code": """
CODE ANIMATION:
- Code() mobject for syntax highlighting OR
- Text("code", font="Monospace", font_size=20)
- Highlight lines by changing color
- Max 8-10 lines visible
- Build incrementally if showing construction
""",
}


def get_animation_guidance(animation_type: str) -> str:
    """Get guidance for specific animation type"""
    return ANIMATION_GUIDANCE.get(animation_type, ANIMATION_GUIDANCE["text"])


# =============================================================================
# LANGUAGE CONFIGURATION
# =============================================================================

LANGUAGE_CONFIGS = {
    "en": {"name": "English", "direction": "ltr", "font": None},
    "es": {"name": "Spanish", "direction": "ltr", "font": None},
    "fr": {"name": "French", "direction": "ltr", "font": None},
    "de": {"name": "German", "direction": "ltr", "font": None},
    "zh": {"name": "Chinese", "direction": "ltr", "font": "Noto Sans SC"},
    "ja": {"name": "Japanese", "direction": "ltr", "font": "Noto Sans JP"},
    "ko": {"name": "Korean", "direction": "ltr", "font": "Noto Sans KR"},
    "ar": {"name": "Arabic", "direction": "rtl", "font": "Noto Sans Arabic"},
    "he": {"name": "Hebrew", "direction": "rtl", "font": "Noto Sans Hebrew"},
    "ru": {"name": "Russian", "direction": "ltr", "font": None},
    "hy": {"name": "Armenian", "direction": "ltr", "font": "Noto Sans Armenian"},
}


def get_language_instructions(language: str) -> str:
    """Get language-specific instructions for text rendering"""
    config = LANGUAGE_CONFIGS.get(language, LANGUAGE_CONFIGS["en"])
    
    instructions = f"LANGUAGE: {config['name']} ({language})\n"
    
    if config["font"]:
        instructions += f'- Use font="{config["font"]}" for Text() objects\n'
    
    if config["direction"] == "rtl":
        instructions += "- Text direction is right-to-left\n"
        instructions += "- Use .flip(RIGHT) if needed for proper display\n"
    
    return instructions


# =============================================================================
# COMPLETE CONTEXT FOR GENERATION
# =============================================================================

@dataclass
class ManimContext:
    """Complete context for Manim code generation"""
    api_reference: str
    style_instructions: str
    animation_guidance: str
    target_duration: float
    language: str
    
    def to_system_prompt(self) -> str:
        """Convert to system prompt for LLM"""
        return f"""You are an expert Manim animator. Generate clean, working Manim CE code.

{self.api_reference}

{self.style_instructions}

{self.animation_guidance}

TARGET DURATION: {self.target_duration} seconds
LANGUAGE: {self.language}

OUTPUT: Generate ONLY the construct() method body. No class definition, no imports.
Ensure animations are timed to match the target duration.
"""


def get_manim_reference() -> str:
    """Get complete Manim API reference"""
    return MANIM_API_REFERENCE


def build_context(
    style: str = "3b1b",
    animation_type: str = "text",
    target_duration: float = 30.0,
    language: str = "en"
) -> ManimContext:
    """Build complete context for generation"""
    return ManimContext(
        api_reference=get_manim_reference(),
        style_instructions=get_style_instructions(style),
        animation_guidance=get_animation_guidance(animation_type),
        target_duration=target_duration,
        language=language
    )
