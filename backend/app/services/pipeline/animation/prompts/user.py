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
    template="""The Manim code has validation errors. Fix them surgically.

## CURRENT CODE
```python
{code}
```

## ERRORS
{errors}

{visual_context}

## SPATIAL FIX STRATEGIES

### Overlapping Objects
When two objects overlap, separate them by modifying position:
- Use `.next_to(other_obj, direction, buff=0.3)` to position relative to another
- Use `.shift(direction * amount)` to move (e.g., `.shift(UP * 0.5)`)
- Use `.move_to(point)` for exact coordinates
- Safe positions: Y from -2.5 to 2.5, X from -5 to 5

Example fix for overlap:
```python
# Before (overlapping)
text1.move_to(ORIGIN)
text2.move_to(ORIGIN)

# After (separated)
text1.move_to(UP * 0.5)
text2.move_to(DOWN * 0.5)
```

### Out of Bounds
When object exceeds screen edges (error shows direction like "Right (+0.88)"):
- Shift opposite direction: "Right" violation → `.shift(LEFT * 1)`
- Scale down: `.scale(0.7)` to make smaller
- Reposition to safe zone: `.move_to(LEFT * 2)` instead of edge

### Low Contrast
When text blends with background (#171717 is dark):
- Use bright colors: WHITE, YELLOW, BLUE, GREEN, RED, ORANGE
- Avoid: GRAY, BLACK, or any dark colors
- Fix: Add `color=WHITE` in constructor OR `.set_color(WHITE)`

## INSTRUCTIONS
1. **Analyze**: Provide a brief analysis of the error and your fix strategy.
2. **Inspect**: Review the attached frames (if any) to confirm visual state.
3. **Fix**: Return a JSON object with a list of surgical edits.

## OUTPUT FORMAT (JSON)
Return a single JSON object with this structure:
```json
{
    "analysis": "Explanation of the error and fix...",
    "edits": [
        {
            "search_text": "exact lines of code to find",
            "replacement_text": "new lines of code"
        }
    ]
}
```

**Rules for Edits:**
- `search_text` MUST be an EXACT match (copy-paste from code).
- Include 2-3 lines of context in `search_text` to avoid ambiguity.
- If multiple identical blocks exist, include more surrounding lines to disambiguate.
- `replacement_text` must be valid, indented Python code.""",
    description="Surgical fix prompt with spatial guidance"
)


# =============================================================================
# LEGACY COMPATIBILITY (will be removed)
# =============================================================================

ANIMATOR_USER = CHOREOGRAPHY_USER  # Alias for backward compatibility
