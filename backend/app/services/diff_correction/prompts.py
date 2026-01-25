"""
Prompt Templates for Diff-based Correction

Prompts that request SEARCH/REPLACE blocks for targeted code fixes.
Includes Manim package version context for accurate fixes.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass


# Manim Community Edition version context
# Update these when upgrading Manim
MANIM_VERSION = "0.18.1"
MANIM_CONTEXT = f"""MANIM VERSION: {MANIM_VERSION} (Community Edition)

DIRECTION CONSTANTS (there is NO "BOTTOM" or "TOP"):
- UP, DOWN, LEFT, RIGHT (unit vectors)
- UL, UR, DL, DR (diagonals: upper-left, upper-right, etc.)
- ORIGIN (center point)
- IN, OUT (for 3D only)

COLOR CONSTANTS (UPPERCASE only):
- RED, GREEN, BLUE, YELLOW, WHITE, BLACK, GRAY/GREY
- ORANGE, PURPLE, PINK, TEAL, GOLD, MAROON
- Variants: LIGHT_GRAY, DARK_GRAY, BLUE_A through BLUE_E
- PURE_RED, PURE_GREEN, PURE_BLUE

TIMING RULES:
- run_time must be positive (>0): use max(0.1, value) for computed values
- self.wait() must be positive: use max(0.1, value)

LATEX (MathTex/Tex):
- MathTex uses raw strings: r"\\frac{{a}}{{b}}" (double backslash, double braces in f-strings)
- Tex for mixed: r"Text with $x^2$"

POSITIONING:
- obj.to_edge(UP/DOWN/LEFT/RIGHT, buff=0.5)
- obj.to_corner(UL/UR/DL/DR, buff=0.5)
- obj.next_to(other, RIGHT, buff=0.25)
- obj.move_to(ORIGIN), obj.shift(UP * 2)

ANIMATIONS:
- FadeIn, FadeOut, Write, Create, Uncreate
- Transform, ReplacementTransform, TransformMatchingShapes
- self.play(anim1, anim2, run_time=1)
- self.add(obj) before FadeOut
- VGroup(obj1, obj2).arrange(DOWN, buff=0.5)"""


DIFF_CORRECTION_SYSTEM = f"""You fix Manim code errors using ONLY SEARCH/REPLACE blocks.

{MANIM_CONTEXT}

RESPONSE FORMAT (output ONLY these blocks, nothing else):

<<<<<<< SEARCH
exact lines from the broken code
=======
fixed replacement lines  
>>>>>>> REPLACE

RULES:
1. SEARCH text must EXACTLY match the broken code (copy-paste, preserve all whitespace)
2. Include 1-3 context lines before/after to make match unique
3. Fix ROOT CAUSE, not symptoms
4. Multiple blocks allowed for multiple fixes
5. NO explanations, NO markdown, ONLY SEARCH/REPLACE blocks

