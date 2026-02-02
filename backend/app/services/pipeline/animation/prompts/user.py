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

SEGMENT_CODER_USER = PromptTemplate(
    template="""Phase 2: Segment Implementation.

Implement the Manim code for Segment {segment_index}:
"{segment_text}"

DURATION: {duration}s
START TIME: {start_time}s

Follow the plan you created. If previous segments exist in history, ensure variables and positions are consistent.
Return ONLY the Manim code (construct method body) in a python code block.""",
    description="User prompt for implementing a single segment in the session"
)

REANIMATOR_USER = PromptTemplate(
    template="""Phase 3: Error Correction.

The code you just generated for this segment has errors:
{errors}

Please provide the corrected Manim code for THIS SEGMENT ONLY.
Ensure consistency with previous segments in history.
Return your fixed code in a python code block.""",
    description="Refinement user prompt for correcting a segment in context"
)
