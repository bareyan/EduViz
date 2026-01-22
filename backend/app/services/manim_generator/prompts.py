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
- Example: Text("Title", color=BLACK, font_size=48)"""
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
- Use MathTex for all mathematical expressions: MathTex(r"\\frac{a}{b}").scale(0.85)
- Transform equations step-by-step with ReplacementTransform
- Highlight specific terms with Indicate() or set_color()
- Show derivation steps one at a time
- Use .scale(0.85) for equations to prevent overflow
- Example flow: Show equation → Highlight term → Transform to next step → Wait for narration""",

    'text': """TEXT-FOCUSED ANIMATION:
- Use Text("content", font_size=32) for regular text
- Build bullet points with VGroup and .arrange(DOWN, buff=0.5, aligned_edge=LEFT)
- Fade in points one by one to match narration
- Keep titles at top with .to_edge(UP, buff=0.8)
- Don't crowd the screen - max 4-5 lines visible at once
- Use FadeOut before adding new content""",

    'diagram': """DIAGRAM/VISUAL ANIMATION:
- Create shapes: Circle(), Square(), Rectangle(), Arrow(), Line()
- Group related elements with VGroup
- Animate connections: GrowArrow for arrows, Create for shapes
- Label components with Text positioned using .next_to()
- Use consistent spacing with .arrange() or manual positioning
- Consider using Brace for grouping visual elements""",

    'code': """CODE DISPLAY ANIMATION:
- Use Code() mobject for syntax highlighting OR
- Use Text("code", font="Monospace", font_size=24) for simple code
- Highlight important lines by changing color: line.animate.set_color(YELLOW)
- Build code incrementally if showing construction
- Keep code blocks reasonably sized - max 10-12 lines
- Position code centrally with good margins""",

    'graph': """GRAPH/PLOT ANIMATION:
- Create axes: Axes(x_range=[-5, 5, 1], y_range=[-3, 3, 1], x_length=8, y_length=5)
- Plot functions: graph = axes.plot(lambda x: x**2, color=BLUE)
- Label axes with axes.get_x_axis_label() and get_y_axis_label()
- Animate graph creation: Create(graph) with run_time matching narration
- Add points of interest with Dot() and labels
- Use axes.get_graph_label() for function labels""",

    'process': """PROCESS/FLOW ANIMATION:
- Create stages as shapes or text boxes
- Connect with arrows: Arrow(start, end)
- Reveal stages sequentially to match narration
- Use consistent left-to-right or top-to-bottom flow
- Highlight current stage while dimming others
- Group stage+arrow pairs for easier animation""",

    'comparison': """COMPARISON ANIMATION:
- Divide screen: LEFT_SIDE and RIGHT_SIDE for two items
- Use consistent styling for comparable elements
- Animate alternating reveals
- Use SurroundingRectangle to highlight differences
- Add clear labels for each side
- Keep visual balance between compared items""",

    'static': """STATIC SCENE (minimal animation):
- Display text/equations that STAY on screen while narrator explains
- Use simple FadeIn animations, then long self.wait() calls
- NO complex transformations - let the narration do the explaining
- Example: Show title → show bullet points → self.wait(5.0)
- 80% of duration should be self.wait() while content is displayed
- Clear content between major topic changes only""",

    'mixed': """MIXED SCENE (balance of static and animated):
- Start with static elements (title, context)
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
2. Use Text() for ALL {script_name} text: Text("text here", font_size=28)
3. Use MathTex() ONLY for pure math symbols: MathTex(r"x^2 + y^2")
4. Position text and math as SEPARATE objects using .next_to()

FONT SIZES for {script_name} (smaller than Latin text):
- Titles: font_size=32
- Body text: font_size=26
- Labels/captions: font_size=22
- Add .scale(0.8) if content is wide

CORRECT PATTERN:
        # Title in {script_name}
        title = Text("Title Here", font_size=32)
        title.to_edge(UP, buff=0.5)
        self.play(Write(title))
        
        # Math equation (universal symbols only)
        eq = MathTex(r"x = 2").scale(0.9)
        eq.move_to(ORIGIN)
        self.play(Write(eq))
        
        # Explanation in {script_name}
        label = Text("Explanation text", font_size=26)
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
- Text() handles accented characters correctly: Text("Théorème", font_size=36)
- MathTex is ONLY for mathematical notation: MathTex(r"\\frac{{x}}{{y}}")
- NEVER put non-math words inside MathTex - it will fail on accented chars
- Keep math and text as separate objects positioned with .next_to()
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
⚠️ CRITICAL: FRAME BOUNDARIES
════════════════════════════════════════════════════════════════════════════════
Manim frame dimensions (MUST RESPECT):
- HORIZONTAL: -7.1 to +7.1 (SAFE ZONE: -6.0 to +6.0)
- VERTICAL: -4.0 to +4.0 (SAFE ZONE: -3.2 to +3.2)
- ORIGIN (0, 0) is the center of the screen

Position reference:
- UP edge: y = +4.0 (safe: +3.2)
- DOWN edge: y = -4.0 (safe: -3.2)
- LEFT edge: x = -7.1 (safe: -6.0)
- RIGHT edge: x = +7.1 (safe: +6.0)

════════════════════════════════════════════════════════════════════════════════
YOUR TASK: Create a Visual Script
════════════════════════════════════════════════════════════════════════════════

For each time segment, specify:

1. **OBJECTS**: What visual elements appear
   - Type: Text, MathTex, Shape, Diagram, Graph, etc.
   - Content: Exact text/equation/shape
   - Size: font_size or scale factor (keep text ≤36, equations scale ≤0.85)

2. **POSITIONS**: Where each object is placed (CRITICAL!)
   - Use coordinates or relative positioning
   - Example: "center of screen (0, 0)", "top with buff=0.8 (0, 3.2)", "below title with buff=0.8"
   - NEVER place objects outside safe zone!

3. **TIMING**: When things happen
   - Start time and duration for each action
   - How long to wait/display

4. **ANIMATIONS**: How objects appear/transform
   - Entry: FadeIn, Write, Create, GrowFromCenter
   - Transform: ReplacementTransform, morph
   - Exit: FadeOut (ALWAYS clear before adding new overlapping content!)

5. **SPACING**: Gaps between elements
   - Minimum vertical gap: 0.6-0.8 units
   - Minimum horizontal gap: 0.5-0.6 units

════════════════════════════════════════════════════════════════════════════════
OUTPUT FORMAT
════════════════════════════════════════════════════════════════════════════════

Use this exact format:

---
VISUAL SCRIPT: {title}
TOTAL DURATION: {audio_duration:.1f}s
---

## SEGMENT 1: [0.0s - X.Xs]
**Narration summary**: "..."

**Objects**:
1. [ObjectType] "content" | size: X | position: (x, y) or description
2. ...

**Actions**:
- [0.0s] Animation(object) | run_time: Xs
- [X.Xs] self.wait(Xs)
- ...

**Layout notes**: Any spacing/positioning considerations

---

## SEGMENT 2: [X.Xs - Y.Ys]
**Narration summary**: "..."

**Cleanup first**: FadeOut(previous_objects) if needed

**Objects**:
...

**Actions**:
...

---

(Continue for all segments)

---
FINAL TIMING CHECK:
- Total animation time: Xs
- Total wait time: Xs
- Combined: {audio_duration:.1f}s ✓
---

Be VERY SPECIFIC about positions. Use exact coordinates when possible.
Ensure NO overlaps and NO off-screen content."""


