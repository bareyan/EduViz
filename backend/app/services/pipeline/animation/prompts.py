"""
Animation Prompts - All Manim-related prompt templates

Centralizes prompts for:
- Agentic code generation
- Error correction
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
# ERROR CORRECTION PROMPTS
# =============================================================================

DIFF_CORRECTION_SYSTEM = PromptTemplate(
    template="""You are an expert Manim code debugger.
Fix Python/Manim errors using SEARCH/REPLACE blocks.

{manim_context}

OUTPUT FORMAT:
For each fix, output a SEARCH/REPLACE block:

```python
<<<<<<< SEARCH
# Exact code to find
=======
# Fixed code
>>>>>>> REPLACE
```

RULES:
1. SEARCH text must EXACTLY match existing code (whitespace matters!)
2. Keep changes minimal and targeted
3. Fix the root cause, not symptoms
4. Preserve timing (self.wait, run_time values)
5. Don't change working code unnecessarily""",
    description="System prompt for diff-based error correction"
)


DIFF_CORRECTION_USER = PromptTemplate(
    template="""Fix this Manim code error.

ERROR TYPE: {error_type}
ERROR MESSAGE:
{error_message}

CURRENT CODE:
```python
{code}
```

{timing_hint}

Provide SEARCH/REPLACE blocks to fix the error.
Keep changes minimal - only fix what's broken.""",
    description="User prompt for diff-based correction"
)


STRUCTURED_CORRECTION_SYSTEM = PromptTemplate(
    template="""You are a Manim code debugger. Analyze errors and provide fixes.

{manim_context}

Provide fixes as search/replace pairs. The "search" field must EXACTLY match text in the code.""",
    description="System prompt for structured JSON error correction"
)


STRUCTURED_CORRECTION_USER = PromptTemplate(
    template="""Analyze and fix this Manim code error.

ERROR TYPE: {error_type}
ERROR:
{error_message}

CODE:
```python
{code}
```

Return JSON with fixes array. Each fix has 'search' and 'replace' fields.""",
    description="User prompt for structured correction"
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


def parse_error_context(error_message: str) -> Dict[str, str]:
    """Parse error message to extract context"""
    context = {
        "error_type": "unknown",
        "line": None,
        "details": error_message
    }
    
    # Try to extract error type
    if "NameError" in error_message:
        context["error_type"] = "NameError"
    elif "AttributeError" in error_message:
        context["error_type"] = "AttributeError"
    elif "TypeError" in error_message:
        context["error_type"] = "TypeError"
    elif "ValueError" in error_message:
        context["error_type"] = "ValueError"
    elif "SyntaxError" in error_message:
        context["error_type"] = "SyntaxError"
    elif "IndentationError" in error_message:
        context["error_type"] = "IndentationError"
    
    # Try to extract line number
    import re
    line_match = re.search(r'line (\d+)', error_message)
    if line_match:
        context["line"] = line_match.group(1)
    
    return context


def build_diff_correction_prompt(
    code: str,
    error_message: str,
    section: Optional[Dict[str, Any]] = None
) -> str:
    """Build complete prompt for diff-based correction"""
    context = parse_error_context(error_message)
    
    timing_hint = ""
    if section:
        timing = section.get("audio_duration", 30)
        timing_hint = f"TARGET TIMING: {timing}s (preserve timing if possible)"
    
    return DIFF_CORRECTION_USER.format(
        error_type=context["error_type"],
        error_message=error_message,
        code=code,
        timing_hint=timing_hint
    )


def build_structured_correction_prompt(
    code: str,
    error_message: str,
    section: Optional[Dict[str, Any]] = None
) -> str:
    """Build prompt for structured JSON correction"""
    context = parse_error_context(error_message)
    
    return STRUCTURED_CORRECTION_USER.format(
        error_type=context["error_type"],
        error_message=error_message,
        code=code
    )


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Generation
    "AGENTIC_GENERATION_SYSTEM",
    "AGENTIC_GENERATION_USER",
    
    # Error Correction
    "DIFF_CORRECTION_SYSTEM",
    "DIFF_CORRECTION_USER",
    "STRUCTURED_CORRECTION_SYSTEM",
    "STRUCTURED_CORRECTION_USER",
    
    # Recompilation
    "RECOMPILE_SYSTEM",
    "RECOMPILE_USER",
    
    # Tool-based Correction
    "TOOL_CORRECTION_SYSTEM",
    "TOOL_CORRECTION_PROMPT",
    
    # Helpers
    "format_timing_context",
    "parse_error_context",
    "build_diff_correction_prompt",
    "build_structured_correction_prompt",
    
    # Constants
    "MANIM_CONTEXT",
    "MANIM_VERSION",
]
