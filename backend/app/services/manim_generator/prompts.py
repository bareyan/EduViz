"""
Manim Generator Prompts - Compatibility Layer

Provides prompts and helpers for the renderer and code_helpers modules.
Uses the centralized tools module for consistency.

NOTE: New code should import directly from .tools module.
This file provides backward compatibility for renderer.py and code_helpers.py.
"""

from typing import Dict, Any, Optional, List

# Import from centralized tools
from .tools import (
    get_manim_reference,
    get_style_config,
    get_style_instructions,
    get_animation_guidance,
    get_language_instructions,
    SEARCH_REPLACE_SCHEMA,
)


# =============================================================================
# CONSTANTS
# =============================================================================

MANIM_VERSION = "0.18.1"

# Get Manim context from centralized tools
MANIM_CONTEXT = get_manim_reference()


# =============================================================================
# THEME SETUP CODE (for code_helpers.py)
# =============================================================================

def get_theme_setup_code(style: str = "3b1b") -> str:
    """Get theme setup code for a scene based on style"""
    config = get_style_config(style)
    
    # Different styles have different background setup
    if style == "3b1b" or config.background.startswith("#"):
        # Dark theme - uses background color
        bg_color = config.background.replace("#", "")
        return f'''        # Theme: {config.name}
        self.camera.background_color = "#{bg_color}"'''
    elif style == "clean":
        return '''        # Theme: Clean Light
        self.camera.background_color = WHITE'''
    else:
        # Default dark theme
        return '''        # Theme: Default Dark
        self.camera.background_color = "#1C1C1C"'''


def get_color_instructions(style: str = "3b1b") -> str:
    """Get color instructions for a style (alias for get_style_instructions)"""
    return get_style_instructions(style)


# =============================================================================
# CORRECTION PROMPTS (for renderer.py correct_manim_code)
# =============================================================================

CORRECTION_SYSTEM_INSTRUCTION = f"""You are an expert Manim code debugger.
Your task is to fix Python/Manim code errors.

{MANIM_CONTEXT}

RULES:
1. Only output the corrected construct() method body
2. Do NOT include class definition or imports
3. Preserve the original animation intent
4. Keep timing (self.wait, run_time) as close to original as possible
5. Fix only the specific error - don't refactor working code

OUTPUT FORMAT:
Return ONLY the construct() method body code.
No markdown, no explanations, just the fixed code.
"""


def build_correction_prompt(
    code: str,
    error_message: str,
    section: Optional[Dict[str, Any]] = None
) -> str:
    """Build prompt for code correction"""
    timing_info = ""
    if section:
        duration = section.get("audio_duration", section.get("duration", 30))
        timing_info = f"\nTARGET DURATION: {duration}s (preserve timing!)"
    
    return f"""Fix the error in this Manim code.

ERROR MESSAGE:
{error_message}

CURRENT CODE:
```python
{code}
```
{timing_info}

Return the FIXED construct() method body ONLY (no class definition, no imports).
"""


# =============================================================================
# VISUAL FIX PROMPTS (for renderer.py generate_visual_fix)
# =============================================================================

def build_visual_fix_prompt(
    code: str,
    error_report: str,
    section: Optional[Dict[str, Any]] = None
) -> str:
    """Build prompt for visual QC fixes"""
    timing_info = ""
    if section:
        duration = section.get("audio_duration", section.get("duration", 30))
        timing_info = f"\nTARGET DURATION: {duration}s"
    
    return f"""Fix the visual layout issues in this Manim animation.

VISUAL ERROR REPORT:
{error_report}

CURRENT CODE:
```python
{code}
```
{timing_info}

COMMON FIXES:
- Text overflow: Reduce font_size (24 for body, 36 for titles max)
- Overlapping: Increase buff values in next_to(), use to_edge() for margins
- Timing issues: Adjust self.wait() and run_time values
- Off-screen: Use to_edge(UP/DOWN, buff=0.5) to keep in bounds

Return the FIXED construct() method body ONLY.
"""


# =============================================================================
# RENDER FIX PROMPTS (for renderer.py fix_render_error)
# =============================================================================

RENDER_FIX_SYSTEM_INSTRUCTION = f"""You are an expert Manim animator fixing render errors.

{MANIM_CONTEXT}

Your task is to fix the code so it renders successfully.
Keep the original animation intent but fix the specific error.

OUTPUT: Complete working Manim scene file with imports.
"""


