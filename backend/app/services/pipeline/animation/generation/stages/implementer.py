"""
Implementer Stage

Responsible for converting choreography plan into Manim code.

Single Responsibility: Generate implementation code from plan
"""

import json
from typing import Dict, Any, Optional

from app.core import get_logger
from app.services.infrastructure.llm import PromptingEngine, PromptConfig

from ...config import BASE_GENERATION_TEMPERATURE, IMPLEMENTATION_MAX_OUTPUT_TOKENS
from ...prompts import IMPLEMENTER_SYSTEM, FULL_IMPLEMENTATION_USER
from ..core import clean_code, ImplementationError
from ..formatters import CodeFormatter


logger = get_logger(__name__, component="animation_implementer")


class Implementer:
    """Generates Manim implementation from choreography plan."""
    
    def __init__(self, engine: PromptingEngine):
        """Initialize implementer with engine.
        
        Args:
            engine: Prompting engine for code generation
        """
        self.engine = engine
        self.formatter = CodeFormatter()
    
    async def implement(
        self,
        section: Dict[str, Any],
        plan: str,
        duration: float,
        context: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None
    ) -> str:
        """Generate Manim code implementation.
        
        Args:
            section: Section dictionary
            plan: Choreography plan text
            duration: Target animation duration
            context: Optional context
            temperature: Optional temperature override for retries
            
        Returns:
            Clean Manim code string
            
        Raises:
            ImplementationError: If code generation fails
        """
        # Get language from section (defaults to English)
        language = section.get("language", "en")
        language_name = self._get_language_name(language)
        
        prompt = FULL_IMPLEMENTATION_USER.format(
            plan=plan,
            segment_timings=self.formatter.summarize_segments(section),
            total_duration=duration,
            section_id_title=self.formatter.derive_class_name(section),
            theme_info=section.get("style", "3b1b"),
            section_data=json.dumps({
                "key_concepts": section.get("key_concepts", []),
                "supporting_data": section.get("supporting_data", []),
            }),
            patterns=self._get_patterns(),
            language_name=language_name
        )
        
        config = PromptConfig(
            enable_thinking=True,
            timeout=300.0,
            temperature=temperature or BASE_GENERATION_TEMPERATURE,
            max_output_tokens=IMPLEMENTATION_MAX_OUTPUT_TOKENS
        )
        
        result = await self.engine.generate(
            prompt=prompt,
            system_prompt=IMPLEMENTER_SYSTEM.template,
            config=config,
            context=dict(context or {}, stage="implementation")
        )
        
        if not result.get("success") or not result.get("response"):
            error_msg = result.get("error", "Unknown error")
            logger.error(f"Implementation failed: {error_msg}")
            raise ImplementationError(f"Code generation failed: {error_msg}")
        
        code = clean_code(result["response"])
        logger.info(f"Generated implementation ({len(code)} chars)")
        
        return code

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

    @staticmethod
    def _get_patterns() -> str:
        """Get Manim patterns for the prompt."""
        from ...prompts import get_compact_patterns
        return get_compact_patterns()
