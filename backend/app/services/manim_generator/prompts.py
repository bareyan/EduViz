"""
Prompt templates and language instructions for Manim code generation
"""

from typing import Dict, Any, List, Optional

# Style-specific color palettes (background is enforced at scene level)
STYLE_COLOR_PALETTES = {
    '3b1b': {
        'colors': """
COLOR PALETTE (3Blue1Brown dark theme - background is pre-set):
- Text: WHITE (default) - no need to specify
- Primary accent: BLUE
- Secondary accent: YELLOW
- Emphasis: GREEN, RED
- DO NOT set background_color (it's pre-configured)"""
    },
    'clean': {
        'colors': """
COLOR PALETTE (Light theme - WHITE background is pre-set):
- Text: BLACK or DARK_GRAY (REQUIRED for visibility)
- Primary: BLUE
- Secondary: GREEN  
- Emphasis: RED
- DO NOT set background_color (it's pre-configured)
- Example: Text("Title", color=BLACK, font_size=36)"""
    },
    'dracula': {
        'colors': """
COLOR PALETTE (Dracula dark purple - background is pre-set):
- Text: "#f8f8f2" (off-white, REQUIRED)
- Primary: "#bd93f9" (purple)
- Secondary: "#8be9fd" (cyan)
- Emphasis: "#ff79c6" (pink), "#50fa7b" (green)
- DO NOT set background_color (it's pre-configured)"""
    },
    'solarized': {
        'colors': """
COLOR PALETTE (Solarized dark - background is pre-set):
- Text: "#839496" (light gray-blue, REQUIRED)
- Primary: "#268bd2" (blue)
- Secondary: "#2aa198" (cyan)
- Emphasis: "#b58900" (yellow), "#cb4b16" (orange)
- DO NOT set background_color (it's pre-configured)"""
    },
    'nord': {
        'colors': """
COLOR PALETTE (Nord arctic - background is pre-set):
- Text: "#eceff4" (snow white, REQUIRED)
- Primary: "#88c0d0" (frost blue)
- Secondary: "#81a1c1" (steel blue)
- Emphasis: "#bf616a" (aurora red), "#a3be8c" (aurora green)
- DO NOT set background_color (it's pre-configured)"""
    }
}

# Animation type guidance - expanded with more detail
ANIMATION_GUIDANCE = {
    'equation': """EQUATION-FOCUSED ANIMATION:
- Use MathTex for all mathematical expressions: MathTex(r"\\frac{a}{b}").scale(0.7)
- Transform equations step-by-step with ReplacementTransform
- Highlight specific terms with Indicate() or set_color()
- Show derivation steps one at a time
- Use .scale(0.7) for equations, .scale(0.6) for very long ones
- Long equations (>20 chars): split across lines or use smaller scale
- Example flow: Show equation → Highlight term → Transform to next step → Wait for narration""",

    'text': """TEXT-FOCUSED ANIMATION:
- Use Text("content", font_size=24) for regular text (max 28)
- Titles: font_size=36 (never exceed 40)
- Build bullet points with VGroup and .arrange(DOWN, buff=0.5, aligned_edge=LEFT)
- Fade in points one by one to match narration
- Keep titles at top with .to_edge(UP, buff=0.8)
- Don't crowd the screen - max 4-5 lines visible at once
- Split long sentences (>8 words) into multiple lines
- Use FadeOut before adding new content""",

    'diagram': """DIAGRAM/VISUAL ANIMATION:
- Create shapes: Circle(), Square(), Rectangle(), Arrow(), Line()
- Group related elements with VGroup
- Animate connections: GrowArrow for arrows, Create for shapes
- Label components with Text(font_size=20) positioned using .next_to()
- Use consistent spacing with .arrange() or manual positioning
- Consider using Brace for grouping visual elements
- Keep diagrams compact: max 8 units wide, 5 units tall
- Position diagrams slightly below center to leave room for titles""",

    'code': """CODE DISPLAY ANIMATION:
- Use Code() mobject for syntax highlighting OR
- Use Text("code", font="Monospace", font_size=20) for simple code
- Highlight important lines by changing color: line.animate.set_color(YELLOW)
- Build code incrementally if showing construction
- Keep code blocks small - max 8-10 lines
- Position code centrally with good margins""",

    'graph': """GRAPH/PLOT ANIMATION:
- Create axes: Axes(x_range=[-4, 4, 1], y_range=[-2.5, 2.5, 1], x_length=7, y_length=4)
- Keep graphs SMALLER than full screen to avoid overflow!
- Plot functions: graph = axes.plot(lambda x: x**2, color=BLUE)
- Label axes with axes.get_x_axis_label(font_size=20) and get_y_axis_label()
- Animate graph creation: Create(graph) with run_time matching narration
- Add points of interest with Dot() and small labels (font_size=18)
- Position graphs in center-lower area to leave room for title""",

    'process': """PROCESS/FLOW ANIMATION:
- Create stages as shapes or text boxes (font_size=24)
- Connect with arrows: Arrow(start, end)
- Reveal stages sequentially to match narration
- Use consistent left-to-right or top-to-bottom flow
- Highlight current stage while dimming others
- Group stage+arrow pairs for easier animation
- Keep process compact - max 4-5 stages visible""",

    'comparison': """COMPARISON ANIMATION:
- Divide screen: LEFT_SIDE and RIGHT_SIDE for two items
- Use consistent styling for comparable elements
- Animate alternating reveals
- Use SurroundingRectangle to highlight differences
- Add clear labels (font_size=24) for each side
- Keep visual balance between compared items""",

    'static': """STATIC SCENE (minimal animation):
- Display text/equations that STAY on screen while narrator explains
- Use simple FadeIn animations, then long self.wait() calls
- NO complex transformations - let the narration do the explaining
- Example: Show title (font_size=36) → show bullet points (font_size=24) → self.wait(5.0)
- 80% of duration should be self.wait() while content is displayed
- Clear content between major topic changes only""",

    'mixed': """MIXED SCENE (balance of static and animated):
- Start with static elements (title font_size=36, context font_size=24)
- Add animated elements for key points only
- Balance: 40% animation, 60% static display with waits
- Animate equations and diagrams, keep text mostly static
- Use self.wait() generously between animations"""
}

# Non-Latin script languages
NON_LATIN_SCRIPTS = {
    'hy': 'Armenian',
    'ar': 'Arabic',
    'he': 'Hebrew',
    'zh': 'Chinese',
    'ja': 'Japanese',
    'ko': 'Korean',
    'ru': 'Russian',
    'el': 'Greek',
    'th': 'Thai',
    'hi': 'Hindi',
    'bn': 'Bengali',
    'ta': 'Tamil',
    'te': 'Telugu',
    'ml': 'Malayalam',
    'kn': 'Kannada',
    'gu': 'Gujarati',
    'pa': 'Punjabi',
    'mr': 'Marathi',
}

# Theme configurations for background colors
THEME_CONFIGS = {
    '3b1b': {
        'background': None,  # Default dark background
        'comment': '3Blue1Brown dark theme (default Manim)'
    },
    'clean': {
        'background': 'WHITE',
        'comment': 'Clean/Light theme'
    },
    'dracula': {
        'background': '"#282a36"',
        'comment': 'Dracula dark purple theme'
    },
    'solarized': {
        'background': '"#002b36"',
        'comment': 'Solarized dark theme'
    },
    'nord': {
        'background': '"#2e3440"',
        'comment': 'Nord arctic theme'
    }
}


