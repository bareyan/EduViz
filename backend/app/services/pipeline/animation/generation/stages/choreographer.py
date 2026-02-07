"""
Choreographer Stage

Responsible for high-level visual planning using reasoning model.

Single Responsibility: Generate conceptual choreography plan
"""

import json
from typing import Dict, Any, Optional, Tuple

from app.core import get_logger
from app.services.infrastructure.llm import PromptingEngine, PromptConfig

from ...config import (
    BASE_GENERATION_TEMPERATURE,
    CHOREOGRAPHY_MAX_OUTPUT_TOKENS,
    MAX_JSON_RETRIES,
)
from ..constants import DEFAULT_THEME, DEFAULT_VISUAL_HINTS, DEFAULT_SECTION_TITLE, DEFAULT_LANGUAGE
from ...prompts import (
    CHOREOGRAPHER_SYSTEM,
    CHOREOGRAPHY_USER,
    CHOREOGRAPHY_COMPACT_USER,
    CHOREOGRAPHY_SCHEMA,
)
from ..core import ChoreographyError
from ..formatters import CodeFormatter


logger = get_logger(__name__, component="animation_choreographer")


class Choreographer:
    """Generates high-level visual plans using reasoning model."""
    
    def __init__(self, engine: PromptingEngine):
        """Initialize choreographer with dedicated engine.
        
        Args:
            engine: Prompting engine configured for choreography model
        """
        self.engine = engine
        self._schema_compatibility: Optional[bool] = None
    
    async def plan(
        self,
        section: Dict[str, Any],
        duration: float,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Generate conceptual visual plan.
        
        Args:
            section: Section dictionary with title, narration, and segments
            duration: Target animation duration in seconds
            context: Optional context for logging and retries
            
        Returns:
            Visual choreography plan as normalized v2 dictionary
            
        Raises:
            ChoreographyError: If planning fails
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
        prompt = CHOREOGRAPHY_USER.format(
            title=section.get("title", DEFAULT_SECTION_TITLE),
            narration=section.get("narration", ""),
            timing_info=json.dumps(section.get("narration_segments", []), indent=2),
            target_duration=duration,
            theme_info=section.get("theme_info") or section.get("style", DEFAULT_THEME),
            visual_hints=CodeFormatter.serialize_for_prompt(
                section.get("visual_hints") or section.get("visual_description"),
                default=DEFAULT_VISUAL_HINTS,
            ),
            section_data=CodeFormatter.serialize_for_prompt(section_data),
            language_name=language_name,
        )

        call_context = dict(context or {}, stage="choreography")
        use_schema = self._should_use_schema()
        result = await self._generate_plan(
            prompt=prompt,
            context=call_context,
            with_schema=use_schema,
        )

        plan, error_msg = self._extract_plan_from_result(result, language_name)
        if plan is not None:
            if use_schema:
                self._schema_compatibility = True
            logger.info(
                "Generated choreography plan v2",
                extra={
                    "object_count": len(plan.get("objects", [])),
                    "timeline_segments": len(plan.get("timeline", [])),
                },
            )
            return plan

        # Provider compatibility fallback for schema support failures.
        if use_schema and self._is_schema_incompatibility_error(error_msg):
            self._schema_compatibility = False
            logger.warning(
                "Schema-based choreography rejected by provider, retrying without schema",
                extra={"error": error_msg},
            )
            result = await self._generate_plan(
                prompt=prompt,
                context={**call_context, "schema_fallback": True},
                with_schema=False,
            )
            plan, error_msg = self._extract_plan_from_result(result, language_name)
            if plan is not None:
                return plan

        # Compact fallback if full prompt is still invalid or truncated.
        compact_prompt = CHOREOGRAPHY_COMPACT_USER.format(
            title=section.get("title", DEFAULT_SECTION_TITLE),
            narration=section.get("narration", ""),
            timing_info=json.dumps(section.get("narration_segments", []), indent=2),
            target_duration=duration,
            theme_info=section.get("theme_info") or section.get("style", DEFAULT_THEME),
            visual_hints=CodeFormatter.serialize_for_prompt(
                section.get("visual_hints") or section.get("visual_description"),
                default=DEFAULT_VISUAL_HINTS,
            ),
            language_name=language_name,
        )
        result = await self._generate_plan(
            prompt=compact_prompt,
            context={**call_context, "compact_fallback": True},
            with_schema=False,
        )
        plan, compact_error = self._extract_plan_from_result(result, language_name)
        if plan is not None:
            return plan

        final_error = compact_error or error_msg or "Unknown error"
        logger.error(f"Choreography failed: {final_error}")
        raise ChoreographyError(f"Planning failed: {final_error}")

    async def _generate_plan(
        self,
        prompt: str,
        context: Dict[str, Any],
        with_schema: bool,
    ) -> Dict[str, Any]:
        return await self.engine.generate(
            prompt=prompt,
            system_prompt=CHOREOGRAPHER_SYSTEM.template,
            config=PromptConfig(
                enable_thinking=True,
                timeout=300.0,
                temperature=BASE_GENERATION_TEMPERATURE,
                response_format="json",
                response_schema=CHOREOGRAPHY_SCHEMA if with_schema else None,
                require_json_valid=True,
                max_output_tokens=CHOREOGRAPHY_MAX_OUTPUT_TOKENS,
                max_retries=1 if with_schema else MAX_JSON_RETRIES,
            ),
            context=context,
        )

    @staticmethod
    def _extract_plan_from_result(
        result: Dict[str, Any],
        language_name: str,
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        if not result.get("success"):
            return None, result.get("error", "Unknown error")

        parsed = result.get("parsed_json")
        if not isinstance(parsed, dict):
            return None, result.get("json_error", "invalid_json")

        plan = CodeFormatter.normalize_choreography_plan(
            parsed,
            language_name=language_name,
        )
        return plan, None

    def _should_use_schema(self) -> bool:
        if self._schema_compatibility is False:
            return False

        model_name = self._resolve_model_name()
        if model_name and self._is_likely_schema_incompatible_model(model_name):
            self._schema_compatibility = False
            logger.info(
                "Disabling choreography response schema for likely incompatible model",
                extra={"model_name": model_name},
            )
            return False

        return True

    def _resolve_model_name(self) -> Optional[str]:
        getter = getattr(self.engine, "_get_config", None)
        if not callable(getter):
            return None
        try:
            config = getter()
        except Exception:
            return None

        model_name = getattr(config, "model_name", None)
        return model_name if isinstance(model_name, str) and model_name.strip() else None

    @staticmethod
    def _is_likely_schema_incompatible_model(model_name: str) -> bool:
        lowered = model_name.lower()
        return lowered.startswith("gemini-3-") and "preview" in lowered

    @staticmethod
    def _is_schema_incompatibility_error(error_msg: Optional[str]) -> bool:
        if not error_msg:
            return False
        lowered = error_msg.lower()
        if "validation errors for schema" in lowered:
            return True
        if "pydantic" in lowered and "schema" in lowered:
            return True
        if "additional_properties" in lowered:
            return True
        if "invalid json payload" in lowered and "response_schema" in lowered:
            return True
        return (
            "invalid_argument" in lowered
            and ("schema" in lowered or "response_schema" in lowered)
        )
