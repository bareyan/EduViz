"""
Visual Script Generation Prompts

Centralizes prompts for visual script generation:
- System instruction with visual style guidelines
- Few-shot examples demonstrating timing and visual planning
- User prompt templates for generation
"""

from typing import Dict, Any, List
from app.services.infrastructure.llm.prompting_engine.prompts.base import PromptTemplate


# =============================================================================
# SYSTEM INSTRUCTION
# =============================================================================

VISUAL_SCRIPT_SYSTEM = PromptTemplate(
    template="""You are an expert Manim Animation Director and Visual Pedagogy Architect.
Your goal is to convert a spoken narration script into a detailed, time-synchronized visual storyboard (Visual Script)
that will be used by a Python developer to generate Manim code.

### YOUR OBJECTIVE
You will receive a list of audio segments (text + duration). You must generate a JSON output that describes exactly
what should happen on screen during that segment, and critically, determine if extra time (pauses) is needed.

### VISUAL STYLE GUIDELINES (MANIM)
1. **Objects:** Use geometric shapes (Circles, Squares), LaTeX text (MathTex), Graphs, coordinate systems, and number lines.
   Avoid requests for photorealistic images or complex 3D character modeling.
2. **Actions:** Use terms like "Write text", "FadeIn", "Transform (morph) object A to B", "Flash", "Indicate", "Move to".
3. **Layout:** Maintain a clean, mathematical aesthetic. Avoid clutter. Use proper spacing.
4. **Colors:** Use Manim color constants: RED, BLUE, GREEN, YELLOW, ORANGE, PURPLE, TEAL, WHITE, GREY.
5. **Positions:** Use Manim position constants: UP, DOWN, LEFT, RIGHT, ORIGIN, UL, UR, DL, DR.

### TIMING & SYNCHRONIZATION RULES
1. **Pacing:** Animations take time. A "Write" animation for a long equation might take 2-3 seconds.
   If the narration is short but the animation is complex, the visual will be cut off.
2. **The Pause Variable:** You have control over `post_narration_pause`:
   * If the visual action is simple (pop an image, show text), set pause to 0.0.
   * If the visual action is complex (writing formulas, transforming graphs, multiple sequential animations), add 1.0 to 3.0 seconds.
   * **CRITICAL:** Do not overlap heavy animations with the *start* of the next sentence if the next sentence introduces a new concept.
3. **Audio Duration:** The `audio_duration` is provided - this is how long the narration lasts. Plan visuals to fit within or extend beyond this time.

### VISUAL ELEMENTS TO USE
- **Shapes:** Circle, Square, Rectangle, Triangle, Polygon, Line, Arrow, Dot
- **Text:** Text (for labels), MathTex (for LaTeX equations), Tex (for text with math)
- **Graphs:** NumberLine, Axes, NumberPlane, FunctionGraph, ParametricCurve
- **Groups:** VGroup (for grouping objects), SurroundingRectangle, Brace

### OUTPUT FORMAT
Return a JSON object with:
- `segments`: Array of segment objects (one per audio segment)
- `section_title`: Title of the section
- `style_notes`: Any overall style preferences

Each segment must have:
- `segment_id`: Index of the audio segment (0-based)
- `narration_text`: Exact text from the audio segment
- `visual_description`: Detailed instructions for animator (NO CODE, just description)
- `visual_elements`: List of Manim objects needed
- `audio_duration`: Duration from input
- `post_narration_pause`: Extra time after audio (0.0 to 3.0 seconds)""",
    description="System prompt for visual script generation"
)


# =============================================================================
# FEW-SHOT EXAMPLES
# =============================================================================

