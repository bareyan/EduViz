"""
Structured Output Schemas for Animation Pipeline.
"""

from typing import Dict, Any

CODE_EDIT_SCHEMA: Dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "analysis": {
            "type": "STRING", 
            "description": "Brief analysis of the error and fix strategy"
        },
        "edits": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "search_text": {
                        "type": "STRING",
                        "description": "Exact text to find (2-3 lines of context)"
                    },
                    "replacement_text": {
                        "type": "STRING",
                        "description": "New text to replace the search_text with"
                    }
                },
                "required": ["search_text", "replacement_text"]
            },
            "description": "List of surgical edits to apply"
        }
    },
    "required": ["edits"]
}
