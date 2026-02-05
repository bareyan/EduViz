"""
Choreographer Stage

Responsible for high-level visual planning using reasoning model.

Single Responsibility: Generate conceptual choreography plan
"""

import json
from typing import Dict, Any, Optional

from app.core import get_logger
from app.services.infrastructure.llm import PromptingEngine, PromptConfig

from ...config import BASE_GENERATION_TEMPERATURE, CHOREOGRAPHY_MAX_OUTPUT_TOKENS
from ...prompts import (
    CHOREOGRAPHER_SYSTEM,
    CHOREOGRAPHY_USER,
    CHOREOGRAPHY_SCHEMA
)
from ..core import ChoreographyError


logger = get_logger(__name__, component="animation_choreographer")


class Choreographer:
    """Generates high-level visual plans using reasoning model."""
    
    def __init__(self, engine: PromptingEngine):
        """Initialize choreographer with dedicated engine.
        
        Args:
            engine: Prompting engine configured for choreography model
        """
        self.engine = engine
    
    async def plan(
        self,
        section: Dict[str, Any],
        duration: float,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate conceptual visual plan.
        
        Args:
            section: Section dictionary with title, narration, and segments
            duration: Target animation duration in seconds
            context: Optional context for logging and retries
            
        Returns:
            Visual choreography plan as text
            
        Raises:
            ChoreographyError: If planning fails
        """
        # Get language from section (defaults to English)
        language = section.get("language", "en")
        language_name = self._get_language_name(language)
        
        prompt = CHOREOGRAPHY_USER.format(
            title=section.get("title", "Untitled"),
            narration=section.get("narration", ""),
            timing_info=json.dumps(section.get("narration_segments", []), indent=2),
            target_duration=duration,
            theme_info=section.get("style", "3b1b"),
            visual_hints=section.get("visual_description", ""),
            section_data=json.dumps({
                "key_concepts": section.get("key_concepts", []),
                "animation_type": section.get("animation_type", "mixed"),
                "supporting_data": section.get("supporting_data", []),
            }),
            language_name=language_name
        )
        
        result = await self.engine.generate(
            prompt=prompt,
            system_prompt=CHOREOGRAPHER_SYSTEM.template,
            config=PromptConfig(
                enable_thinking=True,
                timeout=300.0,
                temperature=BASE_GENERATION_TEMPERATURE,
                response_schema=CHOREOGRAPHY_SCHEMA,
                max_output_tokens=CHOREOGRAPHY_MAX_OUTPUT_TOKENS
            ),
            context=dict(context or {}, stage="choreography")
        )
        
        if not result.get("success") or not result.get("response"):
            error_msg = result.get("error", "Unknown error")
            logger.error(f"Choreography failed: {error_msg}")
            raise ChoreographyError(f"Planning failed: {error_msg}")
        
        plan = result["response"]
        logger.info(f"Generated choreography plan ({len(plan)} chars)")
        
        return plan

    @staticmethod
    def _get_language_name(language_code: str) -> str:
        """Get language name from code."""
        LANGUAGE_NAMES = {
            "en": "English",
            "fr": "French",
            "es": "Spanish",
            "de": "German",
            "it": "Italian",
            "pt": "Portuguese",
            "zh": "Chinese",
            "ja": "Japanese",
            "ko": "Korean",
            "ar": "Arabic",
            "ru": "Russian",
            "ua": "Ukrainian",
            "hy": "Armenian",
        }
        return LANGUAGE_NAMES.get(language_code, "English")
