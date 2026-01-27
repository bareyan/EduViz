"""
Animation Prompts - All Manim-related prompt templates

Centralizes prompts for:
- Agentic code generation
- Tool-based correction
- Code recompilation
- Visual refinement
"""

from typing import Dict, Any, Optional
from app.services.infrastructure.llm.prompting_engine.prompts.base import PromptTemplate
from .generation.tools.context import get_manim_reference


# =============================================================================
# CONSTANTS
# =============================================================================

MANIM_VERSION = "0.18.1"
MANIM_CONTEXT = get_manim_reference()


# =============================================================================
# GENERATION PROMPTS
# =============================================================================

AGENTIC_GENERATION_SYSTEM = PromptTemplate(
    template="""{manim_context}

TOOL-BASED ITERATION:
You have two tools: generate_manim_code and fix_manim_code

PROCESS:
1. Call generate_manim_code with your best attempt
2. You'll receive validation feedback
3. If there are errors, call fix_manim_code with corrections
4. Iterate until code validates or max attempts reached

CRITICAL: Only use the tools to submit code. Do NOT write code in messages.
Each tool call returns validation results to guide your fixes.""",
    description="System prompt for agentic Manim code generation with tool-based iteration"
)


AGENTIC_GENERATION_USER = PromptTemplate(
    template="""Use the generate_manim_code tool to create animation code for this section:

TITLE: {title}

NARRATION:
{narration}

VISUAL DESCRIPTION:
{visual_description}

{timing_context}

TARGET DURATION: {target_duration} seconds

Generate the construct() method body that creates engaging animations matching the narration.
Use self.wait() to sync with narration timing.""",
    description="User prompt for agentic code generation"
)


# =============================================================================
# CODE RECOMPILATION PROMPTS
# =============================================================================

RECOMPILE_SYSTEM = PromptTemplate(
    template="""You are an expert Manim animator, skilled at creating beautiful 3Blue1Brown-style mathematical animations.
Your task is to fix or improve the provided Manim code based on the user's request.

RULES:
1. Return ONLY the complete fixed Python code, no explanations
2. Keep the same class name and structure
3. Ensure the code is valid Manim CE (Community Edition) code
4. Make animations smooth and visually appealing
5. Use proper positioning, colors, and timing

Return ONLY the Python code, nothing else.""",
    description="System prompt for interactive code recompilation"
)


RECOMPILE_USER = PromptTemplate(
    template="""Section Title: {title}
Section Description: {visual_description}
Narration: {narration}

CURRENT MANIM CODE:
```python
{current_code}
```

USER REQUEST: {user_request}

Please provide the fixed/improved Manim code.""",
    description="User prompt for code recompilation with user feedback"
)


# =============================================================================
# TOOL-BASED CORRECTION PROMPTS
# =============================================================================

TOOL_CORRECTION_SYSTEM = PromptTemplate(
    template="""{manim_context}

TOOL-BASED CORRECTION:
You have two tools: analyze_error and fix_code

PROCESS:
1. Call analyze_error to understand the issue
2. Call fix_code with your corrected code
3. You'll receive validation feedback
4. Iterate if needed

Return corrected code via the fix_code tool.""",
    description="System prompt for tool-based error correction"
)


# =============================================================================
# CODE FIXING PROMPTS (write_code / fix_code tools)
# =============================================================================

FIX_CODE_USER = PromptTemplate(
    template="""Fix this Manim code error.

ERROR MESSAGE:
{error_message}

{context_info}

CURRENT CODE (construct method body only):
```python
{code}
```

You have two tools to fix the code:
1. write_code - Full code replacement (use for major changes or complex issues)
2. fix_code - Targeted search/replace fixes (use for small, surgical fixes)

Choose the appropriate tool based on the error. Both tools will validate the result.""",
    description="User prompt for fixing code with write_code or fix_code tools"
)


FIX_CODE_RETRY_USER = PromptTemplate(
    template="""Previous fix still has errors:

{feedback}

CURRENT CODE:
```python
{code}
```

Use write_code or fix_code tool again with corrections.""",
    description="User prompt for retry after failed fix"
)


GENERATION_RETRY_USER = PromptTemplate(
    template="""Previous attempt had validation errors:

{feedback}

CURRENT CODE:
```python
{code}
```

Use write_code (full rewrite) or fix_code (targeted fixes) to correct the code.""",
    description="User prompt for retry during generation"
)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def format_section_context(section: Optional[Dict[str, Any]]) -> str:
    """Format section context for prompts"""
    if not section:
        return ""
    
    return f"""
SECTION CONTEXT:
- Title: {section.get('title', 'Unknown')}
- Duration: {section.get('target_duration', 30)} seconds
"""


TOOL_CORRECTION_PROMPT = PromptTemplate(
    template="""Previous code attempt failed validation. Fix the issues:

ERROR:
{error_message}

FAILED CODE:
```python
{code}
```

Use fix_code tool to provide corrected code.""",
    description="Prompt for tool-based correction iteration"
)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def format_timing_context(section: Dict[str, Any]) -> str:
    """Build timing context from section segments"""
    if "segments" not in section:
        return ""
    
    segments = section["segments"]
    timing_lines = []
    cumulative = 0.0
    
    for seg in segments:
        seg_duration = seg.get("duration", 5.0)
        seg_text = seg.get("tts_text", seg.get("narration", ""))[:50]
        timing_lines.append(f"  [{cumulative:.1f}s-{cumulative + seg_duration:.1f}s]: \"{seg_text}...\"")
        cumulative += seg_duration
    
    return "TIMING:\n" + "\n".join(timing_lines) if timing_lines else ""


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Generation
    "AGENTIC_GENERATION_SYSTEM",
    "AGENTIC_GENERATION_USER",
    
    # Recompilation
    "RECOMPILE_SYSTEM",
    "RECOMPILE_USER",
    
    # Tool-based Correction
    "TOOL_CORRECTION_SYSTEM",
    "TOOL_CORRECTION_PROMPT",
    
    # Code fixing
    "FIX_CODE_USER",
    "FIX_CODE_RETRY_USER",
    "GENERATION_RETRY_USER",
    
    # Helpers
    "format_timing_context",
    "format_section_context",
    
    # Constants
    "MANIM_CONTEXT",
    "MANIM_VERSION",
]
