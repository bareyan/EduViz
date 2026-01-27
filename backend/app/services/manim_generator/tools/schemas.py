"""
Tool Schemas for Gemini Function Calling

Defines JSON schemas for all Manim-related tools.
These schemas tell Gemini exactly what structure to return.
"""

# =============================================================================
# GENERATION TOOLS
# =============================================================================

GENERATE_CODE_SCHEMA = {
    "type": "object",
    "description": "Generate complete Manim animation code",
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


# =============================================================================
# CORRECTION TOOLS
# =============================================================================

SEARCH_REPLACE_SCHEMA = {
    "type": "object",
    "description": "Fix code using search and replace",
    "properties": {
        "fixes": {
            "type": "array",
            "description": "List of fixes to apply",
            "items": {
                "type": "object",
                "properties": {
                    "search": {
                        "type": "string",
                        "description": "Exact text to find (must match exactly including whitespace)"
                    },
                    "replace": {
                        "type": "string",
                        "description": "Replacement text"
                    },
                    "reason": {
                        "type": "string",
                        "description": "Brief reason for this fix"
                    }
                },
                "required": ["search", "replace"]
            }
        }
    },
    "required": ["fixes"]
}


ANALYSIS_SCHEMA = {
    "type": "object",
    "description": "Analyze code or error",
    "properties": {
        "issue_type": {
            "type": "string",
            "enum": ["syntax_error", "runtime_error", "visual_issue", "timing_issue", "api_error"],
            "description": "Type of issue detected"
        },
        "root_cause": {
            "type": "string",
            "description": "Root cause of the issue"
        },
        "affected_lines": {
            "type": "array",
            "items": {"type": "integer"},
            "description": "Line numbers affected"
        },
        "suggested_fix": {
            "type": "string",
            "description": "Suggested fix approach"
        }
    },
    "required": ["issue_type", "root_cause"]
}


# =============================================================================
# VISUAL QC TOOLS
# =============================================================================

VISUAL_QC_SCHEMA = {
    "type": "object",
    "description": "Visual quality control results",
    "properties": {
        "status": {
            "type": "string",
            "enum": ["pass", "issues_found"],
            "description": "Overall QC status"
        },
        "errors": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["overlap", "offscreen", "timing", "readability"],
                        "description": "Error type"
                    },
                    "description": {"type": "string"},
                    "timestamp": {"type": "number", "description": "When error occurs (seconds)"},
                    "severity": {
                        "type": "string",
                        "enum": ["critical", "major", "minor"]
                    }
                },
                "required": ["type", "description"]
            }
        }
    },
    "required": ["status"]
}
