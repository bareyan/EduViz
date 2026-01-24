"""
Gemini LLM Provider

Implementation of LLMProvider for Google's Gemini AI models.
"""

import os
import asyncio
from typing import Any, Dict, List, Optional, Union

from .base import (
    LLMProvider,
    LLMResponse,
    LLMConfig,
    ProviderType,
    UsageStats,
)

# Gemini SDK
try:
    from google import genai
    from google.genai import types
    GEMINI_AVAILABLE = True
except ImportError:
    genai = None
    types = None
    GEMINI_AVAILABLE = False


class GeminiProvider(LLMProvider):
    """Google Gemini LLM Provider
    
    Supports all Gemini models including those with thinking capabilities.
    """
    
    provider_type = ProviderType.GEMINI
    
    # Models that support thinking configuration
    THINKING_CAPABLE_MODELS = [
        "gemini-3-flash-preview",
        "gemini-3-pro-preview",
    ]
    
    # Available Gemini models
    AVAILABLE_MODELS = [
        "gemini-3-flash-preview",
        "gemini-3-pro-preview",
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-flash-lite-latest",
        "gemini-2.0-flash",
    ]
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize Gemini provider
        
        Args:
            api_key: Gemini API key. If not provided, uses GEMINI_API_KEY env var
        """
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.client = None
        
        if GEMINI_AVAILABLE and self.api_key:
            self.client = genai.Client(api_key=self.api_key)
    
    def is_available(self) -> bool:
        """Check if Gemini is available"""
        return GEMINI_AVAILABLE and self.client is not None
    
    def list_models(self) -> List[str]:
        """List available Gemini models"""
        return self.AVAILABLE_MODELS.copy()
    
    def _supports_thinking(self, model: str) -> bool:
        """Check if model supports thinking configuration"""
        return model in self.THINKING_CAPABLE_MODELS
    
    def _build_generation_config(self, config: LLMConfig) -> Any:
        """Build Gemini-specific generation config"""
        if not types:
            return None
            
        kwargs = {}
        
        # Add temperature if specified
        if config.temperature is not None:
            kwargs["temperature"] = config.temperature
        
        # Add max tokens if specified
        if config.max_tokens:
            kwargs["max_output_tokens"] = config.max_tokens
        
        # Add thinking config for capable models
        if config.thinking_level and self._supports_thinking(config.model):
            kwargs["thinking_config"] = types.ThinkingConfig(
                thinking_level=config.thinking_level,
            )
        
        # Add response schema for structured output
        if config.response_schema:
            kwargs["response_mime_type"] = "application/json"
            kwargs["response_schema"] = config.response_schema
        
        if kwargs:
            return types.GenerateContentConfig(**kwargs)
        return None
    
    def _extract_usage(self, response: Any) -> Optional[UsageStats]:
        """Extract usage stats from Gemini response"""
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            usage = response.usage_metadata
            input_tokens = getattr(usage, 'prompt_token_count', 0) or 0
            output_tokens = getattr(usage, 'candidates_token_count', 0) or 0
            return UsageStats(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        return None
    
    async def generate(
        self,
        prompt: Union[str, List[Any]],
        config: Optional[LLMConfig] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate response using Gemini API (async)
        
        Args:
            prompt: Text prompt or list of content parts
            config: LLM configuration
            **kwargs: Additional options (model override, etc.)
            
        Returns:
            LLMResponse with generated text
        """
        if not self.is_available():
            raise RuntimeError("Gemini provider is not available. Check API key.")
        
        # Build config
        if config is None:
            config = LLMConfig(model=kwargs.get("model", "gemini-2.5-flash"))
        
        model = kwargs.get("model", config.model)
        generation_config = self._build_generation_config(config)
        
        # Handle system instruction
        system_instruction = config.system_instruction or kwargs.get("system_instruction")
        
        # Build request kwargs
        request_kwargs = {
            "model": model,
            "contents": prompt,
        }
        
        if generation_config:
            request_kwargs["config"] = generation_config
            
        if system_instruction and types:
            # For Gemini, system instruction is part of the config
            if "config" not in request_kwargs:
                request_kwargs["config"] = types.GenerateContentConfig()
            # Note: System instruction handling depends on Gemini SDK version
        
        # Make async call
        response = await asyncio.to_thread(
            self.client.models.generate_content,
            **request_kwargs
        )
        
        return LLMResponse(
            text=response.text.strip() if response.text else "",
            model=model,
            provider=self.provider_type,
            usage=self._extract_usage(response),
            raw_response=response,
        )
    
    def generate_sync(
        self,
        prompt: Union[str, List[Any]],
        config: Optional[LLMConfig] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate response using Gemini API (sync)
        
        Args:
            prompt: Text prompt or list of content parts
            config: LLM configuration
            **kwargs: Additional options
            
        Returns:
            LLMResponse with generated text
        """
        if not self.is_available():
            raise RuntimeError("Gemini provider is not available. Check API key.")
        
        # Build config
        if config is None:
            config = LLMConfig(model=kwargs.get("model", "gemini-2.5-flash"))
        
        model = kwargs.get("model", config.model)
        generation_config = self._build_generation_config(config)
        
        # Build request kwargs
        request_kwargs = {
            "model": model,
            "contents": prompt,
        }
        
        if generation_config:
            request_kwargs["config"] = generation_config
        
        # Make sync call
        response = self.client.models.generate_content(**request_kwargs)
        
        return LLMResponse(
            text=response.text.strip() if response.text else "",
            model=model,
            provider=self.provider_type,
            usage=self._extract_usage(response),
            raw_response=response,
        )