def get_language_instructions(language: str) -> str:
    """Get language-specific instructions for Manim code generation"""
    
    if language in NON_LATIN_SCRIPTS:
        script_name = NON_LATIN_SCRIPTS[language]
        return f"""
════════════════════════════════════════════════════════════════════════════════
⚠️  {script_name.upper()} TEXT HANDLING - CRITICAL RULES
════════════════════════════════════════════════════════════════════════════════

This content uses {script_name} script. Follow these rules STRICTLY:

1. NEVER mix {script_name} text with LaTeX in the same MathTex object
2. Use Text() for ALL {script_name} text: Text("text here", font_size=24)
3. Use MathTex() ONLY for pure math symbols: MathTex(r"x^2 + y^2").scale(0.7)
4. Position text and math as SEPARATE objects using .next_to()

FONT SIZES for {script_name} (smaller than Latin text to prevent overflow):
- Titles: font_size=30
- Body text: font_size=22
- Labels/captions: font_size=18
- Add .scale(0.75) if content is wide

CORRECT PATTERN:
        # Title in {script_name}
        title = Text("Title Here", font_size=30)
        title.to_edge(UP, buff=0.5)
        self.play(Write(title))
        
        # Math equation (universal symbols only)
        eq = MathTex(r"x = 2").scale(0.7)
        eq.move_to(ORIGIN)
        self.play(Write(eq))
        
        # Explanation in {script_name}
        label = Text("Explanation text", font_size=22)
        label.next_to(eq, DOWN, buff=0.6)
        self.play(FadeIn(label))

WRONG (DO NOT DO):
        # NEVER put {script_name} text in MathTex
        wrong = MathTex(r"\\text{{{script_name} text}}")  # ❌ WILL FAIL
"""
    elif language != 'en':
        # Latin script but non-English (French, German, Spanish, etc.)
        return f"""
════════════════════════════════════════════════════════════════════════════════
NOTE: NON-ENGLISH LATIN TEXT
════════════════════════════════════════════════════════════════════════════════
Text is in a non-English language with accented characters.

Rules:
- Text() handles accented characters correctly: Text("Théorème", font_size=32)
- MathTex is ONLY for mathematical notation: MathTex(r"\\frac{{x}}{{y}}").scale(0.7)
- NEVER put non-math words inside MathTex - it will fail on accented chars
- Keep math and text as separate objects positioned with .next_to()
- Use smaller fonts to accommodate longer words: font_size=24 for body text
"""
    else:
        return ""  # No special instructions for English


def get_color_instructions(style: str) -> str:
    """Get color palette instructions for a given style"""
    style_palette = STYLE_COLOR_PALETTES.get(style, STYLE_COLOR_PALETTES['3b1b'])
    return style_palette['colors']


def get_animation_guidance(animation_type: str) -> str:
    """Get animation guidance for a given type"""
    return ANIMATION_GUIDANCE.get(animation_type, ANIMATION_GUIDANCE['text'])


def get_theme_setup_code(style: str) -> str:
    """Get the theme setup code that runs at the start of construct()"""
    config = THEME_CONFIGS.get(style, THEME_CONFIGS['3b1b'])
    
    if config['background']:
        return f'''        # === THEME: {config['comment']} ===
        self.camera.background_color = {config['background']}
'''
    else:
        return f'''        # === THEME: {config['comment']} ===
'''


# ════════════════════════════════════════════════════════════════════════════════
# TWO-SHOT GENERATION: VISUAL SCRIPT → MANIM CODE
# ════════════════════════════════════════════════════════════════════════════════

def build_visual_script_prompt(
    section: Dict[str, Any],
    audio_duration: float,
    timing_context: str
) -> str:
    """Build prompt for Shot 1: Generate detailed visual script/storyboard"""
    
    title = section.get('title', 'Untitled')
    narration = section.get('narration', section.get('tts_narration', ''))
    visual_description = section.get('visual_description', '')
    animation_type = section.get('animation_type', 'text')
    key_concepts = section.get('key_concepts', section.get('key_equations', []))
    
    # Format key concepts
    if isinstance(key_concepts, list) and key_concepts:
        concepts_str = "\n".join(f"  - {c}" for c in key_concepts)
    elif key_concepts:
        concepts_str = f"  - {key_concepts}"
    else:
        concepts_str = "  (None specified)"
    
    return f"""You are an expert educational video storyboard designer. Create a detailed VISUAL SCRIPT for a Manim animation.

════════════════════════════════════════════════════════════════════════════════
SECTION INFORMATION
════════════════════════════════════════════════════════════════════════════════
Title: {title}
Animation Type: {animation_type}
Total Duration: {audio_duration:.1f} seconds

Visual Description:
{visual_description if visual_description else 'Create appropriate visuals for the narration.'}

Key Concepts to Visualize:
{concepts_str}

════════════════════════════════════════════════════════════════════════════════
NARRATION WITH TIMING
════════════════════════════════════════════════════════════════════════════════
{timing_context}

Full Narration:
{narration}

════════════════════════════════════════════════════════════════════════════════
⚠️ CRITICAL LAYOUT & PACING RULES
════════════════════════════════════════════════════════════════════════════════
1. **SAFE ZONE**: All content MUST fit within x=[-6, +6], y=[-3, +3].
   - **Header/Footer**: Reserve y > 3.0 for Titles, y < -3.0 for subtitles.
   - **Body**: Main content goes in the center box (-6 to +6, -3 to +3).

2. **AVOID CLUTTER**:
   - MAX 4 visual elements (groups/equations) on screen at once.
   - If new content arrives and screen is full -> **CLEAN UP** (`FadeOut`) old content first!
   - **Sequential Display**: Do NOT dump everything at once. Reveal step-by-step.

3. **TEXT SIZE LIMITS** (SMALLER TO PREVENT OVERFLOW):
   - Titles: font_size=36 (max 40)
   - Body text: font_size=24 (max 28)
   - Labels: font_size=20
   - MathTex: scale=0.7 (use 0.65 for equations with >10 symbols)
   - Split long sentences into multiple short lines (Max 6-8 words per line).
   - NEVER place text on top of equations or visual elements.
   - Use `next_to(prev_obj, DOWN)` to naturally flow content.

4. **BOUNDING BOX REALISM**:
   - Text(size 36) is TALLER than you think (~0.5 units).
   - MathTex(size 48) is WIDE. 
   - Always assume objects are 20% larger than minimum to be safe.

5. **MATH vs TEXT**:
   - Variables ($x$, $y$, $\\alpha$) MUST be `MathTex`.
   - Normal words MUST be `Text`.
   - Never write `Text("alpha")` -> Use `MathTex(r"\\alpha")`.

════════════════════════════════════════════════════════════════════════════════
YOUR TASK: Create a Visual Script with Object Lifecycle Tracking
════════════════════════════════════════════════════════════════════════════════

⚠️ **CRITICAL NEW REQUIREMENT: USE TIME VARIABLES, NOT HARDCODED SECONDS!** ⚠️

Instead of writing hardcoded times like "0.0s", "3.5s", "8.2s" scattered throughout,
you will define meaningful TIME VARIABLES and only calculate their actual values at the
bottom of the visual script. This makes timing adjustments much easier!

**Example Time Variables:**
- `segment_1_begin`, `segment_1_end`
- `title_appear`, `title_hide`
- `example_intro`, `example_complete`
- `diagram_build_start`, `diagram_build_end`
- `transition_to_next`, `section_end`

For each time segment, specify:

1. **NARRATION SCRIPT**: Full narration text with TIME VARIABLES
   - Start and end time for each spoken phrase using variables
   - Sync points between narration and visuals

2. **OBJECTS with LIFECYCLE**: Each object MUST include:
   - **id**: Unique identifier (e.g., obj_1, title_main, eq_bias)
   - **type**: Text, MathTex, Shape, Diagram, Graph, Circle, Arrow, etc.
   - **content**: Exact text/equation/shape specification
   - **size**: font_size or scale factor (keep text ≤36, equations scale ≤0.85)
   - **position**: Center point (x, y) coordinates
   - **bounding_box**: Approximate bounds as (x_min, y_min, x_max, y_max)
   - **appear_at**: TIME VARIABLE when object first becomes visible (e.g., `title_appear`)
   - **hide_at**: TIME VARIABLE when object should be removed (e.g., `title_hide`, or "end" if visible until end)

3. **POSITIONS**: Where each object is placed (CRITICAL!)
   - Use exact (x, y) coordinates for center point
   - Calculate bounding box based on content size
   - NEVER place objects outside safe zone!

4. **ANIMATIONS**: How objects appear/transform (use TIME VARIABLES)
   - Entry: FadeIn, Write, Create, GrowFromCenter
   - Transform: ReplacementTransform, morph
   - Exit: FadeOut (ALWAYS clear before adding new overlapping content!)
   - **Duration**: Specify run_time for each animation

5. **SPACING**: Gaps between elements
   - Minimum vertical gap: 0.6-0.8 units
   - Minimum horizontal gap: 0.5-0.6 units

════════════════════════════════════════════════════════════════════════════════
BOUNDING BOX ESTIMATION GUIDE (CRITICAL FOR AVOIDING OVERFLOW!)
════════════════════════════════════════════════════════════════════════════════
Estimate bounding boxes based on content - BE CONSERVATIVE (assume larger):
- Text (font_size 24): ~0.35 units height, ~0.06 units width per character
- Text (font_size 28): ~0.40 units height, ~0.07 units width per character
- Text (font_size 36): ~0.50 units height, ~0.09 units width per character
- MathTex (scale 0.7): ~0.7-1.0 units height, ~0.20 units per symbol
- MathTex (scale 0.65): ~0.6-0.9 units height, ~0.18 units per symbol
- Circle: radius defines bounds, box is (cx-r, cy-r, cx+r, cy+r)
- Arrow: box from start point to end point with 0.3 unit padding
- Axes/Graphs: typically need 8x5 units minimum, center carefully!

⚠️ OVERFLOW PREVENTION:
- Long equations (>15 symbols at scale 0.7): Use scale 0.6 or split
- Text >40 characters: Split into multiple lines
- Graphs/diagrams: Reserve center area (-4, -2.5) to (4, 2.5)
- Keep titles SHORT (max 30 chars) or use smaller font_size=32

For position (cx, cy) and estimated (width, height):
  bounding_box = (cx - width/2, cy - height/2, cx + width/2, cy + height/2)

════════════════════════════════════════════════════════════════════════════════
OUTPUT FORMAT
════════════════════════════════════════════════════════════════════════════════

Use this exact format with TIME VARIABLES instead of hardcoded seconds:

---
VISUAL SCRIPT: {title}
TOTAL DURATION: {audio_duration:.1f}s
---

## SEGMENT 1: [segment_1_begin - segment_1_end]

### Narration Script:
```
[phrase_1_begin - phrase_1_end] "First phrase of narration..."
[phrase_2_begin - phrase_2_end] "Second phrase continues..."
```

### Objects:
| id | type | content | size | position (cx, cy) | bounding_box (x_min, y_min, x_max, y_max) | appear_at | hide_at |
|----|------|---------|------|-------------------|-------------------------------------------|-----------|---------|
| title_1 | Text | "Title Here" | 36 | (0, 3.2) | (-2.0, 3.0, 2.0, 3.4) | title_appear | title_hide |
| eq_main | MathTex | "E[X] = \\mu" | 0.7 | (0, 1.5) | (-1.2, 1.1, 1.2, 1.9) | eq_appear | end |
| arrow_1 | Arrow | from (a,b) to (c,d) | - | (mid_x, mid_y) | (a, min(b,d), c, max(b,d)) | arrow_appear | arrow_hide |

### Actions:
- [title_appear] Write(title_1) | run_time: 1.5s
- [eq_appear] FadeIn(eq_main) | run_time: 1.0s
- [arrow_appear] GrowArrow(arrow_1) | run_time: 1.0s
- [hold_visuals] self.wait(3.8s)

### Layout notes: Any spacing/positioning considerations

---

## SEGMENT 2: [segment_2_begin - segment_2_end]

### Narration Script:
```
[phrase_3_begin - phrase_3_end] "Narration for this segment..."
```

### Cleanup:
- [cleanup_segment_1] FadeOut(title_1, arrow_1) | run_time: 1.0s

### Objects:
| id | type | content | size | position (cx, cy) | bounding_box (x_min, y_min, x_max, y_max) | appear_at | hide_at |
|----|------|---------|------|-------------------|-------------------------------------------|-----------|---------|
...

### Actions:
...

---

(Continue for all segments)

---
## OBJECT LIFECYCLE SUMMARY
| id | type | appear_at | hide_at | notes |
|----|------|-----------|---------|-------|
| title_1 | Text | title_appear | title_hide | Main title |
| eq_main | MathTex | eq_appear | end | Stays visible |
...
---

════════════════════════════════════════════════════════════════════════════════
⚠️ CRITICAL: TIME VARIABLE DEFINITIONS (DEFINED AT THE BOTTOM!)
════════════════════════════════════════════════════════════════════════════════
At the END of your visual script, provide ALL time variable definitions in seconds.
This is the ONLY place where actual numeric times appear!

**TIME VARIABLE DEFINITIONS:**

```python
# Segment boundaries
segment_1_begin = 0.0
segment_1_end = 8.8

segment_2_begin = 8.8
segment_2_end = 18.5

# Individual event times
title_appear = 0.0
title_hide = 8.8

phrase_1_begin = 0.0
phrase_1_end = 2.5

phrase_2_begin = 2.5
phrase_2_end = 5.0

eq_appear = 3.0
arrow_appear = 4.0
arrow_hide = 8.8

hold_visuals = 5.0
cleanup_segment_1 = 8.8

# Add more variables as needed...

# Total duration check
total_duration = {audio_duration:.1f}
assert segment_N_end == total_duration, "Timeline must match total duration!"
```

**BENEFITS OF THIS APPROACH:**
1. Easy to adjust timing - change one variable, everything updates
2. Clear semantic meaning - `title_appear` is more readable than `0.0s`
3. Prevents timing conflicts - can see all times in one place
4. Easier debugging - can verify timeline consistency
5. Better for code generation - variables translate directly to Python

---
## REMOVAL SCHEDULE (derived from hide_at times)
This section helps track when objects should be cleaned up:

REMOVAL SCHEDULE (sorted chronologically by variable):
- [title_hide] FadeOut: title_1, arrow_1
- [eq_hide] FadeOut: eq_main, diagram_1  
- [cleanup_final] FadeOut: bullet_group
- [end] Objects still visible at end: eq_final, conclusion_text

---

---
FINAL TIMING CHECK:
- Total animation time: (sum of all run_times)
- Total wait time: (sum of all waits)
- Combined: {audio_duration:.1f}s ✓
- All time variables defined: ✓
---

⚠️ REMEMBER: 
- Use TIME VARIABLES everywhere, NEVER hardcoded seconds in the segments!
- Define ALL time variables at the bottom with actual numeric values
- Be VERY SPECIFIC about positions and bounding boxes.
- Ensure NO overlaps and NO off-screen content.
- Track every object's full lifecycle from appearance to removal.
- The TIME VARIABLE DEFINITIONS section is MANDATORY!"""


