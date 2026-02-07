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

def _nullable(schema: dict) -> dict:
    """Build provider-compatible nullable schema nodes."""
    node = dict(schema)
    node["nullable"] = True
    return node


_NULLABLE_STRING = _nullable({"type": "string"})

# Choreography JSON Schema (V2 canonical shape)
CHOREOGRAPHY_SCHEMA = {
    "type": "object",
    "properties": {
        "version": {"type": "string", "enum": ["2.0"]},
        "scene": {
            "type": "object",
            "properties": {
                "mode": {"type": "string", "enum": ["2D", "3D"]},
                "camera": _nullable({"type": "object"}),
                "safe_bounds": {
                    "type": "object",
                    "properties": {
                        "x_min": {"type": "number"},
                        "x_max": {"type": "number"},
                        "y_min": {"type": "number"},
                        "y_max": {"type": "number"},
                    },
                    "required": ["x_min", "x_max", "y_min", "y_max"],
                },
            },
            "required": ["mode", "camera", "safe_bounds"],
        },
        "objects": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "kind": {"type": "string"},
                    "content": {
                        "type": "object",
                        "properties": {
                            "text": _NULLABLE_STRING,
                            "latex": _NULLABLE_STRING,
                            "asset_path": _NULLABLE_STRING,
                        },
                        "required": ["text", "latex", "asset_path"],
                    },
                    "placement": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "enum": ["absolute", "relative"]},
                            "absolute": {
                                "type": "object",
                                "nullable": True,
                                "properties": {
                                    "x": {"type": "number"},
                                    "y": {"type": "number"},
                                },
                                "required": ["x", "y"],
                            },
                            "relative": {
                                "type": "object",
                                "nullable": True,
                                "properties": {
                                    "relative_to": {"type": "string"},
                                    "relation": {
                                        "type": "string",
                                        "enum": ["above", "below", "left_of", "right_of"],
                                    },
                                    "spacing": {"type": "number"},
                                },
                                "required": ["relative_to", "relation", "spacing"],
                            },
                        },
                        "required": ["type", "absolute", "relative"],
                    },
                    "lifecycle": {
                        "type": "object",
                        "properties": {
                            "appear_at": {"type": "number"},
                            "remove_at": {"type": "number"},
                        },
                        "required": ["appear_at", "remove_at"],
                    },
                },
                "required": ["id", "kind", "content", "placement", "lifecycle"],
            },
        },
        "timeline": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "segment_index": {"type": "integer"},
                    "start_at": {"type": "number"},
                    "end_at": {"type": "number"},
                    "actions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "at": {"type": "number"},
                                "op": {
                                    "type": "string",
                                    "enum": [
                                        "Create",
                                        "FadeIn",
                                        "Transform",
                                        "ReplacementTransform",
                                        "Write",
                                        "Wait",
                                        "FadeOut",
                                    ],
                                },
                                "target": {"type": "string"},
                                "source": _NULLABLE_STRING,
                                "run_time": {"type": "number"},
                            },
                            "required": ["at", "op", "target", "source", "run_time"],
                        },
                    },
                },
                "required": ["segment_index", "start_at", "end_at", "actions"],
            },
        },
        "constraints": {
            "type": "object",
            "properties": {
                "language": {"type": "string"},
                "max_visible_objects": {"type": "integer"},
                "forbidden_constants": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "required": ["language", "max_visible_objects", "forbidden_constants"],
        },
        "notes": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["version", "scene", "objects", "timeline", "constraints", "notes"],
}

CHOREOGRAPHY_SCHEMA_V2 = CHOREOGRAPHY_SCHEMA


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
