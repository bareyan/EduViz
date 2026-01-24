"""
LLM Provider Factory

Creates and manages LLM provider instances based on configuration.
"""

import os
from typing import Dict, Optional

from .base import LLMProvider, ProviderType
from .gemini_provider import GeminiProvider
from .ollama_provider import OllamaProvider


# Cache for provider instances
_provider_cache: Dict[ProviderType, LLMProvider] = {}


def get_default_provider_type() -> ProviderType:
    """Get the default provider type from environment or config
    
    Checks LLM_PROVIDER env var first, then falls back to Gemini if API key exists,
    otherwise tries Ollama.
    
    Returns:
        ProviderType to use
    """
    # Check explicit provider setting
    provider_env = os.getenv("LLM_PROVIDER", "").lower()
    
    if provider_env == "ollama":
        return ProviderType.OLLAMA
    elif provider_env == "gemini":
        return ProviderType.GEMINI
    
    # Auto-detect based on available configuration
    if os.getenv("GEMINI_API_KEY"):
        return ProviderType.GEMINI
    
    # Fall back to Ollama (local)
    return ProviderType.OLLAMA


def get_llm_provider(
    provider_type: Optional[ProviderType] = None,
    use_cache: bool = True,
    **kwargs
) -> LLMProvider:
    """Get an LLM provider instance
    
    Args:
        provider_type: Specific provider to use. If None, uses default.
        use_cache: Whether to cache and reuse provider instances
        **kwargs: Provider-specific initialization options
        
    Returns:
        LLMProvider instance
        
    Raises:
        ValueError: If provider is not available
    """
    if provider_type is None:
        provider_type = get_default_provider_type()
    
    # Check cache first
    if use_cache and provider_type in _provider_cache:
        return _provider_cache[provider_type]
    
    # Create provider
    provider: LLMProvider
    
    if provider_type == ProviderType.GEMINI:
        provider = GeminiProvider(
            api_key=kwargs.get("api_key"),
        )
        if not provider.is_available():
            raise ValueError(
                "Gemini provider is not available. "
                "Set GEMINI_API_KEY environment variable or use LLM_PROVIDER=ollama"
            )
    
    elif provider_type == ProviderType.OLLAMA:
        provider = OllamaProvider(
            base_url=kwargs.get("base_url"),
            timeout=kwargs.get("timeout", 300.0),
        )
        if not provider.is_available():
            raise ValueError(
                "Ollama provider is not available. "
                "Make sure Ollama is running (ollama serve) or set LLM_PROVIDER=gemini"
            )
    
    else:
        raise ValueError(f"Unknown provider type: {provider_type}")
    
    # Cache if requested
    if use_cache:
        _provider_cache[provider_type] = provider
    
    return provider


def clear_provider_cache():
    """Clear the provider cache"""
    _provider_cache.clear()


def get_all_providers() -> Dict[str, bool]:
    """Get availability status of all providers
    
    Returns:
        Dict mapping provider name to availability status
    """
    results = {}
    
    # Check Gemini
    try:
        gemini = GeminiProvider()
        results["gemini"] = gemini.is_available()
    except Exception:
        results["gemini"] = False
    
    # Check Ollama
    try:
        ollama = OllamaProvider()
        results["ollama"] = ollama.is_available()
    except Exception:
        results["ollama"] = False
    
    return results