# Schema for structured visual script analysis output
def get_visual_script_analysis_schema():
    """Returns the JSON schema for visual script spatial analysis.
    
    This is used with Gemini's structured output feature for reliable parsing.
    """
    try:
        from google import genai
        
        return genai.types.Schema(
            type=genai.types.Type.OBJECT,
            required=["status", "issues_found", "fixes"],
            properties={
                "status": genai.types.Schema(
                    type=genai.types.Type.STRING,
                    description="Overall status: 'ok' if no issues, 'needs_fixes' if issues found",
                    enum=["ok", "needs_fixes"]
                ),
                "issues_found": genai.types.Schema(
                    type=genai.types.Type.INTEGER,
                    description="Total number of spatial issues detected"
                ),
                "fixes": genai.types.Schema(
                    type=genai.types.Type.ARRAY,
                    description="List of fixes/considerations for the Manim code generator. Empty if status is 'ok'.",
                    items=genai.types.Schema(
                        type=genai.types.Type.OBJECT,
                        required=["object_id", "issue_type", "severity", "description", "fix_instruction"],
                        properties={
                            "object_id": genai.types.Schema(
                                type=genai.types.Type.STRING,
                                description="ID of the object with the issue (from visual script)"
                            ),
                            "issue_type": genai.types.Schema(
                                type=genai.types.Type.STRING,
                                description="Type of issue detected",
                                enum=["overflow_left", "overflow_right", "overflow_top", "overflow_bottom", "overlap", "too_large", "spacing_tight"]
                            ),
                            "severity": genai.types.Schema(
                                type=genai.types.Type.STRING,
                                description="How critical the issue is",
                                enum=["critical", "warning"]
                            ),
                            "description": genai.types.Schema(
                                type=genai.types.Type.STRING,
                                description="Brief description of what's wrong"
                            ),
                            "fix_instruction": genai.types.Schema(
                                type=genai.types.Type.STRING,
                                description="Specific instruction for fixing: e.g., 'move to (x, y)', 'reduce scale to 0.7', 'add buff=0.8 between objects'"
                            ),
                            "affects_objects": genai.types.Schema(
                                type=genai.types.Type.ARRAY,
                                description="Other object IDs affected (for overlaps)",
                                items=genai.types.Schema(type=genai.types.Type.STRING)
                            ),
                            "time_range": genai.types.Schema(
                                type=genai.types.Type.STRING,
                                description="Time range when issue occurs, e.g., '5.0s - 12.0s'"
                            )
                        }
                    )
                )
            }
        )
    except ImportError:
        return None