FEW_SHOT_EXAMPLES = """
### EXAMPLE 1: Mathematical Theorem
**Input Audio Segments:**
[
  {"text": "Let's look at the Pythagorean theorem.", "duration": 2.0},
  {"text": "It states that a squared plus b squared equals c squared.", "duration": 4.5}
]

**Ideal Output:**
{
  "segments": [
    {
      "segment_id": 0,
      "narration_text": "Let's look at the Pythagorean theorem.",
      "visual_description": "Display title text 'Pythagorean Theorem' in the center using bold font. Animate with Write effect, then add an underline that draws itself.",
      "visual_elements": ["Text", "Line"],
      "audio_duration": 2.0,
      "post_narration_pause": 0.5
    },
    {
      "segment_id": 1,
      "narration_text": "It states that a squared plus b squared equals c squared.",
      "visual_description": "Fade out the title. Create a Right Triangle in the center using Polygon. Label the sides with Text: 'a' on the vertical side (RED), 'b' on the horizontal side (BLUE), and 'c' on the hypotenuse (YELLOW). After the triangle is shown, Write the equation 'a^2 + b^2 = c^2' using MathTex below the triangle. The equation should appear progressively.",
      "visual_elements": ["Polygon", "Text", "MathTex"],
      "audio_duration": 4.5,
      "post_narration_pause": 2.0
    }
  ],
  "section_title": "Pythagorean Theorem",
  "style_notes": "Use contrasting colors for the three sides to reinforce the relationship"
}

### EXAMPLE 2: Simple Concept
**Input Audio Segments:**
[
  {"text": "First, we draw a circle.", "duration": 1.5}
]

**Ideal Output:**
{
  "segments": [
    {
      "segment_id": 0,
      "narration_text": "First, we draw a circle.",
      "visual_description": "Create a WHITE Circle in the center of the screen. Use Create animation so it draws itself.",
      "visual_elements": ["Circle"],
      "audio_duration": 1.5,
      "post_narration_pause": 0.0
    }
  ],
  "section_title": "Circle Introduction",
  "style_notes": ""
}

### EXAMPLE 3: Algorithm Visualization
**Input Audio Segments:**
[
  {"text": "Bubble Sort compares adjacent elements.", "duration": 2.5},
  {"text": "If they are in wrong order, it swaps them.", "duration": 2.8}
]

**Ideal Output:**
{
  "segments": [
    {
      "segment_id": 0,
      "narration_text": "Bubble Sort compares adjacent elements.",
      "visual_description": "Show an array of 5 colored squares in a row at center, each containing a number (5, 1, 4, 2, 8). Use different colors for each square. Highlight the first two squares (5 and 1) by adding a SurroundingRectangle around them with YELLOW stroke.",
      "visual_elements": ["Square", "Text", "SurroundingRectangle"],
      "audio_duration": 2.5,
      "post_narration_pause": 0.5
    },
    {
      "segment_id": 1,
      "narration_text": "If they are in wrong order, it swaps them.",
      "visual_description": "Animate the swap: the square with 5 moves RIGHT while the square with 1 moves LEFT simultaneously, crossing paths. Use smooth animation. After swap, the array shows (1, 5, 4, 2, 8). Flash the swapped elements briefly with Indicate.",
      "visual_elements": ["Square", "Text"],
      "audio_duration": 2.8,
      "post_narration_pause": 1.5
    }
  ],
  "section_title": "Bubble Sort",
  "style_notes": "Keep array elements clearly spaced for readability"
}
"""


# =============================================================================
# USER PROMPT
# =============================================================================

VISUAL_SCRIPT_USER = PromptTemplate(
    template="""{few_shot_examples}

### NEW TASK

**Section Title:** {section_title}

**Source Context (for understanding the topic):**
{source_context}

**Input Audio Segments:**
{audio_segments_json}

**Instructions:**
Generate the Visual Script based on the Input Audio Segments and Source Context.
- Create one segment entry for each audio segment
- Pay strict attention to `post_narration_pause` calculation
- For complex animations (equations, transformations), add appropriate pauses
- For simple visuals, keep pause at 0.0
- Ensure visual_description is detailed enough for a Manim developer to implement
- List all Manim objects needed in visual_elements""",
    description="User prompt for visual script generation"
)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def build_audio_segments_from_section(section: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Build audio segments from a section's narration_segments.
    
    Args:
        section: Section dict with narration_segments
        
    Returns:
        List of audio segment dicts with text and duration
    """
    segments = section.get("narration_segments", [])
    
    if not segments:
        # Fallback: create single segment from full narration
        narration = section.get("tts_narration") or section.get("narration", "")
        duration = section.get("duration_seconds", 30.0)
        return [{"text": narration, "duration": duration}]
    
    audio_segments = []
    for i, seg in enumerate(segments):
        audio_segments.append({
            "text": seg.get("text", ""),
            "duration": seg.get("estimated_duration", seg.get("actual_duration", 5.0))
        })
    
    return audio_segments


def format_audio_segments_json(audio_segments: List[Dict[str, Any]]) -> str:
    """Format audio segments as JSON string for prompt"""
    import json
    return json.dumps(audio_segments, indent=2)


def build_user_prompt(
    section: Dict[str, Any],
    source_context: str = "",
    audio_segments: List[Dict[str, Any]] = None
) -> str:
    """
    Build the user prompt for visual script generation.
    
    Args:
        section: Section dict with title, narration, etc.
        source_context: Optional context about the source material
        audio_segments: Optional pre-built audio segments (uses section if not provided)
        
    Returns:
        Formatted user prompt string
    """
    if audio_segments is None:
        audio_segments = build_audio_segments_from_section(section)
    
    section_title = section.get("title", "Untitled Section")
    
    # Build source context from section if not provided
    if not source_context:
        narration = section.get("narration", section.get("tts_narration", ""))
        source_context = f"Section narration covers: {narration[:500]}..." if len(narration) > 500 else narration
    
    return VISUAL_SCRIPT_USER.format(
        few_shot_examples=FEW_SHOT_EXAMPLES,
        section_title=section_title,
        source_context=source_context,
        audio_segments_json=format_audio_segments_json(audio_segments)
    )


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Templates
    "VISUAL_SCRIPT_SYSTEM",
    "VISUAL_SCRIPT_USER",
    "FEW_SHOT_EXAMPLES",
    
    # Helper functions
    "build_audio_segments_from_section",
    "format_audio_segments_json",
    "build_user_prompt",
]
