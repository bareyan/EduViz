from app.services.infrastructure.llm.prompting_engine.prompts.base import PromptTemplate

CHOREOGRAPHER_USER = PromptTemplate(
    template="""Create a Visual Choreography Plan for this educational section:

TITLE: {title}
NARRATION:
{narration}

TIMING INFO:
{timing_info}

Format your response as a structured list of segments.
For each segment, specify the VISUAL action and the post-narration PAUSE.""",
    description="User prompt for choreography planning"
)

CODER_USER = PromptTemplate(
    template="""Implement the following Visual Choreography Plan in Manim:

TITLE: {title}
CHOREOGRAPHY PLAN:
{choreography_plan}

TARGET TOTAL DURATION: {target_duration}s

Generate the construct() method body only. Include comments for each segment.""",
    description="User prompt for code generation"
)

REPAIR_USER = PromptTemplate(
    template="""Fix the following Manim code:

ERRORS:
{errors}

CODE:
{code}

Adjust the code to pass validation while maintaining the visual message.""",
    description="User prompt for code repair"
)