def build_visual_script_analysis_prompt(
    visual_script: str,
    audio_duration: float
) -> str:
    """Build prompt for quick safety check of visual script spatial layout.
    
    This is a lightweight check that validates the visual script and outputs
    structured JSON with any fixes needed for the Manim code generator.
    """
    
    return f"""You are an expert visual layout validator for Manim animations. Quickly check this visual script for spatial safety issues.

════════════════════════════════════════════════════════════════════════════════
VISUAL SCRIPT TO CHECK
════════════════════════════════════════════════════════════════════════════════
{visual_script}

════════════════════════════════════════════════════════════════════════════════
SAFETY BOUNDARIES
════════════════════════════════════════════════════════════════════════════════
Manim safe zone (objects must stay within):
- HORIZONTAL: x ∈ [-6.0, +6.0]  (frame edge is ±7.1)
- VERTICAL: y ∈ [-3.2, +3.2]  (frame edge is ±4.0)

════════════════════════════════════════════════════════════════════════════════
SIZE REFERENCE (for estimating if content fits)
════════════════════════════════════════════════════════════════════════════════
Text width ≈ 0.15 * font_size/32 * character_count
Text height ≈ 0.45 * font_size/32
MathTex: roughly 0.25 units per symbol, scale factor applies
Long equations (>15 symbols) risk horizontal overflow
Stacked elements need ~0.6-0.8 units vertical spacing

════════════════════════════════════════════════════════════════════════════════
CHECK FOR THESE ISSUES
════════════════════════════════════════════════════════════════════════════════

1. **OVERFLOW**: Object's bounding box extends beyond safe zone
   - Check if position + estimated size exceeds boundaries
   - Long text/equations near edges are high risk

2. **OVERLAP**: Two objects visible at the same time occupy the same space
   - Compare bounding boxes of simultaneously visible objects
   - Ignore if objects are cleaned up before new ones appear

3. **TIGHT SPACING**: Objects too close together (< 0.5 units apart)
   - Check vertical/horizontal gaps between adjacent objects

4. **TOO LARGE**: Content that won't fit even when centered
   - Very long equations or text blocks

════════════════════════════════════════════════════════════════════════════════
OUTPUT
════════════════════════════════════════════════════════════════════════════════

Return JSON with:
- "status": "ok" if everything is safe, "needs_fixes" if issues found
- "issues_found": count of issues
- "fixes": array of fix instructions (empty if status is "ok")

Each fix should include:
- object_id: which object has the issue
- issue_type: overflow_left/right/top/bottom, overlap, too_large, spacing_tight
- severity: "critical" (will definitely cause problems) or "warning" (might be ok)
- description: what's wrong
- fix_instruction: specific fix like "move to (-3.0, 2.0)" or "scale to 0.7"

Be concise. Only report real issues that will cause visual problems."""


def build_code_from_script_prompt(
    section: Dict[str, Any],
    visual_script: str,
    audio_duration: float,
    language_instructions: str,
    color_instructions: str,
    type_guidance: str,
    spatial_fixes: Optional[List[Dict[str, Any]]] = None
) -> str:
    """Build prompt for Shot 2: Generate Manim code from visual script
    
    Args:
        section: Section data
        visual_script: The visual script to implement (with time variables!)
        audio_duration: Target duration in seconds
        language_instructions: Language-specific instructions
        color_instructions: Color/style instructions
        type_guidance: Animation type guidance
        spatial_fixes: Optional list of spatial fixes from analysis phase
    """
    
    title = section.get('title', 'Untitled')
    narration = section.get('narration', section.get('tts_narration', ''))
    
    # Build spatial fixes section if provided
    spatial_fixes_section = ""
    if spatial_fixes and len(spatial_fixes) > 0:
        fixes_text = []
        for fix in spatial_fixes:
            severity = fix.get('severity', 'warning').upper()
            obj_id = fix.get('object_id', 'unknown')
            issue = fix.get('issue_type', 'unknown')
            desc = fix.get('description', '')
            instruction = fix.get('fix_instruction', '')
            fixes_text.append(f"  - [{severity}] {obj_id}: {issue} - {desc}\n    → FIX: {instruction}")
        
        spatial_fixes_section = f"""
════════════════════════════════════════════════════════════════════════════════
⚠️ SPATIAL FIXES REQUIRED (from layout analysis)
════════════════════════════════════════════════════════════════════════════════
The visual script was analyzed and the following issues need to be addressed
when generating code. Apply these fixes to avoid overflow/overlap problems:

{chr(10).join(fixes_text)}

Apply these fixes when positioning objects. The visual script positions may need adjustment.
"""
    
    return f"""You are an expert Manim Community Edition programmer. Generate Python code for the construct(self) method body.

════════════════════════════════════════════════════════════════════════════════
⚠️ CRITICAL: TARGET DURATION = {audio_duration:.1f} SECONDS
════════════════════════════════════════════════════════════════════════════════
Your animation MUST run for EXACTLY {audio_duration:.1f} seconds total.
Sum of all run_time values + all self.wait() calls MUST equal {audio_duration:.1f}s.

⚠️ **NEW: TIMING WITH PYTHON VARIABLES** ⚠️
The visual script uses TIME VARIABLES (e.g., segment_1_begin, title_appear).
You MUST:
1. Extract ALL time variable definitions from the visual script
2. Define them as Python variables at the START of construct()
3. Use these variables for all self.play() and self.wait() timing
4. Calculate wait durations using variable arithmetic (next_time - current_time)

This makes the code easier to read, debug, and adjust!
{spatial_fixes_section}

════════════════════════════════════════════════════════════════════════════════
VISUAL SCRIPT TO IMPLEMENT
════════════════════════════════════════════════════════════════════════════════
Follow this visual script EXACTLY. It specifies all objects, positions, and timing
using TIME VARIABLES that you'll convert to Python variables:

{visual_script}

════════════════════════════════════════════════════════════════════════════════
ORIGINAL NARRATION (for reference)
════════════════════════════════════════════════════════════════════════════════
{narration}

════════════════════════════════════════════════════════════════════════════════
ANIMATION TYPE GUIDANCE
════════════════════════════════════════════════════════════════════════════════
{type_guidance}
{language_instructions}
{color_instructions}

════════════════════════════════════════════════════════════════════════════════
⚠️ CODE STRUCTURE WITH TIME VARIABLES (MANDATORY!)
════════════════════════════════════════════════════════════════════════════════

Your construct() method MUST follow this structure:

```python
def construct(self):
    # === THEME SETUP ===
    # self.camera.background_color = ... (if needed)
    
    # ═══════════════════════════════════════════════════════════════
    # TIMING VARIABLES (extracted from visual script)
    # ═══════════════════════════════════════════════════════════════
    # Define ALL time variables here at the top!
    # This is the ONLY place where numeric time values appear!
    
    # Segment boundaries
    segment_1_begin = 0.0
    segment_1_end = 8.8
    segment_2_begin = 8.8
    segment_2_end = 18.5
    # ... etc.
    
    # Event times
    title_appear = 0.0
    title_hide = 8.8
    eq_appear = 3.0
    arrow_appear = 4.0
    # ... etc.
    
    # Animation durations (for run_time parameters)
    title_write_duration = 1.5
    eq_fade_duration = 1.0
    # ... etc.
    
    # Calculated wait times
    wait_after_title = eq_appear - (title_appear + title_write_duration)
    wait_after_eq = arrow_appear - (eq_appear + eq_fade_duration)
    # ... etc.
    
    # Total duration verification
    total_duration = {audio_duration:.1f}
    # ═══════════════════════════════════════════════════════════════
    
    # === SEGMENT 1 OBJECTS ===
    title_main = Text("Title", font_size=36)
    # ... create all objects
    
    # === SEGMENT 1 ANIMATIONS ===
    # Use variables for timing!
    self.play(Write(title_main), run_time=title_write_duration)
    self.wait(wait_after_title)
    
    self.play(FadeIn(eq_main), run_time=eq_fade_duration)
    self.wait(wait_after_eq)
    
    # === CLEANUP SEGMENT 1 ===
    cleanup_duration = 1.0
    self.play(FadeOut(title_main, arrow_1), run_time=cleanup_duration)
    
    # === SEGMENT 2 OBJECTS ===
    # ... continue pattern
```

**KEY BENEFITS:**
1. **Easy debugging**: See all timing in one place at the top
2. **No magic numbers**: Every time has a meaningful variable name
3. **Automatic wait calculation**: `wait_time = next_event - (current_event + duration)`
4. **Easy adjustments**: Change one variable, timing updates throughout
5. **Prevents object leaks**: Clear tracking of when objects should be cleaned up

════════════════════════════════════════════════════════════════════════════════
⚠️ POSITIONING RULES (CRITICAL - FOLLOW VISUAL SCRIPT POSITIONS!)
════════════════════════════════════════════════════════════════════════════════

Frame boundaries:
- SAFE ZONE: x ∈ [-6.0, +6.0], y ∈ [-3.2, +3.2]

Position translation:
- "top/UP with buff=0.8" → .to_edge(UP, buff=0.8)
- "center" → .move_to(ORIGIN)
- "below X with buff=0.8" → .next_to(X, DOWN, buff=0.8)
- "(x, y)" coordinates → .move_to(np.array([x, y, 0])) or .move_to(RIGHT*x + UP*y)

Spacing rules:
- **AVOID OVERLAPS**: When placing B below A, `B.next_to(A, DOWN, buff=0.8)` is SAFER than manual coordinates.
- ALL .next_to() calls: use `buff=0.8` minimum for vertical stacking.
- ALL .to_edge() calls: use `buff=0.8` minimum.
- ALL .arrange() calls: use `buff=0.5` minimum and `aligned_edge=LEFT` for text lists.

Size rules - STANDARDIZED (SMALLER TO PREVENT OVERFLOW):
- **Titles**: `font_size=36` (max 40, prefer 36)
- **Subtitles/Headers**: `font_size=28`
- **Body Text**: `font_size=24` (never exceed 28)
- **Labels/captions**: `font_size=20`
- **Math Equations**: `MathTex(...).scale(0.7)` (use 0.65 for long equations)

LaTeX vs Text Rules - STRICT ENFORCEMENT:
1. **Math Mode**: ALWAYS use `MathTex(r"...")` for anything that is a variable, number, or formula.
   - ❌ WRONG: `Text("x = 5")`, `Text("alpha")`, `Text("30%")`, `Text("H2O")`, `Text("v_0")`
   - ✅ CORRECT: `MathTex(r"x = 5")`, `MathTex(r"\alpha")`, `MathTex(r"30\%")`, `MathTex(r"H_2O")`, `MathTex(r"v_0")`
   - **MANDATORY**: Even single variables like "x" MUST be `MathTex(r"x")`.
2. **Plain Text**: Use `Text("...")` for descriptions and sentences.
   - Example: `Text("The limit diverges")`
3. **Mixed Content**: 
   - ❌ NEVER mix simple text descriptions with latex symbols in `Text()`.
   - ❌ NEVER put long English sentences in `MathTex()`.
   - ✅ SPLIT THEM: `VGroup(Text("Velocity"), MathTex(r"v_0"), Text("is constant")).arrange(RIGHT)`
   - ✅ `Text()` cannot render LaTeX commands like `\frac`, `^`, `_`, `\alpha`.

════════════════════════════════════════════════════════════════════════════════
COMMON PATTERNS WITH TIME VARIABLES
════════════════════════════════════════════════════════════════════════════════

# Example 1: Sequential animations with calculated waits
title_appear = 0.0
title_write_duration = 1.5
eq_appear = title_appear + title_write_duration + 0.5  # 0.5s gap
eq_fade_duration = 1.0
next_event = eq_appear + eq_fade_duration + 2.0  # 2.0s hold time

title = Text("Title", font_size=36).to_edge(UP, buff=0.8)
self.play(Write(title), run_time=title_write_duration)
self.wait(eq_appear - (title_appear + title_write_duration))

eq = MathTex(r"x^2 + y^2 = r^2").scale(0.75).move_to(ORIGIN)
self.play(FadeIn(eq), run_time=eq_fade_duration)
self.wait(next_event - (eq_appear + eq_fade_duration))

# Example 2: Cleanup with proper timing
cleanup_start = 8.8
cleanup_duration = 0.5
segment_2_begin = cleanup_start + cleanup_duration

self.play(FadeOut(title, eq), run_time=cleanup_duration)
# Now we're at segment_2_begin time

# Example 3: Multiple objects appearing in sequence
obj_1_appear = 2.0
obj_1_duration = 0.8
obj_2_appear = obj_1_appear + obj_1_duration + 0.2
obj_2_duration = 0.8

self.play(FadeIn(obj_1), run_time=obj_1_duration)
self.wait(obj_2_appear - (obj_1_appear + obj_1_duration))
self.play(FadeIn(obj_2), run_time=obj_2_duration)

════════════════════════════════════════════════════════════════════════════════
OBJECT CLEANUP TRACKING (PREVENT LEAKS!)
════════════════════════════════════════════════════════════════════════════════

The visual script contains an "OBJECT LIFECYCLE SUMMARY" and "REMOVAL SCHEDULE".
Use this to ensure you FadeOut objects at the right time!

Pattern:
1. Look at the REMOVAL SCHEDULE in the visual script
2. For each cleanup time variable, collect all objects with that hide_at time
3. FadeOut them together

Example from visual script:
```
REMOVAL SCHEDULE:
- [title_hide] FadeOut: title_1, arrow_1
- [diagram_cleanup] FadeOut: eq_main, diagram_1  
- [end] Objects still visible: conclusion_text
```

Your code:
```python
# At title_hide time
self.play(FadeOut(title_1, arrow_1), run_time=0.5)

# At diagram_cleanup time  
self.play(FadeOut(eq_main, diagram_1), run_time=0.5)

# conclusion_text stays until end (no FadeOut)
```

════════════════════════════════════════════════════════════════════════════════
SYNTAX REQUIREMENTS
════════════════════════════════════════════════════════════════════════════════
- Use 8 spaces for indentation (inside construct body)
- MathTex uses raw strings with double backslashes: r"\\frac{{a}}{{b}}"
- Import numpy as needed: positions like np.array([x, y, 0])

════════════════════════════════════════════════════════════════════════════════
OUTPUT REQUIREMENTS
════════════════════════════════════════════════════════════════════════════════
Output ONLY the Python code for the construct() body.
- NO markdown code blocks (no ```)
- NO explanations
- NO class definition or imports
- Just the indented code that goes inside construct(self)
- MUST start with timing variable definitions!
- VERIFY: Implement ALL segments from the visual script
- VERIFY: Use time variables for ALL timing
- VERIFY: Total duration = {audio_duration:.1f}s"""


