"""
Base Prompting Engine

Provides core LLM interaction functionality with unified client handling,
response parsing, retries, and cost tracking.
"""

import asyncio
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass

from app.services.infrastructure.llm.gemini.client import (
    create_client,
    GenerationConfig as UnifiedGenerationConfig
)
from app.config.models import get_model_config, get_thinking_config
from app.services.infrastructure.llm.cost_tracker import CostTracker
from app.services.infrastructure.parsing import parse_json_response


@dataclass
class PromptConfig:
    """Configuration for a prompt execution"""
    model_name: Optional[str] = None  # If None, uses config's model
    temperature: float = 1.0
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    max_output_tokens: Optional[int] = None
    max_retries: int = 3
    timeout: Optional[float] = None
    enable_thinking: bool = False
    response_format: str = "text"  # "text", "json", or "function_call"
    system_instruction: Optional[str] = None
    response_schema: Optional[Any] = None


class PromptingEngine:
    """
    Centralized engine for all LLM interactions.
    
    Responsibilities:
    - Unified Gemini client management
    - Request/response handling
    - Retry logic with exponential backoff
    - Cost tracking integration
    - Response parsing (text, JSON, function calls)
    """

    def __init__(
        self,
        config_key: str = "script_generation",
        cost_tracker: Optional[CostTracker] = None,
        pipeline_name: Optional[str] = None,
    ):
        """Initialize the prompting engine.

        Args:
            config_key: Key in model config (e.g., "script_generation", "manim_generation")
            cost_tracker: Optional cost tracker instance
            pipeline_name: Optional pipeline override (avoids global mutation)
        """
        self.config_key = config_key
        self.pipeline_name = pipeline_name
        self.client = create_client()
        self.types = self.client._types_module
        self.cost_tracker = cost_tracker or CostTracker()

    def _get_config(self):
        """Resolve the model config with optional pipeline override."""
        return get_model_config(self.config_key)

    def _get_generation_config(
        self,
        prompt_config: PromptConfig
    ) -> Optional[UnifiedGenerationConfig]:
        """Build generation config from prompt config"""
        config = self._get_config()
        kwargs = {}
        
        if prompt_config.temperature != 1.0:
            kwargs["temperature"] = prompt_config.temperature

        if prompt_config.top_p is not None:
            kwargs["top_p"] = prompt_config.top_p

        if prompt_config.top_k is not None:
            kwargs["top_k"] = prompt_config.top_k

        if prompt_config.max_output_tokens is not None:
            kwargs["max_output_tokens"] = prompt_config.max_output_tokens
            
        if prompt_config.enable_thinking:
            thinking_config = get_thinking_config(config)
            if thinking_config:
                kwargs["thinking_config"] = thinking_config
                
        if prompt_config.response_format == "json":
            kwargs["response_mime_type"] = "application/json"

        if prompt_config.response_schema is not None:
            kwargs["response_schema"] = prompt_config.response_schema

        if prompt_config.system_instruction:
            kwargs["system_instruction"] = prompt_config.system_instruction
            
        return UnifiedGenerationConfig(**kwargs) if kwargs else None

    async def generate(
        self,
        prompt: str,
        config: Optional[PromptConfig] = None,
        tools: Optional[List[Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
        system_instruction: Optional[str] = None,
        response_schema: Optional[Any] = None,
        model: Optional[str] = None,
        contents: Optional[Union[str, List[Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a response from the LLM.
        
        Args:
            prompt: The prompt text
            config: Optional prompt configuration
            tools: Optional list of function calling tools
            context: Optional context for error messages/logging
            
        Returns:
            Dict containing:
                - success: bool
                - response: str (text response)
                - function_calls: List[Dict] (if using function calling)
                - parsed_json: Dict (if response_format is "json")
                - error: str (if failed)
                - usage: Dict (token usage info)
        """
        config = config or PromptConfig()
        if system_instruction or system_prompt:
            config.system_instruction = system_instruction or system_prompt
        if response_schema is not None:
            config.response_schema = response_schema
        config_obj = self._get_config()
        model_name = model or config.model_name or config_obj.model_name
        payload = contents if contents is not None else prompt
        
        for attempt in range(config.max_retries):
            try:
                # Build generation config
                gen_config = self._get_generation_config(config)
                
                # Get model - use client.models.generate_content for unified client
                if config.timeout:
                    response = await asyncio.wait_for(
                        asyncio.to_thread(
                            self.client.models.generate_content,
                            model=model_name,
                            contents=payload,
                            tools=tools,
                            config=gen_config
                        ),
                        timeout=config.timeout,
                    )
                else:
                    response = await asyncio.to_thread(
                        self.client.models.generate_content,
                        model=model_name,
                        contents=payload,
                        tools=tools,
                        config=gen_config
                    )
                
                # Track costs
                if hasattr(response, 'usage_metadata'):
                    usage = {
                        'input_tokens': response.usage_metadata.prompt_token_count,
                        'output_tokens': response.usage_metadata.candidates_token_count,
                        'total_tokens': response.usage_metadata.total_token_count,
                    }
                    self.cost_tracker.track_request(
                        model_name=model_name,
                        input_tokens=usage['input_tokens'],
                        output_tokens=usage['output_tokens']
                    )
                else:
                    usage = {}
                
                # Parse response based on format
                result = {
                    "success": True,
                    "usage": usage,
                    "raw_response": response,
                }
                
                # Handle function calls
                if tools and hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    if hasattr(candidate.content, 'parts'):
                        function_calls = []
                        for part in candidate.content.parts:
                            if hasattr(part, 'function_call') and part.function_call:
                                fc = part.function_call
                                function_calls.append({
                                    "name": fc.name,
                                    "args": dict(fc.args) if fc.args else {}
                                })
                        if function_calls:
                            result["function_calls"] = function_calls
                
                # Get text response
                text_response = response.text if hasattr(response, 'text') else ""
                result["response"] = text_response
                
                # Parse JSON if requested
                if config.response_format == "json" and text_response:
                    try:
                        result["parsed_json"] = parse_json_response(text_response)
                    except Exception as e:
                        result["json_parse_error"] = str(e)
                
                return result
                
            except asyncio.TimeoutError:
                if attempt < config.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                return {
                    "success": False,
                    "error": "Request timed out",
                    "context": context,
                }
                
            except Exception as e:
                if attempt < config.max_retries - 1:
                    # Exponential backoff
                    await asyncio.sleep(2 ** attempt)
                    continue
                    
                return {
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "context": context,
                }
        
        return {
            "success": False,
            "error": f"Failed after {config.max_retries} retries",
            "context": context,
        }

    def generate_sync(
        self,
        prompt: str,
        config: Optional[PromptConfig] = None,
        tools: Optional[List[Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        system_prompt: Optional[str] = None,
        system_instruction: Optional[str] = None,
        response_schema: Optional[Any] = None,
        model: Optional[str] = None,
        contents: Optional[Union[str, List[Any]]] = None,
    ) -> Dict[str, Any]:
        """Synchronous wrapper for generate()"""
        return asyncio.run(
            self.generate(
                prompt,
                config,
                tools,
                context,
                system_prompt,
                system_instruction,
                response_schema,
                model,
                contents,
            )
        )
