"""
Diff Correction Prompts - Compatibility Layer

Provides prompts for diff-based correction using the centralized tools module.
This is a thin layer that imports from manim_generator/tools for consistency.
"""

from typing import Dict, Any, Optional

# Import from centralized tools
from app.services.pipeline.animation.generation.tools import (
    get_manim_reference,
    SEARCH_REPLACE_SCHEMA,
)

# =============================================================================
# CONSTANTS
# =============================================================================

MANIM_VERSION = "0.18.1"

# Get Manim context from centralized tools
MANIM_CONTEXT = get_manim_reference()


# =============================================================================
# SCHEMAS (re-export from tools)
# =============================================================================

DIFF_CORRECTION_SCHEMA = SEARCH_REPLACE_SCHEMA

VISUAL_QC_DIFF_SCHEMA = {
    "type": "object",
    "properties": {
        "analysis": {
            "type": "string",
            "description": "Brief analysis of the visual error"
        },
        "fixes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "search": {"type": "string", "description": "Exact text to find"},
                    "replace": {"type": "string", "description": "Replacement text"},
                    "reason": {"type": "string", "description": "Why this fix helps"}
                },
                "required": ["search", "replace"]
            }
        }
    },
    "required": ["fixes"]
}


# =============================================================================
# SYSTEM PROMPTS
# =============================================================================

DIFF_CORRECTION_SYSTEM = f"""You are an expert Manim code debugger.
Fix Python/Manim errors using SEARCH/REPLACE blocks.

{MANIM_CONTEXT}

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
5. Don't change working code unnecessarily
"""

VISUAL_QC_DIFF_SYSTEM = f"""You are an expert at fixing visual layout issues in Manim.
Fix visual errors (text overflow, overlapping, timing) using SEARCH/REPLACE blocks.

{MANIM_CONTEXT}

COMMON VISUAL FIXES:
1. Text overflow: Reduce font_size or truncate text
2. Overlapping: Increase buff values, reposition with to_edge/next_to
3. Timing issues: Adjust self.wait() and run_time values
4. Off-screen: Use to_edge() with proper buff values

OUTPUT FORMAT:
```python
<<<<<<< SEARCH
# Exact code to find
=======
# Fixed code
>>>>>>> REPLACE
```
"""


# =============================================================================
# PROMPT BUILDERS
# =============================================================================

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
    """Build prompt for diff-based correction"""
    context = parse_error_context(error_message)
    
    prompt = f"""Fix this Manim code error.

ERROR TYPE: {context["error_type"]}
ERROR MESSAGE:
{error_message}

CURRENT CODE:
```python
{code}
```

Provide SEARCH/REPLACE blocks to fix the error.
Keep changes minimal - only fix what's broken.
"""
    
    if section:
        timing = section.get("audio_duration", 30)
        prompt += f"\nTARGET TIMING: {timing}s (preserve timing if possible)"
    
    return prompt


def build_structured_prompt(
    code: str,
    error_message: str,
    section: Optional[Dict[str, Any]] = None
) -> str:
    """Build prompt for structured JSON output"""
    context = parse_error_context(error_message)
    
    return f"""Analyze and fix this Manim code error.

ERROR TYPE: {context["error_type"]}
ERROR:
{error_message}

CODE:
```python
{code}
```

Return JSON with fixes array. Each fix has 'search' and 'replace' fields.
"""


def build_visual_qc_diff_prompt(
    code: str,
    error_report: str,
    section: Optional[Dict[str, Any]] = None
) -> str:
    """Build prompt for visual QC diff correction"""
    prompt = f"""Fix the visual layout issues in this Manim code.

VISUAL ERROR REPORT:
{error_report}

CURRENT CODE:
```python
{code}
```

Provide SEARCH/REPLACE blocks to fix the visual issues.
Focus on:
- Text positioning and sizing
- Element spacing (buff values)
- Timing adjustments
"""
    
    if section:
        timing = section.get("audio_duration", 30)
        prompt += f"\nTARGET TIMING: {timing}s"
    
    return prompt


def build_visual_qc_structured_prompt(
    code: str,
    error_report: str,
    section: Optional[Dict[str, Any]] = None
) -> str:
    """Build prompt for structured visual QC output"""
    return f"""Fix visual layout issues in this Manim code.

ERROR REPORT:
{error_report}

CODE:
```python
{code}
```

Return JSON with 'analysis' and 'fixes' array.
Each fix: {{"search": "exact text", "replace": "fixed text", "reason": "why"}}
"""