def build_timing_context(section: Dict[str, Any], narration_segments: List[Dict]) -> str:
    """Build timing context string from section data and narration segments
    
    IMPORTANT: Includes FULL narration text for each segment, not truncated,
    so Gemini can understand what visuals to create for each timing segment.
    """
    
    is_unified_section = section.get('is_unified_section', False)
    is_segment = section.get('is_segment', False)
    
    # Build subsection timing from narration_segments
    subsection_lines = []
    cumulative_time = 0.0
    for seg in narration_segments:
        seg_duration = seg.get('estimated_duration', seg.get('duration', 7.0))
        start_time = seg.get('start_time', cumulative_time)
        end_time = seg.get('end_time', cumulative_time + seg_duration)
        seg_text = seg.get('text', '')  # Full text, not truncated!
        seg_visual = seg.get('visual_description', '')
        
        line = f"  SEGMENT {len(subsection_lines) + 1}: [{start_time:.1f}s - {end_time:.1f}s] ({seg_duration:.1f}s)"
        if seg_visual:
            line += f"\n    Visual Focus: {seg_visual}"
        line += f"\n    Narration: \"{seg_text}\""
        subsection_lines.append(line)
        cumulative_time = end_time
    
    subsection_timing_str = "\n\n".join(subsection_lines) if subsection_lines else "Single continuous segment"
    
    if is_unified_section:
        # Unified section with multiple segments - use segment_timing if available
        segment_timing = section.get('segment_timing', [])
        if segment_timing:
            timing_lines = []
            for i, s in enumerate(segment_timing):
                line = f"  SEGMENT {i + 1}: [{s['start_time']:.1f}s - {s['end_time']:.1f}s] ({s.get('duration', s['end_time'] - s['start_time']):.1f}s)"
                if s.get('visual_description'):
                    line += f"\n    Visual Focus: {s['visual_description']}"
                # Include FULL narration text
                line += f"\n    Narration: \"{s['text']}\""
                timing_lines.append(line)
            return "\n\n".join(timing_lines)
        return subsection_timing_str
        
    elif is_segment:
        # Individual segment within a larger section
        seg_idx = section.get('segment_index', 0)
        total_segs = section.get('total_segments', 1)
        is_first = seg_idx == 0
        is_last = seg_idx == total_segs - 1
        
        context = f"Segment {seg_idx + 1} of {total_segs}\n"
        if is_first:
            context += "  → This is the FIRST segment: Include section title animation\n"
        else:
            context += "  → Continuation segment: NO title needed, continue from previous\n"
        if is_last:
            context += "  → This is the LAST segment: Include conclusion/summary visual"
        else:
            context += "  → More segments follow: End with content that flows to next"
        return context
    else:
        return subsection_timing_str


