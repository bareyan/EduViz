"""
JSON Schemas for Structured Output

All response schemas for the animation pipeline LLM interactions.
Ensures valid, parseable JSON with all required fields.

Organization:
- Choreography schemas: For visual planning stage
- Code edit schemas: For refinement/fixing stage
"""

# =============================================================================
# CHOREOGRAPHY SCHEMAS
# =============================================================================

# Choreography JSON Schema (Full)
CHOREOGRAPHY_SCHEMA = {
    "type": "object",
    "properties": {
        "scene_type": {
            "type": "string",
            "description": "Scene type: 2D or 3D"
        },
        "objects": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "type": {"type": "string"},
                    "text": {"type": "string"},
                    "latex": {"type": "string"},
                    "appears_at": {"type": "number"},
                    "removed_at": {"type": "number"},
                    "relative_to": {"type": "string"},
                    "relation": {"type": "string"},
                    "spacing": {"type": "number"}
                },
                "required": ["id", "type", "appears_at", "removed_at"]
            }
        },
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "segment_index": {"type": "integer"},
                    "start_time": {"type": "number"},
                    "end_time": {"type": "number"},
                    "steps": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "time": {"type": "number"},
                                "action": {"type": "string"},
                                "target": {"type": "string"},
                                "duration": {"type": "number"}
                            },
                            "required": ["time", "action"]
                        }
                    }
                },
                "required": ["segment_index", "start_time", "end_time", "steps"]
            }
        }
    },
    "required": ["scene_type", "objects", "segments"]
}


# =============================================================================
# CODE REFINEMENT SCHEMAS
# =============================================================================

# Surgical code edit schema for refinement stage
CODE_EDIT_SCHEMA = {
    "type": "object",
    "properties": {
        "analysis": {
            "type": "string",
            "description": "Brief analysis of the error and fix strategy",
            "maxLength": 200
        },
        "edits": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "search_text": {
                        "type": "string",
                        "description": "Exact text to find with 2-3 lines of context",
                        "maxLength": 5000
                    },
                    "replacement_text": {
                        "type": "string",
                        "description": "New text to replace search_text with",
                        "maxLength": 5000
                    }
                },
                "required": ["search_text", "replacement_text"]
            },
            "description": "List of surgical edits",
            "maxItems": 10
        }
    },
    "required": ["analysis", "edits"]
}


# =============================================================================
# VISION QC SCHEMA
# =============================================================================

VISION_QC_SCHEMA = {
    "type": "object",
    "properties": {
        "issues": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "frame": {"type": "string"},
                    "time_sec": {"type": "number"},
                    "severity": {
                        "type": "string",
                        "enum": ["critical", "warning", "info"],
                    },
                    "confidence": {
                        "type": "string",
                        "enum": ["high", "medium", "low"],
                    },
                    "message": {"type": "string"},
                    "fix_hint": {"type": "string"},
                },
                "required": ["frame", "time_sec", "severity", "confidence", "message"],
            },
        },
    },
    "required": ["issues"],
}
