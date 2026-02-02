from app.services.infrastructure.llm.prompting_engine.prompts.base import PromptTemplate

ANIMATOR_USER = PromptTemplate(
    template="""Phase 1: Planning.

Create a detailed 'Visual Choreography Plan' for the following educational content:

TITLE: {title}
NARRATION:
{narration}

TIMING INFO:
{timing_info}

TARGET DURATION: {target_duration}s

Break the animation into logical segments. For each segment, describe:
- What objects appear.
- How they move/transform.
- The start/end timing relative to the narration.

Return ONLY the structured plan.""",
    description="User prompt for the planning phase of the session"
)

FULL_IMPLEMENTATION_USER = PromptTemplate(
    template="""Phase 2: Full Implementation.

Based on your choreography plan, implement the COMPLETE, RUNNABLE Manim animation file for this section.

CHOREOGRAPHY PLAN:
{plan}

SEGMENT TIMINGS:
{segment_timings}

TOTAL DURATION: {total_duration}s

CLASS NAME: Scene{section_id_title}

RULES:
- Provide the FULL Manim code, including imports (`from manim import *`), the Scene class, and the `construct` method.
- Use the provided CLASS NAME: Scene{section_id_title}
- Reference existing objects by their variable names.
- Create new objects with descriptive variable names (e.g., 'title_text', 'main_circle').
- Ensure total duration of all animations and waits matches the total duration exactly.
- Use self.wait() to sync with segment start times.
- DO NOT use `self.wait(0)` or other zero-duration waits; skip the wait instead.
- All code must be syntactically correct and follow standard Python indentation.
- The code must be a COMPLETE file starting from column 0 with all necessary imports.

Return the complete code in a python code block.""",
    description="Single-shot full file implementation prompt"
)

SURGICAL_FIX_USER = PromptTemplate(
    template="""The following Manim code has validation errors.

CURRENT CODE:
```python
{code}
```

VALIDATION ERRORS:
{errors}

Use the `apply_surgical_edit` tool to fix ONLY the problematic lines. 
Provide a surgical fix that uniquely identifies the lines to be changed.
Return your fix using the tool call.""",
    description="Isolated surgical fix prompt"
)