def build_generation_prompt(
    section: Dict[str, Any],
    audio_duration: float,
    timing_context: str,
    language_instructions: str,
    color_instructions: str,
    type_guidance: str
) -> str:
    """Build the comprehensive Manim code generation prompt"""
    
    title = section.get('title', 'Untitled')
    narration = section.get('narration', section.get('tts_narration', ''))
    visual_description = section.get('visual_description', '')
    animation_type = section.get('animation_type', 'text')
    key_concepts = section.get('key_concepts', section.get('key_equations', []))
    
    # Format key concepts nicely
    if isinstance(key_concepts, list) and key_concepts:
        concepts_str = "\n".join(f"  - {c}" for c in key_concepts)
    elif key_concepts:
        concepts_str = f"  - {key_concepts}"
    else:
        concepts_str = "  (None specified)"
    
    return f"""You are an expert Manim Community Edition programmer. Generate Python code for the construct(self) method body.

════════════════════════════════════════════════════════════════════════════════
⚠️ CRITICAL: TARGET DURATION = {audio_duration:.1f} SECONDS ⚠️
════════════════════════════════════════════════════════════════════════════════
Your animation MUST run for EXACTLY {audio_duration:.1f} seconds total.
Sum of all run_time values + all self.wait() calls MUST equal {audio_duration:.1f}s.

TIMING CALCULATION EXAMPLE for a {audio_duration:.1f}s video:
- If you have 3 animations with run_time=1.5 each = 4.5s of animation
- You need self.wait() calls totaling {audio_duration:.1f} - 4.5 = {max(0, audio_duration - 4.5):.1f}s
- Distribute waits after each visual to let viewer absorb content

════════════════════════════════════════════════════════════════════════════════
SECTION INFORMATION
════════════════════════════════════════════════════════════════════════════════
Title: {title}
Animation Type: {animation_type}

════════════════════════════════════════════════════════════════════════════════
VISUAL DESCRIPTION
════════════════════════════════════════════════════════════════════════════════
{visual_description if visual_description else 'Create appropriate visuals for the narration below.'}

════════════════════════════════════════════════════════════════════════════════
KEY CONCEPTS TO VISUALIZE
════════════════════════════════════════════════════════════════════════════════
{concepts_str}

════════════════════════════════════════════════════════════════════════════════
NARRATION (sync your animations to this audio timing)
════════════════════════════════════════════════════════════════════════════════
{narration}

════════════════════════════════════════════════════════════════════════════════
⚠️ CRITICAL: TIMING BREAKDOWN - EACH SEGMENT NEEDS MATCHING VISUALS ⚠️
════════════════════════════════════════════════════════════════════════════════
The narration is divided into timed segments below. You MUST:
1. Create DISTINCT visual content for EACH segment
2. Animate/display content at the START TIME of each segment  
3. Use self.wait() to hold content until the segment ends
4. Transition to NEXT segment's content at its start time

{timing_context}

════════════════════════════════════════════════════════════════════════════════
ANIMATION TYPE GUIDANCE
════════════════════════════════════════════════════════════════════════════════
{type_guidance}
{language_instructions}
{color_instructions}

════════════════════════════════════════════════════════════════════════════════
⚠️⚠️⚠️ CRITICAL: LAYOUT & POSITIONING RULES (PREVENTS QC FAILURES) ⚠️⚠️⚠️
════════════════════════════════════════════════════════════════════════════════

The Manim frame is approximately:
- HORIZONTAL: -7.1 to +7.1 (total width ~14.2 units)
- VERTICAL: -4.0 to +4.0 (total height ~8.0 units)
- SAFE ZONE: Stay within -6.0 to +6.0 horizontal, -3.2 to +3.2 vertical

═══ 1. SPACING & OVERLAPS (MOST COMMON ERROR) ═══
ALWAYS use generous buff values to prevent overlapping:
   ✓ .next_to(obj, DOWN, buff=0.8)   # Safe vertical spacing
   ✓ .next_to(obj, RIGHT, buff=0.6)  # Safe horizontal spacing
   ✓ .arrange(DOWN, buff=0.6)        # Safe VGroup arrangement
   ✗ .next_to(obj, DOWN, buff=0.2)   # WILL OVERLAP!
   ✗ .arrange(DOWN, buff=0.3)        # TOO TIGHT!

For VGroups with multiple items:
   bullets = VGroup(*items).arrange(DOWN, buff=0.5, aligned_edge=LEFT)
   bullets.scale_to_fit_height(5.0)  # Constrain to safe height if needed

═══ 2. SCREEN MARGINS (AVOID CUTOFF/OVERFLOW) ═══
Use large buff values for edges to prevent content from going off-screen:
   ✓ .to_edge(UP, buff=0.8)          # Title placement
   ✓ .to_edge(DOWN, buff=0.8)        # Footer placement
   ✓ .to_edge(LEFT, buff=1.0)        # Left margin
   ✓ .to_edge(RIGHT, buff=1.0)       # Right margin
   ✗ .to_edge(UP, buff=0.2)          # TOO CLOSE TO EDGE!
   ✗ .to_corner(UR, buff=0.3)        # WILL BE CUT OFF!

═══ 3. MANDATORY SCALING (PREVENT OVERFLOW) ═══
ALWAYS scale elements BEFORE positioning:
   ✓ MathTex(r"long equation").scale(0.75).move_to(ORIGIN)
   ✓ Text("Title text", font_size=36).to_edge(UP, buff=0.8)
   ✓ equation.scale_to_fit_width(12.0)  # Force fit within safe width

Scale guidelines by content type:
   - Long equations: .scale(0.7) to .scale(0.85)
   - Multi-line text: .scale(0.8) to .scale(0.9)
   - Diagrams/graphs: .scale_to_fit_width(10.0) or .scale_to_fit_height(5.5)
   - Groups with many items: .scale_to_fit_height(5.0)

═══ 4. CONTENT CLEANUP (PREVENT STACKING) ═══
ALWAYS remove old content before adding new to prevent overlaps:
   ✓ self.play(FadeOut(old_content))
     self.play(FadeIn(new_content))
   ✓ self.play(ReplacementTransform(old, new))
   ✓ self.play(*[FadeOut(mob) for mob in self.mobjects])  # Clear all
   ✗ Just adding new content without removing old (causes overlaps!)

═══ 5. SAFE POSITIONING PATTERNS ═══
# Title at top, content in center:
title = Text("Title", font_size=38).to_edge(UP, buff=0.8)
content = MathTex(r"equation").scale(0.8).move_to(ORIGIN)

# Vertical list with proper spacing:
items = VGroup(
    Text("Item 1", font_size=28),
    Text("Item 2", font_size=28),
    Text("Item 3", font_size=28)
).arrange(DOWN, buff=0.6, aligned_edge=LEFT)
items.next_to(title, DOWN, buff=0.8)

# Side-by-side comparison:
left_content.scale(0.8).to_edge(LEFT, buff=1.2)
right_content.scale(0.8).to_edge(RIGHT, buff=1.2)

# Graph with labels:
axes = Axes(x_range=[-3,3,1], y_range=[-2,4,1], x_length=6, y_length=4.5)
axes.scale(0.9).move_to(DOWN * 0.3)  # Slightly below center for labels

═══ 6. SIZE GUIDELINES ═══
- Titles: font_size=36-40 (never larger than 42)
- Body text: font_size=26-32
- Labels: font_size=22-26
- Math equations: Always add .scale(0.75-0.85)
- Axes x_length: 6-8 max, y_length: 4.5-6 max

═══ 7. BEFORE FINALIZING - CHECKLIST ═══
□ Did you scale large elements? (equations, graphs)
□ Did you use buff >= 0.6 for all .next_to() calls?
□ Did you use buff >= 0.8 for all .to_edge() calls?
□ Did you FadeOut old content before adding new?
□ Will all content stay within -6 to +6 horizontal, -3.2 to +3.2 vertical?

════════════════════════════════════════════════════════════════════════════════
COMMON MANIM PATTERNS
════════════════════════════════════════════════════════════════════════════════
# Bullet list
bullets = VGroup(
    Text("• First point", font_size=28),
    Text("• Second point", font_size=28),
    Text("• Third point", font_size=28)
).arrange(DOWN, buff=0.5, aligned_edge=LEFT)
bullets.next_to(title, DOWN, buff=0.8)
for bullet in bullets:
    self.play(FadeIn(bullet), run_time=0.8)
    self.wait(2.0)  # Wait while narrator explains

# Step-by-step equation
eq1 = MathTex(r"x^2 + 2x + 1").scale(0.85)
self.play(Write(eq1))
self.wait(2.0)
eq2 = MathTex(r"(x + 1)^2").scale(0.85)
self.play(ReplacementTransform(eq1, eq2))
self.wait(2.0)

# Graph
axes = Axes(x_range=[-3, 3, 1], y_range=[-2, 4, 1], x_length=7, y_length=5)
graph = axes.plot(lambda x: x**2, color=BLUE)
self.play(Create(axes), run_time=1.5)
self.play(Create(graph), run_time=2.0)
self.wait(3.0)

════════════════════════════════════════════════════════════════════════════════
SYNTAX REQUIREMENTS
════════════════════════════════════════════════════════════════════════════════
- Use 8 spaces for indentation (inside construct body)
- MathTex uses raw strings with double backslashes: r"\\frac{{a}}{{b}}"
- Double braces for Python f-strings: axis_config={{"include_tip": True}}

⚠️ DURATION CHECK: Before finishing, mentally sum all run_time + wait values.
   They MUST total {audio_duration:.1f} seconds. Add more self.wait() if needed!

════════════════════════════════════════════════════════════════════════════════
OUTPUT REQUIREMENTS
════════════════════════════════════════════════════════════════════════════════
Output ONLY the Python code for the construct() body.
- NO markdown code blocks (no ```)
- NO explanations
- NO class definition or imports
- Just the indented code that goes inside construct(self)
- VERIFY total duration = {audio_duration:.1f}s before outputting!
"""



