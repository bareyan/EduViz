"""
Animation Editor Tool - In-place code modification.

Provides surgical edit capabilities for the animation agent, 
allowing for high-efficiency refinements without full code regeneration.
"""

from typing import Dict, Any

from app.core import get_logger
from app.services.infrastructure.llm.tools import BaseLLMTool, ToolExecutionError

logger = get_logger(__name__, component="animation_editor")

class ManimEditor(BaseLLMTool):
    """Handles in-place modifications to Manim code."""

    def execute(self, code: str, search_text: str, replacement_text: str) -> str:
        """Applies a surgical string replacement to the code.
        
        Args:
            code: The current full Manim code.
            search_text: The exact text block to search for.
            replacement_text: The replacement text block.
            
        Returns:
            The modified code string.
            
        Raises:
            ToolExecutionError: If the search_text is not found or is ambiguous.
        """
        occurences = code.count(search_text)
        
        if occurences == 0:
            logger.warning("Exact search text not found in code.")
            raise ToolExecutionError(
                "The search text was not found in the code. "
                "Please provide an EXACT match of the lines you wish to change."
            )
        
        if occurences > 1:
            raise ToolExecutionError(
                f"The search text matches multiple locations ({occurences}). "
                "Please include more context lines to uniquely identify the section."
            )
        
        return code.replace(search_text, replacement_text)

    @property
    def tool_definition(self) -> Dict[str, Any]:
        """Returns the Gemini-compatible tool definition schema."""
        return {
            "name": "apply_surgical_edit",
            "description": "Applies an in-place edit to the current Manim code. Use this for precise fixes.",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "code": {
                        "type": "STRING",
                        "description": "The current full Manim code to edit."
                    },
                    "search_text": {
                        "type": "STRING",
                        "description": "The exact literal text block to find in the code (provide 2-3 lines of context)."
                    },
                    "replacement_text": {
                        "type": "STRING",
                        "description": "The new text block that will replace the search_text."
                    }
                },
                "required": ["code", "search_text", "replacement_text"]
            }
        }
