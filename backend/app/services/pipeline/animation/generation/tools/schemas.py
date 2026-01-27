"""
Tool Schemas for Gemini Function Calling

Defines JSON schemas for all Manim-related tools.
These schemas tell Gemini exactly what structure to return.
"""

# =============================================================================
# CODE WRITING AND FIXING TOOLS
# =============================================================================

WRITE_CODE_SCHEMA = {
    "type": "object",
    "description": "Write complete Manim animation code (full replacement)",
    "properties": {
        "code": {
            "type": "string",
            "description": "Complete Python code for the construct() method body. NO class definition, NO imports."
        },
        "objects_used": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of Manim objects used (Text, MathTex, Circle, etc.)"
        },
        "estimated_duration": {
            "type": "number",
            "description": "Estimated animation duration in seconds"
        }
    },
    "required": ["code"]
}


FIX_CODE_SCHEMA = {
    "type": "object",
    "description": "Fix code using targeted search/replace operations (preserves working code)",
    "properties": {
        "fixes": {
            "type": "array",
            "description": "List of targeted fixes to apply",
            "items": {
                "type": "object",
                "properties": {
                    "search": {
                        "type": "string",
                        "description": "Exact text to find (must match exactly including whitespace). Include enough context to make it unique."
                    },
                    "replace": {
                        "type": "string",
                        "description": "Replacement text (exact whitespace/indentation)"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Brief reason for this fix"
                    }
                },
                "required": ["search", "replace", "reason"]
            }
        },
        "description": {
            "type": "string",
            "description": "Overall description of what these fixes accomplish"
        }
    },
    "required": ["fixes"]
}


# Backward compatibility alias
GENERATE_CODE_SCHEMA = WRITE_CODE_SCHEMA


# =============================================================================
# VISUAL SCRIPT SCHEMA
# =============================================================================

VISUAL_SCRIPT_SCHEMA = {
    "type": "object",
    "description": "Visual storyboard for animation",
    "properties": {
        "segments": {
            "type": "array",
            "description": "Animation segments with timing",
            "items": {
                "type": "object",
                "properties": {
                    "start_time": {"type": "number", "description": "Start time in seconds"},
                    "end_time": {"type": "number", "description": "End time in seconds"},
                    "visual_elements": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "What appears on screen"
                    },
                    "animations": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Animations to use (FadeIn, Write, Transform, etc.)"
                    },
                    "narration_sync": {
                        "type": "string",
                        "description": "Corresponding narration text"
                    }
                },
                "required": ["start_time", "end_time", "visual_elements"]
            }
        },
        "total_duration": {
            "type": "number",
            "description": "Total animation duration"
        }
    },
    "required": ["segments", "total_duration"]
}