# System instruction for code correction
CORRECTION_SYSTEM_INSTRUCTION = """You are an expert Manim Community Edition (manim) programmer and debugger.
Your task is to fix Python code errors in Manim animations.

MANIM CE QUICK REFERENCE:

DIRECTION CONSTANTS (use these, NOT "BOTTOM"):
- UP, DOWN, LEFT, RIGHT (unit vectors)
- UL, UR, DL, DR (diagonals: upper-left, upper-right, etc.)
- ORIGIN (center point)
- IN, OUT (for 3D scenes only)
NOTE: There is NO "BOTTOM" constant! Use DOWN instead.

COLOR CONSTANTS (uppercase):
- RED, GREEN, BLUE, YELLOW, ORANGE, PURPLE, PINK, WHITE, BLACK, GRAY/GREY
- Variants: LIGHT_GRAY, DARK_GRAY, BLUE_A, BLUE_B, BLUE_C, BLUE_D, BLUE_E
- TEAL, MAROON, GOLD, etc.

POSITIONING METHODS:
- .to_edge(UP/DOWN/LEFT/RIGHT, buff=0.5) - move to screen edge
- .to_corner(UL/UR/DL/DR, buff=0.5) - move to corner
- .next_to(obj, UP/DOWN/LEFT/RIGHT, buff=0.25) - position relative to another object
- .move_to(point or obj) - move center to position
- .shift(direction * amount) - relative movement
- .align_to(obj, direction) - align edges

COMMON MOBJECTS:
- Text("string", font_size=48) - regular text
- MathTex(r"\\frac{a}{b}") - LaTeX math (double backslashes!)
- Tex(r"Text with $math$") - mixed text and math
- Circle(), Square(), Rectangle(), Triangle(), Polygon()
- Line(start, end), Arrow(start, end), DashedLine()
- Dot(), NumberLine(), Axes(), NumberPlane()
- VGroup(*mobjects) - group multiple objects
- SurroundingRectangle(obj), Brace(obj, direction)

ANIMATIONS:
- Create(mobject), Write(mobject), FadeIn(mobject), FadeOut(mobject)
- Transform(source, target), ReplacementTransform(source, target)
- Indicate(mobject), Circumscribe(mobject), Flash(mobject)
- GrowFromCenter(mobject), GrowArrow(arrow)
- self.play(animation, run_time=1) - play animation
- self.wait(seconds) - pause
- self.add(mobject) - add without animation
- self.remove(mobject) - remove without animation

ANIMATE SYNTAX (for property changes):
- obj.animate.shift(UP)
- obj.animate.scale(2)
- obj.animate.set_color(RED)
- obj.animate.move_to(ORIGIN)
- Can chain: obj.animate.shift(UP).scale(0.5)

COMMON ERRORS TO FIX:
1. "BOTTOM" is not defined → Use DOWN instead
2. "TOP" is not defined → Use UP instead  
3. IndentationError → Use 8 spaces inside construct()
4. NameError for colors → Use uppercase: BLUE not blue
5. MathTex needs double backslashes: r"\\frac{a}{b}"
6. VGroup elements must be Mobjects, not strings
7. self.play() needs animations, not raw Mobjects
8. Objects must be added before FadeOut

OUTPUT: Return ONLY the complete fixed Python code. No markdown, no explanations."""


# Shorter system instruction for render error fixes
RENDER_FIX_SYSTEM_INSTRUCTION = """You are an expert Manim Community Edition debugger.
Fix the error in the provided Manim code.

MANIM CE QUICK REFERENCE:

DIRECTION CONSTANTS (use these, NOT "BOTTOM" or "TOP"):
- UP, DOWN, LEFT, RIGHT (unit vectors)
- UL, UR, DL, DR (diagonals)
- ORIGIN (center)
NOTE: "BOTTOM" and "TOP" do NOT exist! Use DOWN and UP instead.

COLOR CONSTANTS: RED, GREEN, BLUE, YELLOW, WHITE, BLACK, GRAY, etc. (uppercase)

POSITIONING:
- .to_edge(UP/DOWN/LEFT/RIGHT, buff=0.5)
- .next_to(obj, direction, buff=0.25)
- .move_to(point), .shift(direction * amount)

COMMON FIXES:
1. BOTTOM → DOWN, TOP → UP
2. Colors must be uppercase
3. MathTex needs double backslashes: r"\\frac{a}{b}"
4. 8 spaces indentation inside construct()
5. Objects must be added before FadeOut

OUTPUT: Return ONLY the complete fixed Python code. No markdown."""


def build_correction_prompt(
    original_code: str,
    error_message: str,
    section: Dict[str, Any]
) -> str:
    """Build the prompt for fixing Manim code errors"""
    
    # Get duration info
    duration = section.get('duration_seconds', section.get('target_duration', section.get('total_duration', 30)))
    
    # Build timing context for fix - include FULL segment text for proper timing
    timing_context = ""
    if section.get('is_unified_section', False):
        segment_timing = section.get('segment_timing', [])
        if segment_timing:
            timing_lines = []
            for i, s in enumerate(segment_timing):
                line = f"  SEGMENT {i+1}: [{s['start_time']:.1f}s - {s['end_time']:.1f}s] ({s.get('duration', s['end_time']-s['start_time']):.1f}s)"
                line += f"\n    Narration: \"{s['text']}\""
                timing_lines.append(line)
            timing_context = f"\n════════════════════════════════════════════════════════════════\nTIMING BREAKDOWN (Total: {duration:.1f}s) - Sync visuals to these segments:\n════════════════════════════════════════════════════════════════\n" + "\n\n".join(timing_lines)
    elif section.get('narration_segments'):
        segments = section.get('narration_segments', [])
        if segments:
            cumulative = 0.0
            timing_lines = []
            for i, seg in enumerate(segments):
                seg_dur = seg.get('estimated_duration', seg.get('duration', 5.0))
                start_time = seg.get('start_time', cumulative)
                end_time = seg.get('end_time', cumulative + seg_dur)
                line = f"  SEGMENT {i+1}: [{start_time:.1f}s - {end_time:.1f}s] ({seg_dur:.1f}s)"
                line += f"\n    Narration: \"{seg.get('text', '')}\""
                timing_lines.append(line)
                cumulative = end_time
            timing_context = f"\n════════════════════════════════════════════════════════════════\nTIMING BREAKDOWN (Total: {duration:.1f}s) - Sync visuals to these segments:\n════════════════════════════════════════════════════════════════\n" + "\n\n".join(timing_lines)
    
    return f"""Fix the following Manim code error:

⚠️ TARGET DURATION: {duration:.1f} seconds - animations + waits MUST sum to this!

ORIGINAL CODE:
```python
{original_code}
```

ERROR MESSAGE:
```
{error_message[-2000:]}
```

SECTION CONTEXT:
- Title: {section.get('title', 'Untitled')}
- Visual: {section.get('visual_description', '')[:300]}
{timing_context}

Analyze the error and fix the code. Ensure the fixed code still matches the {duration:.1f}s target duration.
Return ONLY the complete corrected Python file."""


