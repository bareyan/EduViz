"""
Function calling tools for Manim code generation

Provides tool definitions and execution for LLM function calling.
Integrates with the validation package for clean separation of concerns.

Single Responsibility: Define tools and execute them, delegate validation logic.
"""

import re
from typing import Dict, Any, Tuple

from .validation import CodeValidator


def extract_code_from_response(response: str) -> str:
    """
    Extract Python code from various response formats.
    
    Args:
        response: Raw LLM response that may contain code blocks
        
    Returns:
        Extracted Python code
    """
    # Remove markdown code blocks
    if "```python" in response:
        parts = response.split("```python")
        if len(parts) > 1:
            code_part = parts[1].split("```")[0]
            return code_part.strip()
    elif "```" in response:
        parts = response.split("```")
        if len(parts) >= 3:
            return parts[1].strip()
    
    # If no code blocks, return as-is (assume it's all code)
    return response.strip()


def apply_search_replace(code: str, search: str, replace: str) -> Tuple[bool, str, str]:
    """
    Apply a search/replace operation on code.
    
    Args:
        code: Current code
        search: Exact text to find (must be unique)
        replace: Text to replace with
        
    Returns:
        Tuple of (success, new_code, error_message)
    """
    if not search:
        return False, code, "Search pattern cannot be empty"
    
    if search not in code:
        return False, code, "Search pattern not found in code"
    
    # Count occurrences
    count = code.count(search)
    if count > 1:
        return False, code, f"Search pattern appears {count} times - must be unique"
    
    new_code = code.replace(search, replace)
    return True, new_code, ""


# Tool definitions for function calling API
MANIM_TOOLS = [
    {
        "name": "create_code",
        "description": "Submit your generated Manim code. System will validate it (syntax, structure, imports, spatial layout) and return validation results.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The complete Manim code you generated"
                }
            },
            "required": ["code"]
        }
    },
    {
        "name": "apply_fix",
        "description": "Apply a fix to code using search/replace. The search string must match exactly and appear only once. Returns validation results for the fixed code.",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The current code"
                },
                "search": {
                    "type": "string",
                    "description": "The exact text to search for (must be unique)"
                },
                "replace": {
                    "type": "string",
                    "description": "The text to replace it with"
                },
                "reason": {
                    "type": "string",
                    "description": "Brief explanation of why this fix is needed"
                }
            },
            "required": ["code", "search", "replace", "reason"]
        }
    }
]


class ToolExecutor:
    """
    Executes function calling tools for code generation.
    
    Single Responsibility: Execute tools and delegate to appropriate validators.
    """
    
    def __init__(self):
        self.validator = CodeValidator()
    
    def execute(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool and return results.
        
        Args:
            tool_name: Name of the tool to execute
            parameters: Tool parameters
            
        Returns:
            Tool execution results
        """
        if tool_name == "create_code":
            return self._create_code(parameters)
        elif tool_name == "apply_fix":
            return self._apply_fix(parameters)
        else:
            return {"error": f"Unknown tool: {tool_name}"}
    
    def _create_code(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute create_code tool - validate and return results"""
        code = params.get("code", "")
        validation = self.validator.validate(code)
        return validation.to_dict()
    
    def _apply_fix(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute apply_fix tool and auto-validate the result"""
        code = params.get("code", "")
        search = params.get("search", "")
        replace = params.get("replace", "")
        reason = params.get("reason", "")
        
        success, new_code, error = apply_search_replace(code, search, replace)
        
        if success:
            # Auto-validate the fixed code
            validation = self.validator.validate(new_code)
            return {
                "success": True,
                "reason": reason,
                "validation": validation.to_dict()
            }
        else:
            return {
                "success": False,
                "error": error,
                "reason": reason
            }
    
    def _validate_and_return(self, code: str) -> Dict[str, Any]:
        """Validate code and return results (used internally)"""
        validation = self.validator.validate(code)
        return validation.to_dict()


# Schema for structured JSON responses (non-tool mode)
MANIM_CODE_SCHEMA = {
    "type": "object",
    "properties": {
        "code": {
            "type": "string",
            "description": "The complete Python/Manim code"
        },
        "explanation": {
            "type": "string",
            "description": "Brief explanation of the animation approach"
        }
    },
    "required": ["code"]
}