def build_render_fix_prompt(
    code: str,
    error_message: str,
    section: Optional[Dict[str, Any]] = None
) -> str:
    """Build prompt for fixing render errors"""
    timing_info = ""
    if section:
        duration = section.get("audio_duration", section.get("duration", 30))
        timing_info = f"\nRequired duration: {duration}s"
    
    return f"""Fix this Manim render error.

ERROR:
{error_message}

CODE:
```python
{code}
```
{timing_info}

Return the complete fixed Manim scene file (with imports and class definition).
"""


# =============================================================================
# TIMING HELPERS
# =============================================================================

def build_timing_context(section: Dict[str, Any], narration_segments: List = None) -> str:
    """Build timing context from section data"""
    segments = narration_segments or section.get("segments", [])
    
    if not segments:
        duration = section.get("audio_duration", section.get("duration", 30))
        return f"Total duration: {duration}s"
    
    lines = ["TIMING BREAKDOWN:"]
    cumulative = 0.0
    
    for i, seg in enumerate(segments):
        seg_duration = seg.get("duration", 5.0)
        seg_text = seg.get("tts_text", seg.get("narration", ""))[:40]
        lines.append(f"  [{cumulative:.1f}s-{cumulative + seg_duration:.1f}s]: \"{seg_text}...\"")
        cumulative += seg_duration
    
    lines.append(f"  TOTAL: {cumulative:.1f}s")
    return "\n".join(lines)


# =============================================================================
# VISUAL SCRIPT PROMPTS (backward compatibility)
# =============================================================================

def build_visual_script_prompt(
    section: Dict[str, Any],
    audio_duration: float,
    timing_context: str = ""
) -> str:
    """Build prompt for visual script generation"""
    title = section.get("title", "Section")
    narration = section.get("narration", section.get("tts_narration", ""))
    
    return f"""Create a visual script (storyboard) for this animation section.

TITLE: {title}
NARRATION: {narration[:500]}
DURATION: {audio_duration}s

{timing_context}

Create a timeline of visual elements and animations.
Format as markdown with timestamps and descriptions.
"""


def build_visual_script_analysis_prompt(visual_script: str, audio_duration: float) -> str:
    """Build prompt for analyzing visual script"""
    return f"""Analyze this visual script for potential layout issues.

VISUAL SCRIPT:
{visual_script}

TARGET DURATION: {audio_duration}s

Check for:
1. Overlapping elements
2. Text overflow risk
3. Timing issues
4. Spatial conflicts

Return JSON: {{"status": "ok"|"issues", "issues_found": N, "fixes": [...]}}
"""


def get_visual_script_analysis_schema() -> Dict:
    """Get JSON schema for visual script analysis"""
    return {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["ok", "issues"]},
            "issues_found": {"type": "integer"},
            "fixes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "issue": {"type": "string"},
                        "fix": {"type": "string"}
                    }
                }
            }
        },
        "required": ["status", "issues_found", "fixes"]
    }


def build_code_from_script_prompt(
    section: Dict[str, Any],
    visual_script: str,
    audio_duration: float,
    language_instructions: str = "",
    color_instructions: str = "",
    type_guidance: str = "",
    spatial_fixes: List = None
) -> str:
    """Build prompt for generating code from visual script"""
    title = section.get("title", "Section")
    
    prompt = f"""Generate Manim code from this visual script.

TITLE: {title}
DURATION: {audio_duration}s

VISUAL SCRIPT:
{visual_script}

{language_instructions}
{color_instructions}
{type_guidance}
"""
    
    if spatial_fixes:
        prompt += f"\n\nAPPLY THESE FIXES:\n"
        for fix in spatial_fixes:
            prompt += f"- {fix.get('fix', fix)}\n"
    
    prompt += "\nGenerate ONLY the construct() method body. No class, no imports."
    return prompt


def build_generation_prompt(
    section: Dict[str, Any],
    audio_duration: float,
    timing_context: str = "",
    language_instructions: str = "",
    color_instructions: str = "",
    type_guidance: str = ""
) -> str:
    """Build single-shot generation prompt"""
    title = section.get("title", "Section")
    narration = section.get("narration", section.get("tts_narration", ""))
    
    return f"""Generate Manim animation code for this section.

TITLE: {title}
NARRATION: {narration[:500]}
DURATION: {audio_duration}s

{timing_context}
{language_instructions}
{color_instructions}
{type_guidance}

Generate ONLY the construct() method body. No class, no imports.
Ensure animations are timed to match the duration.
"""
