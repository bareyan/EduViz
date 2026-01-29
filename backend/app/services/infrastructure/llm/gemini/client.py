"""
Unified Gemini Client - Works with both Gemini API and Vertex AI

This module provides a unified interface for both:
1. Gemini API (using API keys)
2. Vertex AI (using GCP credentials)

The client automatically detects which backend to use based on environment
variables and provides a consistent interface for both.
"""

import os
from typing import Optional, Dict, Any, List, Union
from dataclasses import dataclass

from app.core.llm_logger import get_llm_logger


@dataclass
class GenerationConfig:
    """Configuration for content generation"""
    temperature: float = 1.0
    top_p: float = 0.95
    top_k: int = 40
    max_output_tokens: int = 8192
    thinking_config: Optional[Dict[str, str]] = None
    response_mime_type: Optional[str] = None
    response_schema: Optional[Any] = None
    system_instruction: Optional[Any] = None
    media_resolution: Optional[str] = None


class UnifiedGeminiClient:
    """
    Unified client that works with both Gemini API and Vertex AI.
    
    Environment Variables:
        USE_VERTEX_AI: Set to 'true' to use Vertex AI instead of Gemini API
        GEMINI_API_KEY: API key for Gemini API (when USE_VERTEX_AI=false)
        GCP_PROJECT_ID: GCP project ID (when USE_VERTEX_AI=true)
        GCP_LOCATION: GCP region (default: us-central1, when USE_VERTEX_AI=true)
    
    Usage:
        # Automatically detects which backend to use
        client = UnifiedGeminiClient()
        
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Hello!",
            config=GenerationConfig(temperature=0.7)
        )
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the unified client.
        
        Args:
            api_key: Optional API key. If not provided, will use GEMINI_API_KEY env var
        """
        self.use_vertex_ai = os.getenv("USE_VERTEX_AI", "false").lower() == "true"
        self.backend = None
        self.models = None
        self._types_module = None  # Cache for types module
        self.llm_logger = get_llm_logger()  # Initialize LLM logger

        if self.use_vertex_ai:
            self._init_vertex_ai()
        else:
            self._init_gemini_api(api_key)

    def _init_gemini_api(self, api_key: Optional[str] = None):
        """Initialize Gemini API backend"""
        try:
            from google import genai
            from google.genai import types
            print(f"DEBUG: Inside _init_gemini_api. genai.Client is {genai.Client}")
            
            api_key = api_key or os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("GEMINI_API_KEY environment variable is required when USE_VERTEX_AI=false")

            self.backend = genai.Client(api_key=api_key)
            self.models = GeminiAPIModels(self.backend)
            self._types_module = types  # Cache types module

        except ImportError:
            raise ImportError(
                "google-generativeai package not found. "
                "Install it with: pip install google-generativeai"
            )

    def _init_vertex_ai(self):
        """Initialize Vertex AI backend"""
        try:
            import vertexai

            project_id = os.getenv("GCP_PROJECT_ID")
            location = os.getenv("GCP_LOCATION", "us-central1")

            if not project_id:
                raise ValueError("GCP_PROJECT_ID environment variable is required when USE_VERTEX_AI=true")

            vertexai.init(project=project_id, location=location)
            self.backend = vertexai
            self.models = VertexAIModels(vertexai, location)
            # Cache a compatible types module for Vertex AI
            self._types_module = self._create_vertex_types_wrapper()

        except ImportError:
            raise ImportError(
                "google-cloud-aiplatform package not found. "
                "Install it with: pip install google-cloud-aiplatform"
            )

    def _create_vertex_types_wrapper(self):
        """Create a wrapper that provides Gemini API-like types for Vertex AI"""
        from vertexai.generative_models import Part, Content
        try:
            # Try to import Schema from Vertex AI
            from vertexai.generative_models._generative_models import Schema, Type
        except ImportError:
            # Fallback if not available
            Schema = None
            Type = None

        class VertexTypesWrapper:
            """Wrapper to make Vertex AI types compatible with Gemini API code"""
            # Assign the imported classes
            pass

        # Set class attributes dynamically
        VertexTypesWrapper.Part = Part
        VertexTypesWrapper.Content = Content
        
        # Add Schema and Type if available
        if Schema:
            VertexTypesWrapper.Schema = Schema
        if Type:
            VertexTypesWrapper.Type = Type

        # For backward compatibility with code that checks types.GenerateContentConfig
        @staticmethod
        def GenerateContentConfig(**kwargs):
            # Return the config dict, actual conversion happens in VertexAIModels
            return kwargs

        class ThinkingConfig:
            def __init__(self, thinking_level):
                self.thinking_level = thinking_level

        VertexTypesWrapper.GenerateContentConfig = GenerateContentConfig
        VertexTypesWrapper.ThinkingConfig = ThinkingConfig

        return VertexTypesWrapper()


