"""
LLM Service - Abstraction layer for Language Model providers

This module provides a unified interface for interacting with different LLM providers:
- Gemini (Google's AI models)
- Ollama (local models like gemma3, deepseek, etc.)

Usage:
    from app.services.llm import get_llm_provider, LLMResponse
    
    # Get the configured provider
    llm = get_llm_provider()
    
    # Generate content
    response = await llm.generate("Your prompt here", model="gemma3")
    print(response.text)
"""

from .base import (
    LLMProvider,
    LLMResponse,
    LLMConfig,
    ProviderType,
)
from .factory import get_llm_provider, get_default_provider_type
from .gemini_provider import GeminiProvider
from .ollama_provider import OllamaProvider

__all__ = [
    # Base classes
    "LLMProvider",
    "LLMResponse", 
    "LLMConfig",
    "ProviderType",
    # Providers
    "GeminiProvider",
    "OllamaProvider",
    # Factory
    "get_llm_provider",
    "get_default_provider_type",
]
