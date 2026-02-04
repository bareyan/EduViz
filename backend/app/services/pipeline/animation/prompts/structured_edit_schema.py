"""
Structured Output Schemas for Animation Pipeline.
"""

from typing import Dict, Any

CODE_EDIT_SCHEMA: Dict[str, Any] = {
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