class GeminiAPIModels:
    """Gemini API models interface (wraps google-generativeai)"""

    def __init__(self, client):
        self.client = client
        self.llm_logger = get_llm_logger()

    def generate_content(
        self,
        model: str,
        contents: Union[str, List[Any]],
        config: Optional[GenerationConfig] = None,
        tools: Optional[List[Any]] = None,
    ):
        """
        Generate content using Gemini API.
        
        Args:
            model: Model name (e.g., "gemini-2.5-flash")
            contents: Text prompt or list of content parts
            config: Generation configuration
        
        Returns:
            Response object with .text property
        """
        from google.genai import types

        config = config or GenerationConfig()

        # Build generation config
        gen_config_dict = {
            "temperature": config.temperature,
            "top_p": config.top_p,
            "top_k": config.top_k,
            "max_output_tokens": config.max_output_tokens,
        }

        # Add thinking config if present
        # Note: Not all models support thinking_config (e.g., gemini-2.0-flash-exp)
        # The API will return an error if the model doesn't support it
        if config.thinking_config:
            gen_config_dict["thinking_config"] = config.thinking_config

        # Add response format if specified
        if config.response_mime_type:
            gen_config_dict["response_mime_type"] = config.response_mime_type

        if config.response_schema:
            gen_config_dict["response_schema"] = config.response_schema

        if config.system_instruction:
            gen_config_dict["system_instruction"] = config.system_instruction

        gen_config = types.GenerateContentConfig(**gen_config_dict)

        # Attach tools to config if supported (google.genai expects tools in config)
        if tools and hasattr(gen_config, "tools"):
            try:
                gen_config.tools = tools
            except Exception:
                # If assignment fails, we'll fall back to passing via kwargs below
                pass

        # Make the API call (handle older clients that might require tools kwarg)
        kwargs = {
            "model": model,
            "contents": contents,
            "config": gen_config,
        }

        # Only pass tools kwarg if config didn't capture it
        if tools and not getattr(gen_config, "tools", None):
            kwargs["tools"] = tools

        # Log the request before making the API call
        request_id = self.llm_logger.log_request(
            model=model,
            contents=contents,
            config=gen_config_dict,
            tools=tools,
            system_instruction=config.system_instruction if config else None
        )

        try:
            response = self.client.models.generate_content(**kwargs)
            
            # Log successful response
            self.llm_logger.log_response(
                request_id=request_id,
                response=response,
                success=True
            )
        except Exception as e:
            error_msg = str(e)

            # Retry without tools if the client version doesn't support them
            if "unexpected keyword argument 'tools'" in error_msg or "got an unexpected keyword argument 'tools'" in error_msg:
                kwargs.pop("tools", None)
                try:
                    response = self.client.models.generate_content(**kwargs)
                    # Log successful retry
                    self.llm_logger.log_response(
                        request_id=request_id,
                        response=response,
                        success=True,
                        metadata={"retry": "removed_tools"}
                    )
                except Exception as retry_error:
                    # Log failed retry
                    self.llm_logger.log_error(request_id, retry_error)
                    raise
            # If the error is about thinking_config not being supported, retry without it
            elif config.thinking_config and ("thinking_level is not supported" in error_msg or "thinking" in error_msg.lower()):
                print("[UnifiedGeminiClient] Model doesn't support thinking_config, retrying without it...")
                gen_config_dict_no_thinking = {k: v for k, v in gen_config_dict.items() if k != "thinking_config"}
                gen_config = types.GenerateContentConfig(**gen_config_dict_no_thinking)
                kwargs["config"] = gen_config
                try:
                    response = self.client.models.generate_content(**kwargs)
                    # Log successful retry
                    self.llm_logger.log_response(
                        request_id=request_id,
                        response=response,
                        success=True,
                        metadata={"retry": "removed_thinking_config"}
                    )
                except Exception as e2:
                    if "unexpected keyword argument 'tools'" in str(e2) or "got an unexpected keyword argument 'tools'" in str(e2):
                        kwargs.pop("tools", None)
                        try:
                            response = self.client.models.generate_content(**kwargs)
                            # Log successful retry
                            self.llm_logger.log_response(
                                request_id=request_id,
                                response=response,
                                success=True,
                                metadata={"retry": "removed_thinking_config_and_tools"}
                            )
                        except Exception as final_error:
                            # Log final failure
                            self.llm_logger.log_error(request_id, final_error)
                            raise
                    else:
                        # Log error
                        self.llm_logger.log_error(request_id, e2)
                        raise
            else:
                # Log error for unhandled exception
                self.llm_logger.log_error(request_id, e)
                raise

        return response


