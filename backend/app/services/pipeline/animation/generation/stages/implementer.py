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
from ..constants import DEFAULT_THEME, DEFAULT_LANGUAGE
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
        plan: Any,
        duration: float,
        context: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None
    ) -> str:
        """Generate Manim code implementation.
        
        Args:
            section: Section dictionary
            plan: Choreography plan (v2 dict, legacy dict, or JSON/text string)
            duration: Target animation duration
            context: Optional context
            temperature: Optional temperature override for retries
            
        Returns:
            Clean Manim code string
            
        Raises:
            ImplementationError: If code generation fails
        """
        # Extract section data flexibly from multiple possible keys
        section_data = (
            section.get("section_data")
            or section.get("visual_data")
            or section.get("metadata")
        )
        
        language_name = CodeFormatter.get_language_name(
            section.get("language", DEFAULT_LANGUAGE)
        )
        prompt = FULL_IMPLEMENTATION_USER.format(
            plan=self._format_plan_for_prompt(plan, language_name),
            segment_timings=self.formatter.summarize_segments(section),
            total_duration=duration,
            section_id_title=self.formatter.derive_class_name(section),
            theme_info=section.get("theme_info") or section.get("style", DEFAULT_THEME),
            section_data=self.formatter.serialize_for_prompt(section_data),
            patterns=self._get_patterns(),
            language_name=language_name,
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
    def _format_plan_for_prompt(plan: Any, language_name: str) -> str:
        """Serialize incoming choreography payload into canonical v2 JSON text."""
        if isinstance(plan, str):
            try:
                parsed = json.loads(plan)
            except (TypeError, ValueError):
                return plan
            return CodeFormatter.serialize_choreography_plan(parsed, language_name=language_name)
        if isinstance(plan, dict):
            return CodeFormatter.serialize_choreography_plan(plan, language_name=language_name)
        return CodeFormatter.serialize_choreography_plan({}, language_name=language_name)

    @staticmethod
    def _get_patterns() -> str:
        """Get Manim patterns for the prompt."""
        from ...prompts import get_compact_patterns
        return get_compact_patterns()
