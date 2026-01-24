"""
Base classes for LLM providers

Defines the abstract interface that all LLM providers must implement.
"""

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union


class ProviderType(str, Enum):
    """Supported LLM providers"""
    GEMINI = "gemini"
    OLLAMA = "ollama"


@dataclass
class LLMConfig:
    """Configuration for an LLM request"""
    model: str
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    thinking_level: Optional[str] = None  # For Gemini models that support thinking
    response_schema: Optional[Dict[str, Any]] = None  # For structured output
    system_instruction: Optional[str] = None
    
    # Provider-specific options
    extra_options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UsageStats:
    """Token usage statistics"""
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    
    def __post_init__(self):
        if self.total_tokens == 0:
            self.total_tokens = self.input_tokens + self.output_tokens


@dataclass
class LLMResponse:
    """Unified response from any LLM provider"""
    text: str
    model: str
    provider: ProviderType
    usage: Optional[UsageStats] = None
    raw_response: Any = None  # Original response object from the provider
    
    @property
    def usage_metadata(self):
        """Compatibility property for existing cost tracker"""
        if self.usage:
            # Create a simple object that mimics Gemini's usage_metadata
            class UsageMetadata:
                def __init__(self, usage: UsageStats):
                    self.prompt_token_count = usage.input_tokens
                    self.candidates_token_count = usage.output_tokens
            return UsageMetadata(self.usage)
        return None


class LLMProvider(ABC):
    """Abstract base class for LLM providers
    
    All LLM providers must implement this interface to ensure
    consistent behavior across different backends.
    """
    
    provider_type: ProviderType
    
    @abstractmethod
    async def generate(
        self,
        prompt: Union[str, List[Any]],
        config: Optional[LLMConfig] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate a response from the LLM
        
        Args:
            prompt: The prompt text or list of content parts (for multimodal)
            config: LLM configuration options
            **kwargs: Additional provider-specific options
            
        Returns:
            LLMResponse with the generated text and metadata
        """
        pass
    
    @abstractmethod
    def generate_sync(
        self,
        prompt: Union[str, List[Any]],
        config: Optional[LLMConfig] = None,
        **kwargs
    ) -> LLMResponse:
        """Synchronous version of generate
        
        Args:
            prompt: The prompt text or list of content parts
            config: LLM configuration options
            **kwargs: Additional provider-specific options
            
        Returns:
            LLMResponse with the generated text and metadata
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is available and properly configured
        
        Returns:
            True if the provider can be used
        """
        pass
    
    @abstractmethod
    def list_models(self) -> List[str]:
        """List available models for this provider
        
        Returns:
            List of model names
        """
        pass
    
    def get_default_model(self) -> str:
        """Get the default model for this provider
        
        Returns:
            Default model name
        """
        models = self.list_models()
        return models[0] if models else ""
    
    @property
    def name(self) -> str:
        """Get the provider name"""
        return self.provider_type.value


# Model name mappings for cross-provider compatibility
# Maps generic/Gemini model names to Ollama equivalents
MODEL_MAPPINGS = {
    # Fast/lite models -> smaller local models
    "gemini-flash-lite-latest": "gemma3:4b",
    "gemini-2.0-flash-lite": "gemma3:4b",
    
    # Flash models -> medium local models
    "gemini-2.5-flash": "gemma3:12b",
    "gemini-3-flash-preview": "deepseek-r1:14b",
    
    # Pro models -> larger local models
    "gemini-2.5-pro": "deepseek-r1:32b",
    "gemini-3-pro-preview": "deepseek-r1:32b",
}


def get_ollama_equivalent(gemini_model: str) -> str:
    """Get the Ollama model equivalent for a Gemini model name
    
    Args:
        gemini_model: Gemini model name
        
    Returns:
        Equivalent Ollama model name
    """
    return MODEL_MAPPINGS.get(gemini_model, "gemma3:12b")
