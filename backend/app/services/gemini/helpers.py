"""
Shared Gemini API utilities to reduce code duplication across services.

This module provides helper functions for common Gemini API patterns.
"""

import asyncio
from typing import Optional, Dict, Any, List


async def generate_content_with_text(
    client,
    model: str,
    prompt: str,
    system_instruction: Optional[str] = None,
    temperature: float = 0.7,
    max_output_tokens: Optional[int] = None,
    thinking_config: Optional[Dict[str, Any]] = None,
    types_module = None,
    cost_tracker = None,
) -> Optional[str]:
    """Generate content from a text prompt.
    
    Args:
        client: Gemini client instance
        model: Model name to use
        prompt: The text prompt
        system_instruction: Optional system instruction
        temperature: Temperature for generation
        max_output_tokens: Max tokens in response
        thinking_config: Optional thinking config dict with 'thinking_level' key
        types_module: The types module from gemini_client (for Content, Part, GenerateContentConfig)
        cost_tracker: Optional cost tracker for tracking usage
        
    Returns:
        Generated text or None if generation fails
    """
    if types_module is None:
        from .client import get_types_module
        types_module = get_types_module()

    # Build config
    config_kwargs = {
        "temperature": temperature,
    }

    if system_instruction:
        config_kwargs["system_instruction"] = system_instruction

    if max_output_tokens:
        config_kwargs["max_output_tokens"] = max_output_tokens

    if thinking_config:
        config_kwargs["thinking_config"] = types_module.ThinkingConfig(
            thinking_level=thinking_config.get("thinking_level", "LOW")
        )

    config = types_module.GenerateContentConfig(**config_kwargs)

    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=model,
            contents=[
                types_module.Content(
                    role="user",
                    parts=[types_module.Part.from_text(text=prompt)]
                )
            ],
            config=config
        )

        if cost_tracker:
            try:
                cost_tracker.track_usage(response, model)
            except Exception:
                pass

        if not response or not response.text:
            return None

        return response.text

    except asyncio.TimeoutError:
        return None
    except Exception:
        return None


async def generate_content_with_images(
    client,
    model: str,
    prompt: str,
    image_bytes_list: List[bytes],
    system_instruction: Optional[str] = None,
    temperature: float = 0.7,
    max_output_tokens: Optional[int] = None,
    types_module = None,
    cost_tracker = None,
) -> Optional[str]:
    """Generate content from a prompt and images.
    
    Args:
        client: Gemini client instance
        model: Model name to use
        prompt: The text prompt
        image_bytes_list: List of image bytes (PNG/JPEG)
        system_instruction: Optional system instruction
        temperature: Temperature for generation
        max_output_tokens: Max tokens in response
        types_module: The types module from gemini_client
        cost_tracker: Optional cost tracker for tracking usage
        
    Returns:
        Generated text or None if generation fails
    """
    if types_module is None:
        from .client import get_types_module
        types_module = get_types_module()

    parts = []

    # Add images
    for image_bytes in image_bytes_list[:5]:  # Limit to 5 images
        try:
            parts.append(types_module.Part.from_bytes(data=image_bytes, mime_type="image/png"))
        except Exception:
            pass

    # Add text prompt
    parts.append(types_module.Part.from_text(text=prompt))

    # Build config
    config_kwargs = {
        "temperature": temperature,
    }

    if system_instruction:
        config_kwargs["system_instruction"] = system_instruction

    if max_output_tokens:
        config_kwargs["max_output_tokens"] = max_output_tokens

    config = types_module.GenerateContentConfig(**config_kwargs)

    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=model,
            contents=[
                types_module.Content(role="user", parts=parts)
            ],
            config=config
        )

        if cost_tracker:
            try:
                cost_tracker.track_usage(response, model)
            except Exception:
                pass

        if not response or not response.text:
            return None

        return response.text

    except asyncio.TimeoutError:
        return None
    except Exception:
        return None


async def generate_structured_output(
    client,
    model: str,
    prompt: str,
    response_schema: Dict[str, Any],
    system_instruction: Optional[str] = None,
    temperature: float = 0.7,
    types_module = None,
    cost_tracker = None,
) -> Optional[str]:
    """Generate structured JSON output using response schema.
    
    Args:
        client: Gemini client instance
        model: Model name to use
        prompt: The text prompt
        response_schema: JSON schema for structured output
        system_instruction: Optional system instruction
        temperature: Temperature for generation
        types_module: The types module from gemini_client
        cost_tracker: Optional cost tracker for tracking usage
        
    Returns:
        Generated JSON text or None if generation fails
    """
    if types_module is None:
        from .client import get_types_module
        types_module = get_types_module()

    config = types_module.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=response_schema,
        system_instruction=system_instruction,
        temperature=temperature,
    )

    try:
        response = await asyncio.to_thread(
            client.models.generate_content,
            model=model,
            contents=[
                types_module.Content(
                    role="user",
                    parts=[types_module.Part.from_text(text=prompt)]
                )
            ],
            config=config
        )

        if cost_tracker:
            try:
                cost_tracker.track_usage(response, model)
            except Exception:
                pass

        if not response or not response.text:
            return None

        return response.text

    except asyncio.TimeoutError:
        return None
    except Exception:
        return None