def build_code_from_script_prompt(
    section: Dict[str, Any],
    visual_script: str,
    audio_duration: float,
    language_instructions: str,
    color_instructions: str,
    type_guidance: str
) -> str:
    """Build prompt for Shot 2: Generate Manim code from visual script"""
    
    title = section.get('title', 'Untitled')
    narration = section.get('narration', section.get('tts_narration', ''))
    
    return f"""You are an expert Manim Community Edition programmer. Generate Python code for the construct(self) method body.

════════════════════════════════════════════════════════════════════════════════
⚠️ CRITICAL: TARGET DURATION = {audio_duration:.1f} SECONDS
════════════════════════════════════════════════════════════════════════════════
Your animation MUST run for EXACTLY {audio_duration:.1f} seconds total.
Sum of all run_time values + all self.wait() calls MUST equal {audio_duration:.1f}s.

════════════════════════════════════════════════════════════════════════════════
VISUAL SCRIPT TO IMPLEMENT
════════════════════════════════════════════════════════════════════════════════
Follow this visual script EXACTLY. It specifies all objects, positions, and timing:

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
- ALL .next_to() calls: use buff=0.6 minimum (0.8 preferred)
- ALL .to_edge() calls: use buff=0.8 minimum
- ALL .arrange() calls: use buff=0.5 minimum

Size rules:
- Titles: font_size=36-40
- Body text: font_size=26-32
- Equations: ALWAYS add .scale(0.75-0.85)

════════════════════════════════════════════════════════════════════════════════
COMMON PATTERNS
════════════════════════════════════════════════════════════════════════════════

# Position at coordinates:
obj.move_to(RIGHT * 2 + UP * 1.5)  # Position at (2, 1.5)

# Proper cleanup before new content:
self.play(FadeOut(old_group))
new_content = Text("New", font_size=32).move_to(ORIGIN)
self.play(FadeIn(new_content))

# VGroup with safe spacing:
items = VGroup(*elements).arrange(DOWN, buff=0.6, aligned_edge=LEFT)
items.next_to(title, DOWN, buff=0.8)

# Scale equation to safe size:
eq = MathTex(r"\\frac{{a}}{{b}} = c").scale(0.8).move_to(ORIGIN)

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
- VERIFY: Implement ALL segments from the visual script
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
- SCALE DOWN: Add .scale(0.7) or .scale(0.75) to large elements
- Use .scale_to_fit_width(12.0) for wide content
- Use .scale_to_fit_height(5.5) for tall content
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
