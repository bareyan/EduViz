"""
Tool Infrastructure - Unified interface for LLM tool definitions and execution.

Provides a standard base class for all tools that interact with LLMs, ensuring
consistent schema definitions and execution patterns across the application.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List


class BaseLLMTool(ABC):
    """
    Base class for all LLM-callable tools.
    
    Enforces a consistent interface for:
    - Tool definition (schema for LLM)
    - Execution logic
    - Error handling
    
    Usage:
        class MyTool(BaseLLMTool):
            @property
            def tool_definition(self) -> Dict[str, Any]:
                return {
                    "name": "my_tool",
                    "description": "What the tool does",
                    "parameters": {...}
                }
            
            def execute(self, param1: str, param2: int) -> Any:
                # Implementation
                return result
    """
    
    @property
    @abstractmethod
    def tool_definition(self) -> Dict[str, Any]:
        """
        Returns the Gemini-compatible tool definition schema.
        
        Must follow Gemini Function Calling schema:
        {
            "name": "tool_name",
            "description": "Clear description of what the tool does",
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "param_name": {
                        "type": "STRING",  # STRING, NUMBER, BOOLEAN, ARRAY, OBJECT
                        "description": "Parameter description"
                    }
                },
                "required": ["param_name"]
            }
        }
        
        Returns:
            Tool definition dictionary
        """
        pass
    
    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """
        Execute the tool action.
        
        Args:
            **kwargs: Tool parameters as defined in tool_definition
        
        Returns:
            Tool execution result
        
        Raises:
            ValueError: If parameters are invalid
            ToolExecutionError: If execution fails
        """
        pass
    
    def validate_params(self, params: Dict[str, Any]) -> None:
        """
        Validate that provided parameters match the tool definition.
        
        Args:
            params: Parameters to validate
        
        Raises:
            ValueError: If required parameters are missing or invalid
        """
        definition = self.tool_definition
        required = definition.get("parameters", {}).get("required", [])
        
        for req_param in required:
            if req_param not in params:
                raise ValueError(
                    f"Missing required parameter '{req_param}' for tool '{definition['name']}'"
                )


class ToolExecutionError(Exception):
    """Raised when a tool execution fails."""
    pass


def create_tool_declaration(tool: BaseLLMTool, types_module) -> Any:
    """
    Create a Gemini-compatible Tool declaration from a BaseLLMTool.
    
    Args:
        tool: Tool instance that implements BaseLLMTool
        types_module: Gemini types module (from PromptingEngine.types)
    
    Returns:
        types.Tool object ready to pass to generate()
    
    Example:
        tool = ManimEditor()
        declaration = create_tool_declaration(tool, engine.types)
        response = await engine.generate(..., tools=[declaration])
    """
    definition = tool.tool_definition
    
    return types_module.Tool(
        function_declarations=[
            types_module.FunctionDeclaration(
                name=definition["name"],
                description=definition["description"],
                parameters=definition["parameters"]
            )
        ]
    )


def create_tool_response(function_name: str, result: Dict[str, Any], types_module) -> Any:
    """
    Create a Gemini-compatible function response Part.
    
    Args:
        function_name: Name of the function that was called
        result: Result dictionary from tool execution
        types_module: Gemini types module
    
    Returns:
        types.Part object with function_response
    
    Example:
        result = {"status": "success", "message": "Done"}
        response_part = create_tool_response("my_tool", result, engine.types)
        history.append(types.Content(role="user", parts=[response_part]))
    """
    return types_module.Part(
        function_response=types_module.FunctionResponse(
            name=function_name,
            response=result
        )
    )


def execute_tool_calls(
    tool_calls: List[Dict[str, Any]],
    available_tools: Dict[str, BaseLLMTool]
) -> List[Dict[str, Any]]:
    """
    Execute a batch of tool calls and return results.
    
    Args:
        tool_calls: List of tool calls from LLM response
                   [{"name": "tool_name", "args": {...}}]
        available_tools: Dict mapping tool names to tool instances
    
    Returns:
        List of result dictionaries
    
    Example:
        tools = {"edit_code": ManimEditor()}
        calls = response.get("function_calls", [])
        results = execute_tool_calls(calls, tools)
    """
    results = []
    
    for call in tool_calls:
        tool_name = call["name"]
        tool_args = call["args"]
        
        if tool_name not in available_tools:
            results.append({
                "status": "error",
                "error": f"Unknown tool: {tool_name}"
            })
            continue
        
        tool = available_tools[tool_name]
        
        try:
            tool.validate_params(tool_args)
            result = tool.execute(**tool_args)
            results.append({
                "status": "success",
                "result": result
            })
        except ValueError as e:
            results.append({
                "status": "error",
                "error": f"Invalid parameters: {str(e)}"
            })
        except ToolExecutionError as e:
            results.append({
                "status": "error",
                "error": f"Execution failed: {str(e)}"
            })
        except Exception as e:
            results.append({
                "status": "error",
                "error": f"Unexpected error: {str(e)}"
            })
    
    return results
