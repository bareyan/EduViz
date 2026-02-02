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

1. **Object Lifecycle**: List every visual object, when it's created, and when it's removed
2. **Animation Timeline**: For each segment, describe:
   - What appears/disappears
   - How it animates (Create, FadeIn, Transform, etc.)
   - Exact start time and duration
3. **Spatial Layout**: Where objects are positioned

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
5. Use ONLY valid rate functions: `linear`, `smooth`, `rush_into`, `rush_from`
6. NO `self.wait(0)` - skip zero-duration waits
7. Use `tracker.get_value()` not `tracker.number` for ValueTrackers

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

## INSTRUCTIONS
Use the `apply_surgical_edit` tool to fix ONLY the problematic lines.
Be precise - identify the exact text to replace and provide the fix.

Common fixes:
- `tracker.number` → `tracker.get_value()`
- `ease_in_expo` → `smooth`
- `self.wait(0)` → remove the line
- Undefined variables → define them or use correct names""",
    description="Isolated surgical fix prompt"
)


# =============================================================================
# LEGACY COMPATIBILITY (will be removed)
# =============================================================================

ANIMATOR_USER = CHOREOGRAPHY_USER  # Alias for backward compatibility