COMMON FIXES:
- BOTTOM → DOWN, TOP → UP (direction constants)
- blue → BLUE (color constants are uppercase)
- run_time=x where x could be ≤0 → run_time=max(0.1, x)
- self.wait(x) where x could be ≤0 → self.wait(max(0.1, x))
- NameError for color → Check spelling, use uppercase
- Object not in scene → Add self.add(obj) before animation"""


# JSON Schema for structured output (Gemini feature)
DIFF_CORRECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "fixes": {
            "type": "array",
            "description": "List of SEARCH/REPLACE fixes to apply",
            "items": {
                "type": "object",
                "properties": {
                    "search": {
                        "type": "string",
                        "description": "Exact text to find in the code (must match exactly including whitespace)"
                    },
                    "replace": {
                        "type": "string",
                        "description": "Replacement text with the fix applied"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Brief reason for this fix (1 sentence max)"
                    }
                },
                "required": ["search", "replace"]
            }
        }
    },
    "required": ["fixes"]
}


@dataclass
class ManimErrorContext:
    """Structured context about a Manim error"""
    error_type: str  # e.g., "NameError", "ValueError", "TypeError"
    error_message: str  # The actual error text
    line_number: Optional[int] = None
    problematic_code: Optional[str] = None


def parse_error_context(error_message: str) -> ManimErrorContext:
    """
    Parse error message to extract structured context.
    
    Args:
        error_message: Raw stderr from Manim
        
    Returns:
        Structured error context
    """
    import re
    
    # Extract error type
    error_type = "Unknown"
    type_match = re.search(r'(\w+Error|\w+Exception):', error_message)
    if type_match:
        error_type = type_match.group(1)
    
    # Extract line number
    line_number = None
    line_match = re.search(r'line (\d+)', error_message)
    if line_match:
        line_number = int(line_match.group(1))
    
    # Extract the actual error message
    msg_match = re.search(r'(?:Error|Exception): (.+?)(?:\n|$)', error_message)
    error_msg = msg_match.group(1) if msg_match else error_message[-200:]
    
    # Try to extract problematic code line
    code_match = re.search(r'^\s+(.+?)\n\s+\^+', error_message, re.MULTILINE)
    problematic_code = code_match.group(1).strip() if code_match else None
    
    return ManimErrorContext(
        error_type=error_type,
        error_message=error_msg,
        line_number=line_number,
        problematic_code=problematic_code
    )


def build_diff_correction_prompt(
    code: str,
    error_message: str,
    section: Optional[Dict[str, Any]] = None,
    error_context: Optional[str] = None
) -> str:
    """
    Build prompt for diff-based correction.
    
    Args:
        code: The full code that has the error
        error_message: The error message from Manim
        section: Optional section info for context
        error_context: Optional extracted context around error
        
    Returns:
        Formatted prompt string
    """
    # Parse structured error context
    parsed = parse_error_context(error_message)
    
    # Extract relevant parts of error message (last 1500 chars max)
    error_excerpt = error_message[-1500:] if len(error_message) > 1500 else error_message
    
    # Build section context
    section_info = ""
    if section:
        parts = []
        if section.get('narration'):
            parts.append(f"Scene content: {section['narration'][:150]}...")
        if section.get('target_duration'):
            parts.append(f"Target duration: {section['target_duration']}s")
        section_info = " | ".join(parts)
    
    # Build focused prompt
    prompt = f"""FIX THIS MANIM ERROR:

Error Type: {parsed.error_type}
{f"Line: {parsed.line_number}" if parsed.line_number else ""}
{f"Problem: {parsed.problematic_code}" if parsed.problematic_code else ""}

Full Error:
{error_excerpt}

{f"Context: {section_info}" if section_info else ""}

CODE TO FIX:
{code}

Output SEARCH/REPLACE blocks to fix this error. SEARCH must exactly match code."""
    
    return prompt


def build_structured_prompt(
    code: str,
    error_message: str,
    section: Optional[Dict[str, Any]] = None
) -> str:
    """
    Build prompt for structured JSON output.
    
    Args:
        code: The code with errors
        error_message: Error from Manim
        section: Optional section context
        
    Returns:
        Prompt for JSON structured output
    """
    parsed = parse_error_context(error_message)
    error_excerpt = error_message[-1500:] if len(error_message) > 1500 else error_message
    
    prompt = f"""Analyze this Manim error and provide fixes.

ERROR TYPE: {parsed.error_type}
{f"LINE NUMBER: {parsed.line_number}" if parsed.line_number else ""}
ERROR DETAILS:
{error_excerpt}

BROKEN CODE:
```python
{code}
```

Provide search/replace fixes. The "search" field must EXACTLY match text in the code above."""
    
    return prompt


def build_multi_error_prompt(
    code: str,
    errors: List[str],
    section: Optional[Dict[str, Any]] = None
) -> str:
    """
    Build prompt for fixing multiple errors at once.
    """
    errors_text = "\n\n---\n\n".join([f"Error {i+1}:\n{e[-500:]}" for i, e in enumerate(errors)])
    
    prompt = f"""Fix ALL these Manim errors using SEARCH/REPLACE blocks:

{errors_text}

CODE:
{code}

Output SEARCH/REPLACE blocks for ALL errors."""
    
    return prompt
