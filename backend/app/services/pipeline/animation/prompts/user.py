"""
User prompts for the Animation Pipeline.

These define the specific instructions for each generation phase.
"""

from app.services.infrastructure.llm.prompting_engine.prompts.base import PromptTemplate


# =============================================================================
# PHASE 1: CHOREOGRAPHY PLANNING
# =============================================================================

CHOREOGRAPHY_USER = PromptTemplate(
    template="""Create a detailed Visual Choreography Plan for this educational content.

## CONTENT
**Title**: {title}
**Duration**: {target_duration}s

**Narration**:
{narration}

**Segment Timings**:
{timing_info}

## YOUR TASK

Create a structured plan with:

3. **Spatial Layout**: Where objects are positioned

## REASONING STEP (CRITICAL)
Before writing the plan, think deeply about:
- **Spatial Density**: How many objects are on screen? Will they overlap?
- **Coordinate System**: Mentally map everything to the X [-5.5, 5.5] and Y [-3, 3] grid.
- **Visual Flow**: How does the scene transition from one segment to the next?
- **Timing**: Does the animation duration leave enough time for the narration to be understood?

## OUTPUT FORMAT

```
OBJECTS:
- object_name: type, appears at X.Xs, removed at Y.Ys

TIMELINE:
Segment 0 (0.00s - X.XXs): "narration text"
  - 0.00s: Create object_name (duration: 1.5s)
  - 1.50s: Wait 0.5s
  ...

Segment 1 (X.XXs - Y.YYs): "narration text"
  ...
```

Be precise with timing. Total must equal {target_duration}s.""",
    description="User prompt for choreography planning phase"
)


# =============================================================================
# PHASE 2: FULL IMPLEMENTATION
# =============================================================================

FULL_IMPLEMENTATION_USER = PromptTemplate(
    template="""Implement the COMPLETE Manim animation based on this choreography plan.

## CHOREOGRAPHY PLAN
{plan}

## SEGMENT TIMINGS
{segment_timings}

## REQUIREMENTS
- **Total Duration**: {total_duration}s (must match exactly)
- **Class Name**: Scene{section_id_title}
- **Background**: #171717

## CODE REQUIREMENTS
1. Start with `from manim import *`
2. Define class `Scene{section_id_title}(Scene)`
3. Implement `def construct(self):`
4. Set background: `self.camera.background_color = "#171717"`
5. **STRICTLY FOLLOW the technical rules.**

## SELF-CORRECTION (THINK BEFORE WRITING)
- **Version Check**: Am I using Manim Community v0.19.2 syntax? (e.g., `font_size` instead of `size`)
- **Spatial Check**: Is any object moving beyond X: 5.5 or Y: 3.0?
- **Overlap Check**: Did I FadeOut the previous text before FadingIn the new text?
- **Color Check**: Am I using only official Manim colors (e.g., `BLUE_C` NOT `CYAN`)?

## OUTPUT
Return the complete, runnable Python file in a code block.""",
    description="Single-shot full file implementation prompt"
)


# =============================================================================
# PHASE 3: SURGICAL FIXES
# =============================================================================

SURGICAL_FIX_USER = PromptTemplate(
    template="""Fix the listed errors in the ManimCE v0.19.2 code using SURGICAL text replacements.

You MUST output a single JSON object that matches the required schema:
- analysis: string (<=200 chars)
- edits: 1–2 objects with exact search_text and replacement_text

RULES:
- search_text MUST be copied EXACTLY from CURRENT CODE (including whitespace).
- Include 2–3 lines of surrounding context (max ~10 lines total).
- Replace ONLY the minimum lines needed to fix the errors.
- Do NOT reformat or make cosmetic changes.

## CURRENT CODE
```python
{code}
```

## ERRORS TO FIX
```
{errors}
```
""",
    description="Surgical fix prompt with clear examples"
)


SURGICAL_FIX_FOLLOWUP = PromptTemplate(
    template="""The previous edits were applied, but validation failed with the following errors.

## REVISED CODE STATE
```python
{code}
```

## NEW ERRORS
```
{errors}
```

Please analyze the new state and errors. Provide a new JSON correction following the same schema.""",
    description="Follow-up prompt for conversational fixing"
)
