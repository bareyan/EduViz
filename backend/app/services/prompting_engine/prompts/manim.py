"""
Manim code generation prompts.

Used by: manim_generator/generator.py
"""

from .base import PromptTemplate


VISUAL_SCRIPT = PromptTemplate(
    template="""Create a visual storyboard for this animation section.

Section: {section_title}
Narration: {narration}
Duration: {duration} seconds

For each moment, describe:
- Timestamp (e.g., 0:00-0:05)
- What appears on screen
- Animations/transitions
- Text/equations to show
- Colors and positioning

Be specific about:
- Object positions (use "upper left", "center", etc.)
- Animation timing (Write, FadeIn, Transform, etc.)
- Visual hierarchy (what's most important)

{timing_context}""",
    description="Generate visual script/storyboard for Manim"
)


VISUAL_SCRIPT_ANALYSIS = PromptTemplate(
    template="""Check this visual script for spatial layout issues.

Visual Script:
{visual_script}

Duration: {duration} seconds

Check for:
1. Overlapping elements at same timestamp
2. Too many objects on screen at once (max 4-5)
3. Text too small or too large
4. Poor positioning (off-screen, cramped)
5. Missing cleanup (objects staying too long)

Respond with JSON:
{{
    "status": "ok" or "issues_found",
    "issues_found": <count>,
    "fixes": [
        {{"issue": "...", "fix": "..."}}
    ]
}}""",
    description="Analyze visual script for layout problems"
)


MANIM_CODE_FROM_SCRIPT = PromptTemplate(
    template="""Generate Manim code for this visual script.

Visual Script:
{visual_script}

Duration: {duration} seconds
Style: {style}

{language_instructions}
{color_instructions}
{type_guidance}

{spatial_fixes}

Generate ONLY the construct() method body.
Use proper Manim CE syntax.
Match timing to narration segments.

Important:
- Clean up objects before adding new ones
- Use self.wait() for timing
- Keep animations smooth
- Position text clearly""",
    description="Generate Manim code from visual script"
)


MANIM_SINGLE_SHOT = PromptTemplate(
    template="""Generate Manim animation code for this section.

Title: {section_title}
Narration: {narration}
Visual Description: {visual_description}
Duration: {duration} seconds

{timing_context}

{language_instructions}
{color_instructions}
{type_guidance}

Generate ONLY the construct() method body.
Match animation timing to narration.
Use clean, working Manim CE code.""",
    description="Single-shot Manim code generation"
)
