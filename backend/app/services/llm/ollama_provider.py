"""
Ollama LLM Provider

Implementation of LLMProvider for local models via Ollama.
Supports models like gemma3, deepseek, llama, mistral, etc.
"""

import os
import asyncio
import json
from typing import Any, Dict, List, Optional, Union

import httpx

from .base import (
    LLMProvider,
    LLMResponse,
    LLMConfig,
    ProviderType,
    UsageStats,
    get_ollama_equivalent,
)


class OllamaProvider(LLMProvider):
    """Ollama LLM Provider for local models
    
    Connects to a local or remote Ollama server to run models like:
    - gemma3 (4b, 12b, 27b)
    - deepseek-r1 (1.5b, 7b, 14b, 32b, 70b)
    - llama3.3
    - mistral
    - qwen2.5-coder
    - and more
    """
    
    provider_type = ProviderType.OLLAMA
    
    # Popular models for code generation / instruction following
    RECOMMENDED_MODELS = [
        "gemma3:12b",
        "gemma3:4b",
        "deepseek-r1:14b",
        "deepseek-r1:32b",
        "qwen2.5-coder:14b",
        "llama3.3:70b",
        "mistral:7b",
    ]
    
    DEFAULT_MODEL = "gemma3:12b"
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 300.0,
    ):
        """Initialize Ollama provider
        
        Args:
            base_url: Ollama server URL. Defaults to OLLAMA_HOST env or http://localhost:11434
            timeout: Request timeout in seconds (default 5 minutes for large models)
        """
        self.base_url = base_url or os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.base_url = self.base_url.rstrip("/")
        self.timeout = timeout
        self._available_models: Optional[List[str]] = None
    
    def is_available(self) -> bool:
        """Check if Ollama server is available"""
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.base_url}/api/tags")
                return response.status_code == 200
        except Exception:
            return False
    
    def list_models(self) -> List[str]:
        """List models available on the Ollama server"""
        if self._available_models is not None:
            return self._available_models
        
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(f"{self.base_url}/api/tags")
                if response.status_code == 200:
                    data = response.json()
                    self._available_models = [
                        model["name"] for model in data.get("models", [])
                    ]
                    return self._available_models
        except Exception as e:
            print(f"[OllamaProvider] Failed to list models: {e}")
        
        return self.RECOMMENDED_MODELS
    
    def _resolve_model(self, model: str) -> str:
        """Resolve model name, converting Gemini names to Ollama equivalents if needed"""
        # Check if it's a Gemini model name
        if model.startswith("gemini"):
            ollama_model = get_ollama_equivalent(model)
            print(f"[OllamaProvider] Mapped {model} -> {ollama_model}")
            return ollama_model
        return model
    
    def _build_options(self, config: LLMConfig) -> Dict[str, Any]:
        """Build Ollama-specific options"""
        options = {}
        
        if config.temperature is not None:
            options["temperature"] = config.temperature
        
        if config.max_tokens:
            options["num_predict"] = config.max_tokens
        
        # Add any extra options from config
        options.update(config.extra_options)
        
        return options if options else None
    
    def _parse_response(self, data: Dict[str, Any], model: str) -> LLMResponse:
        """Parse Ollama API response"""
        text = data.get("response", "")
        
        # Extract usage stats if available
        usage = None
        if "prompt_eval_count" in data or "eval_count" in data:
            usage = UsageStats(
                input_tokens=data.get("prompt_eval_count", 0),
                output_tokens=data.get("eval_count", 0),
            )
        
        return LLMResponse(
            text=text.strip(),
            model=model,
            provider=self.provider_type,
            usage=usage,
            raw_response=data,
        )
    
    async def generate(
        self,
        prompt: Union[str, List[Any]],
        config: Optional[LLMConfig] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate response using Ollama API (async)
        
        Args:
            prompt: Text prompt (multimodal not fully supported yet)
            config: LLM configuration
            **kwargs: Additional options
            
        Returns:
            LLMResponse with generated text
        """
        # Build config
        if config is None:
            config = LLMConfig(model=kwargs.get("model", self.DEFAULT_MODEL))
        
        model = self._resolve_model(kwargs.get("model", config.model))
        options = self._build_options(config)
        
        # Build request payload
        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt if isinstance(prompt, str) else str(prompt),
            "stream": False,
        }
        
        if options:
            payload["options"] = options
        
        # Add system instruction if provided
        system = config.system_instruction or kwargs.get("system_instruction")
        if system:
            payload["system"] = system
        
        # Handle JSON format request
        if config.response_schema:
            payload["format"] = "json"
            # Add schema hint to the prompt
            schema_hint = f"\n\nRespond with valid JSON matching this schema: {json.dumps(config.response_schema)}"
            payload["prompt"] += schema_hint
        
        # Make async request
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/api/generate",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        
        return self._parse_response(data, model)
    
    def generate_sync(
        self,
        prompt: Union[str, List[Any]],
        config: Optional[LLMConfig] = None,
        **kwargs
    ) -> LLMResponse:
        """Generate response using Ollama API (sync)
        
        Args:
            prompt: Text prompt
            config: LLM configuration
            **kwargs: Additional options
            
        Returns:
            LLMResponse with generated text
        """
        # Build config
        if config is None:
            config = LLMConfig(model=kwargs.get("model", self.DEFAULT_MODEL))
        
        model = self._resolve_model(kwargs.get("model", config.model))
        options = self._build_options(config)
        
        # Build request payload
        payload: Dict[str, Any] = {
            "model": model,
            "prompt": prompt if isinstance(prompt, str) else str(prompt),
            "stream": False,
        }
        
        if options:
            payload["options"] = options
        
        # Add system instruction if provided
        system = config.system_instruction or kwargs.get("system_instruction")
        if system:
            payload["system"] = system
        
        # Handle JSON format request
        if config.response_schema:
            payload["format"] = "json"
            schema_hint = f"\n\nRespond with valid JSON matching this schema: {json.dumps(config.response_schema)}"
            payload["prompt"] += schema_hint
        
        # Make sync request
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.base_url}/api/generate",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
        
        return self._parse_response(data, model)
    
    async def pull_model(self, model: str) -> bool:
        """Pull a model from Ollama library
        
        Args:
            model: Model name to pull (e.g., "gemma3:12b")
            
        Returns:
            True if successful
        """
        try:
            async with httpx.AsyncClient(timeout=600.0) as client:  # 10 min timeout for downloads
                response = await client.post(
                    f"{self.base_url}/api/pull",
                    json={"name": model, "stream": False},
                )
                return response.status_code == 200
        except Exception as e:
            print(f"[OllamaProvider] Failed to pull model {model}: {e}")
            return False
    
    def check_model_available(self, model: str) -> bool:
        """Check if a specific model is available locally
        
        Args:
            model: Model name to check
            
        Returns:
            True if model is available
        """
        available = self.list_models()
        # Check exact match or base name match (e.g., "gemma3" matches "gemma3:12b")
        return any(
            m == model or m.startswith(f"{model}:") or model.startswith(f"{m.split(':')[0]}:")
            for m in available
        )