def build_visual_fix_prompt(
    original_code: str,
    error_report: str,
    section: Dict[str, Any]
) -> str:
    """Build the prompt for fixing visual layout issues detected by QC"""
    
    section_title = section.get('title', 'Untitled')
    duration = section.get('duration_seconds', section.get('target_duration', section.get('total_duration', 30)))
    narration = section.get('narration', section.get('tts_narration', ''))[:500]
    
    # Build FULL timing context with complete segment text
    timing_context = ""
    if section.get('is_unified_section', False):
        segment_timing = section.get('segment_timing', [])
        if segment_timing:
            timing_lines = []
            for i, s in enumerate(segment_timing):
                seg_dur = s.get('duration', s['end_time'] - s['start_time'])
                line = f"  SEGMENT {i+1}: [{s['start_time']:.1f}s - {s['end_time']:.1f}s] ({seg_dur:.1f}s)"
                line += f"\n    Narration: \"{s['text']}\""
                if s.get('visual_description'):
                    line += f"\n    Visual: {s['visual_description']}"
                timing_lines.append(line)
            timing_context = "\n════════════════════════════════════════════════════════════════\nTIMING BREAKDOWN - Create visuals for EACH segment:\n════════════════════════════════════════════════════════════════\n" + "\n\n".join(timing_lines)
    elif section.get('narration_segments'):
        segments = section.get('narration_segments', [])
        if segments:
            cumulative = 0.0
            timing_lines = []
            for i, seg in enumerate(segments):
                seg_dur = seg.get('estimated_duration', seg.get('duration', 5.0))
                start_time = seg.get('start_time', cumulative)
                end_time = seg.get('end_time', cumulative + seg_dur)
                line = f"  SEGMENT {i+1}: [{start_time:.1f}s - {end_time:.1f}s] ({seg_dur:.1f}s)"
                line += f"\n    Narration: \"{seg.get('text', '')}\""
                if seg.get('visual_description'):
                    line += f"\n    Visual: {seg['visual_description']}"
                timing_lines.append(line)
                cumulative = end_time
            timing_context = "\n════════════════════════════════════════════════════════════════\nTIMING BREAKDOWN - Create visuals for EACH segment:\n════════════════════════════════════════════════════════════════\n" + "\n\n".join(timing_lines)

    return f"""You are an expert Manim (Community Edition) programmer. Your task is to fix VISUAL LAYOUT ERRORS in the code below.

SECTION: {section_title}
⚠️ TARGET DURATION: {duration:.1f} seconds - all animations + waits MUST total this!

NARRATION (for context):
{narration}
{timing_context}

ORIGINAL MANIM CODE WITH VISUAL ISSUES:
```python
{original_code}
```

VISUAL ERRORS DETECTED BY QC SYSTEM:
{error_report}

════════════════════════════════════════════════════════════════════════════════
⚠️⚠️⚠️ YOUR TASK: FIX THE VISUAL LAYOUT ERRORS ⚠️⚠️⚠️
════════════════════════════════════════════════════════════════════════════════

Preserve:
1. The same educational content and meaning
2. The same animations and transitions (if possible)
3. The same total duration (~{duration}s)
4. The same class name and structure

═══ FRAME BOUNDARIES - CRITICAL REFERENCE ═══
Manim frame dimensions:
- HORIZONTAL: -7.1 to +7.1 (use -6.0 to +6.0 for safe zone)
- VERTICAL: -4.0 to +4.0 (use -3.2 to +3.2 for safe zone)
Content MUST stay within safe zone to avoid cutoff!

═══ SPECIFIC FIXES BY ERROR TYPE ═══

**FOR OVERLAPS (most common):**
- INCREASE all buff values: Change buff=0.3 → buff=0.8
- For .next_to(): Use buff=0.8 minimum for vertical, buff=0.6 for horizontal
- For .arrange(): Use buff=0.6 minimum
- ADD cleanup: self.play(FadeOut(old_content)) before adding new
- USE ReplacementTransform(old, new) instead of just adding new content
- For VGroups: items.arrange(DOWN, buff=0.6, aligned_edge=LEFT)

**FOR OVERFLOW/CLIPPING/OFF-SCREEN:**
- **MANDATORY**: Use `.scale_to_fit_width(12.0)` on wide groups/equations.
- **MANDATORY**: Use `.scale_to_fit_height(6.0)` on tall groups.
- SCALE DOWN: Add .scale(0.7) or .scale(0.75) to large elements
- INCREASE edge buffers: .to_edge(UP, buff=0.8) not buff=0.3
- RECENTER: Use .move_to(ORIGIN) or .move_to(DOWN * 0.5)
- For equations: .scale(0.75) is usually needed

**FOR TEXT/EQUATION TOO LARGE:**
- Reduce font_size: 40 → 34, 36 → 30, 32 → 26
- Add scaling: .scale(0.8) after creation
- For long equations: .scale(0.7) and .move_to(ORIGIN)

**FOR POSITIONING ISSUES:**
- Title: .to_edge(UP, buff=0.8) 
- Content below title: .next_to(title, DOWN, buff=0.8)
- Center content: .move_to(ORIGIN) or .move_to(DOWN * 0.3)
- Side content: .to_edge(LEFT, buff=1.2) or .to_edge(RIGHT, buff=1.2)

═══ COMMON FIX PATTERNS ═══

# Fix overlapping bullet points:
bullets = VGroup(*items).arrange(DOWN, buff=0.6, aligned_edge=LEFT)
bullets.scale_to_fit_height(5.0)  # Constrain height
bullets.next_to(title, DOWN, buff=0.8)

# Fix equation overflow:
eq = MathTex(r"long equation").scale(0.7)
eq.move_to(ORIGIN)  # Center it

# Fix content stacking (add cleanup):
self.play(FadeOut(old_group))  # Clear first!
self.play(FadeIn(new_content))

# Fix edge cutoff:
content.scale(0.8).to_edge(LEFT, buff=1.2)

═══ VERIFICATION CHECKLIST ═══
Before outputting, verify:
□ All buff values >= 0.6 for .next_to() and .arrange()
□ All edge buff values >= 0.8 for .to_edge()
□ Large elements have .scale(0.7-0.85)
□ Old content is FadeOut before new content appears
□ Nothing positioned beyond x=±6.0 or y=±3.2

════════════════════════════════════════════════════════════════════════════════
OUTPUT REQUIREMENTS
════════════════════════════════════════════════════════════════════════════════
- Output ONLY valid Python code - no markdown, no explanations
- Include all imports: `from manim import *`
- Keep the same class name and structure
- Use 8-space indentation inside `construct()`
- The code must compile and run without errors

OUTPUT: Complete fixed Python file only."""


def build_render_fix_prompt(code: str, error_message: str, section: Optional[Dict[str, Any]] = None) -> str:
    """Build a simpler prompt for fixing render/syntax errors"""
    
    # Build timing context if section is provided
    timing_info = ""
    duration = 30  # default
    
    if section:
        duration = section.get('duration_seconds', section.get('target_duration', section.get('total_duration', 30)))
        timing_info = f"\n⚠️ TARGET DURATION: {duration:.1f}s - animations + waits must total this!\n"
        
        if section.get('is_unified_section', False):
            segment_timing = section.get('segment_timing', [])
            if segment_timing:
                timing_lines = []
                for i, s in enumerate(segment_timing):
                    timing_lines.append(f"  SEGMENT {i+1}: [{s['start_time']:.1f}s-{s['end_time']:.1f}s] \"{s['text']}\"")
                timing_info += "\nSEGMENT TIMING:\n" + "\n".join(timing_lines) + "\n"
        elif section.get('narration_segments'):
            segments = section.get('narration_segments', [])
            if segments:
                cumulative = 0.0
                timing_lines = []
                for i, seg in enumerate(segments):
                    seg_dur = seg.get('estimated_duration', seg.get('duration', 5.0))
                    timing_lines.append(f"  SEGMENT {i+1}: [{cumulative:.1f}s-{cumulative+seg_dur:.1f}s] \"{seg.get('text', '')}\"")
                    cumulative += seg_dur
                timing_info += "\nSEGMENT TIMING:\n" + "\n".join(timing_lines) + "\n"
    
    return f"""Fix this Manim code error:
{timing_info}
CODE:
```python
{code}
```

ERROR:
```
{error_message[-1500:]}
```

Return the complete fixed Python file only. Ensure animations match the target duration."""
