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
        
        if self.use_vertex_ai:
            self._init_vertex_ai()
        else:
            self._init_gemini_api(api_key)
    
    def _init_gemini_api(self, api_key: Optional[str] = None):
        """Initialize Gemini API backend"""
        try:
            from google import genai
            from google.genai import types
            
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
            from vertexai.generative_models import GenerativeModel
            
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
        
        class VertexTypesWrapper:
            """Wrapper to make Vertex AI types compatible with Gemini API code"""
            # Assign the imported classes
            pass
        
        # Set class attributes dynamically
        VertexTypesWrapper.Part = Part
        VertexTypesWrapper.Content = Content
        
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
    
    def generate_content(
        self,
        model: str,
        contents: Union[str, List[Any]],
        config: Optional[GenerationConfig] = None
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
        if config.thinking_config:
            gen_config_dict["thinking_config"] = config.thinking_config
        
        # Add response format if specified
        if config.response_mime_type:
            gen_config_dict["response_mime_type"] = config.response_mime_type
        
        if config.response_schema:
            gen_config_dict["response_schema"] = config.response_schema
        
        gen_config = types.GenerateContentConfig(**gen_config_dict)
        
        # Make the API call
        response = self.client.models.generate_content(
            model=model,
            contents=contents,
            config=gen_config
        )
        
        return response


class VertexAIModels:
    """Vertex AI models interface (wraps vertexai)"""
    
    def __init__(self, vertexai_module, location: str):
        self.vertexai = vertexai_module
        self.location = location
    
    def generate_content(
        self,
        model: str,
        contents: Union[str, List[Any]],
        config: Optional[GenerationConfig] = None
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
            GenerationConfig as VertexGenerationConfig,
            Content,
            Part
        )
        
        config = config or GenerationConfig()
        
        # Convert model name to Vertex AI format if needed
        model = self._convert_model_name(model)
        
        # Create model instance
        model_instance = GenerativeModel(model)
        
        # Build generation config
        gen_config_dict = {
            "temperature": config.temperature,
            "top_p": config.top_p,
            "top_k": config.top_k,
            "max_output_tokens": config.max_output_tokens,
        }
        
        vertex_config = VertexGenerationConfig(**gen_config_dict)
        
        # Convert contents to Vertex AI format if needed
        if isinstance(contents, str):
            contents = [contents]
        
        # Make the API call
        response = model_instance.generate_content(
            contents,
            generation_config=vertex_config,
        )
        
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