class VertexAIModels:
    """Vertex AI models interface (wraps vertexai)"""

    def __init__(self, vertexai_module, location: str):
        self.vertexai = vertexai_module
        self.location = location
        self.llm_logger = get_llm_logger()

    def generate_content(
        self,
        model: str,
        contents: Union[str, List[Any]],
        config: Optional[GenerationConfig] = None,
        tools: Optional[List[Any]] = None,
    ):
        """
        Generate content using Vertex AI.
        
        Args:
            model: Model name (e.g., "gemini-2.5-flash-002")
            contents: Text prompt or list of content parts
            config: Generation configuration
        
        Returns:
            Response object with .text property
        """
        from vertexai.generative_models import (
            GenerativeModel,
            GenerationConfig as VertexGenerationConfig
        )

        config = config or GenerationConfig()

        # Handle both GenerationConfig object and dict (from wrapper)
        if isinstance(config, dict):
            # Convert dict back to GenerationConfig
            config = GenerationConfig(**config)

        # Convert model name to Vertex AI format if needed
        model = self._convert_model_name(model)

        # Extract system_instruction if present in config
        system_instruction = None
        if hasattr(config, 'system_instruction'):
            system_instruction = config.system_instruction

        # Create model instance with system instruction if provided
        model_kwargs = {"model_name": model}
        if system_instruction:
            model_kwargs["system_instruction"] = system_instruction

        model_instance = GenerativeModel(**model_kwargs)

        # Build generation config
        gen_config_dict = {
            "temperature": config.temperature,
            "top_p": config.top_p,
            "top_k": config.top_k,
            "max_output_tokens": config.max_output_tokens,
        }

        # Add response format if specified (Vertex AI supports this)
        if config.response_mime_type:
            gen_config_dict["response_mime_type"] = config.response_mime_type

        if config.response_schema:
            gen_config_dict["response_schema"] = config.response_schema

        vertex_config = VertexGenerationConfig(**gen_config_dict)

        if tools and hasattr(vertex_config, "tools"):
            try:
                vertex_config.tools = tools
            except Exception:
                pass

        # Convert contents to Vertex AI format if needed
        if isinstance(contents, str):
            contents = [contents]

        # Log the request
        request_id = self.llm_logger.log_request(
            model=model,
            contents=contents,
            config=gen_config_dict,
            tools=tools,
            system_instruction=system_instruction
        )

        # Make the API call
        try:
            response = model_instance.generate_content(
                contents,
                generation_config=vertex_config,
                tools=tools
            )
            # Log successful response
            self.llm_logger.log_response(
                request_id=request_id,
                response=response,
                success=True
            )
        except TypeError:
            try:
                response = model_instance.generate_content(
                    contents,
                    generation_config=vertex_config,
                )
                # Log successful retry
                self.llm_logger.log_response(
                    request_id=request_id,
                    response=response,
                    success=True,
                    metadata={"retry": "removed_tools"}
                )
            except Exception as error:
                # Log error
                self.llm_logger.log_error(request_id, error)
                raise
        except Exception as error:
            # Log error
            self.llm_logger.log_error(request_id, error)
            raise

        return response

    def _convert_model_name(self, model: str) -> str:
        """
        Convert Gemini API model names to Vertex AI format.
        
        Vertex AI uses versioned model names:
        - gemini-2.5-flash -> gemini-2.5-flash-002
        - gemini-2.5-pro -> gemini-2.5-pro-002
        - gemini-2.0-flash -> gemini-2.0-flash-001
        - gemini-flash-lite-latest -> gemini-flash-lite-latest (no change)
        """
        model_mappings = {
            "gemini-2.5-flash": "gemini-2.5-flash-002",
            "gemini-2.5-pro": "gemini-2.5-pro-002",
            "gemini-2.0-flash": "gemini-2.0-flash-001",
            "gemini-1.5-flash": "gemini-1.5-flash-002",
            "gemini-1.5-pro": "gemini-1.5-pro-002",
        }

        return model_mappings.get(model, model)


def create_client(api_key: Optional[str] = None) -> UnifiedGeminiClient:
    """
    Create a unified Gemini client (convenience function).
    
    Args:
        api_key: Optional API key for Gemini API
    
    Returns:
        UnifiedGeminiClient instance configured for either API or Vertex AI
    """
    return UnifiedGeminiClient(api_key=api_key)


# Alias for backward compatibility
get_gemini_client = create_client


def get_types_module():
    """
    Get the types module for the active backend.
    
    DEPRECATED: Use client._types_module or self.types instead.
    This function creates a temporary client just to get types, which is inefficient.
    """
    client = create_client()
    return client._types_module
