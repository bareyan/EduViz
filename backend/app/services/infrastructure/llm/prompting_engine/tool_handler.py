"""
Tool Handler for Function Calling

Manages tool/function definitions and execution for LLM function calling.
"""

from typing import Dict, Any, List, Callable
from dataclasses import dataclass


@dataclass
class Tool:
    """Represents a function calling tool"""
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Callable[[Dict[str, Any]], Any]


class ToolHandler:
    """
    Manages function calling tools for LLM interactions.
    
    Responsibilities:
    - Tool registration
    - Schema generation for Gemini API
    - Tool execution
    - Response handling
    """

    def __init__(self, types_module):
        """
        Initialize tool handler.
        
        Args:
            types_module: Gemini types module (for FunctionDeclaration, etc.)
        """
        self.types = types_module
        self.tools: Dict[str, Tool] = {}

    def register_tool(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        handler: Callable[[Dict[str, Any]], Any]
    ):
        """
        Register a new tool.
        
        Args:
            name: Tool name
            description: What the tool does
            parameters: JSON schema for parameters
            handler: Function to execute the tool
        """
        self.tools[name] = Tool(
            name=name,
            description=description,
            parameters=parameters,
            handler=handler
        )

    def get_tool_declarations(self) -> List[Any]:
        """
        Generate Gemini API tool declarations.
        
        Returns:
            List of FunctionDeclaration objects for Gemini API
        """
        declarations = []
        for tool in self.tools.values():
            declarations.append(
                self.types.FunctionDeclaration(
                    name=tool.name,
                    description=tool.description,
                    parameters=tool.parameters
                )
            )
        return [self.types.Tool(function_declarations=declarations)] if declarations else []

    async def execute_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a tool by name.
        
        Args:
            name: Tool name
            args: Tool arguments
            
        Returns:
            Dict with:
                - success: bool
                - result: Any (tool output)
                - error: str (if failed)
        """
        if name not in self.tools:
            return {
                "success": False,
                "error": f"Unknown tool: {name}"
            }

        try:
            tool = self.tools[name]
            result = tool.handler(args)
            
            # Handle async handlers
            if hasattr(result, '__await__'):
                result = await result
            
            return {
                "success": True,
                "result": result
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "error_type": type(e).__name__
            }

    def execute_tool_sync(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Synchronous wrapper for execute_tool"""
        import asyncio
        return asyncio.run(self.execute_tool(name, args))


def create_manim_tools(types_module, code_context: Dict[str, Any]) -> ToolHandler:
    """
    Create standard Manim generation tools.
    
    Args:
        types_module: Gemini types module
        code_context: Dict with validation functions and current code
        
    Returns:
        Configured ToolHandler with Manim tools
    """
    from app.services.pipeline.animation.generation.validation import CodeValidator
    
    handler = ToolHandler(types_module)
    validator = CodeValidator()
    
    # Tool: Generate complete code
    handler.register_tool(
        name="generate_manim_code",
        description="Generate complete Manim animation code for a section",
        parameters={
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Complete Python code for the Manim scene"
                }
            },
            "required": ["code"]
        },
        handler=lambda args: validator.validate_code(args["code"])
    )
    
    # Tool: Search and replace
    handler.register_tool(
        name="search_replace",
        description="Search for exact text and replace it with new text",
        parameters={
            "type": "object",
            "properties": {
                "search": {
                    "type": "string",
                    "description": "Exact text to search for (must be unique)"
                },
                "replace": {
                    "type": "string",
                    "description": "Text to replace with"
                }
            },
            "required": ["search", "replace"]
        },
        handler=lambda args: _handle_search_replace(
            code_context.get("current_code", ""),
            args["search"],
            args["replace"]
        )
    )
    
    return handler


def _handle_search_replace(code: str, search: str, replace: str) -> Dict[str, Any]:
    """Handle search/replace tool execution"""
    if not search or search not in code:
        return {
            "success": False,
            "error": "Search text not found or not unique"
        }
    
    # Check uniqueness
    if code.count(search) > 1:
        return {
            "success": False,
            "error": f"Search text appears {code.count(search)} times, must be unique"
        }
    
    new_code = code.replace(search, replace, 1)
    
    from app.services.pipeline.animation.generation.validation import CodeValidator
    validator = CodeValidator()
    validation = validator.validate_code(new_code)
    
    if validation["valid"]:
        return {
            "success": True,
            "code": new_code
        }
    else:
        return {
            "success": False,
            "error": f"Replacement resulted in invalid code: {validation.get('error', 'Unknown error')}"
        }
