"""
Choreographer Stage

Responsible for high-level visual planning using reasoning model.

Single Responsibility: Generate conceptual choreography plan
"""

import json
from typing import Dict, Any, Optional

from app.core import get_logger
from app.services.infrastructure.llm import PromptingEngine, PromptConfig

from ...config import (
    BASE_GENERATION_TEMPERATURE,
    get_choreography_max_output_tokens,
    OVERVIEW_CHOREOGRAPHY_TIMEOUT,
)
from ..constants import DEFAULT_THEME, DEFAULT_VISUAL_HINTS, DEFAULT_SECTION_TITLE, DEFAULT_LANGUAGE
from ...prompts import (
    CHOREOGRAPHER_SYSTEM,
    CHOREOGRAPHY_USER,
    CHOREOGRAPHY_SCHEMA
)
from ..core import ChoreographyError
from ..core.visual_strategy import build_visual_strategy
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
        # Extract section data flexibly from multiple possible keys
        section_data = (
            section.get("section_data")
            or section.get("visual_data")
            or section.get("metadata")
        )
        if not isinstance(section_data, dict):
            section_data = {}
        if isinstance(section.get("supporting_data"), list):
            section_data.setdefault("supporting_data", section.get("supporting_data"))
        if section.get("source_pages") is not None:
            section_data.setdefault("source_pages", section.get("source_pages"))
        if section.get("source_pdf_path"):
            section_data.setdefault("source_pdf_path", section.get("source_pdf_path"))
        
        prompt = CHOREOGRAPHY_USER.format(
            title=section.get("title", DEFAULT_SECTION_TITLE),
            narration=section.get("narration", ""),
            timing_info=json.dumps(section.get("narration_segments", []), indent=2),
            target_duration=duration,
            theme_info=section.get("theme_info") or section.get("style", DEFAULT_THEME),
            visual_strategy=build_visual_strategy(
                content_focus=str(section.get("content_focus", "as_document")),
                video_mode=str(section.get("video_mode", "comprehensive")),
                document_context=str(section.get("document_context", "auto")),
                section=section,
            ),
            visual_hints=CodeFormatter.serialize_for_prompt(
                section.get("visual_hints") or section.get("visual_description"),
                default=DEFAULT_VISUAL_HINTS,
            ),
            section_data=CodeFormatter.serialize_for_prompt(section_data),
            language_name=CodeFormatter.get_language_name(section.get("language", DEFAULT_LANGUAGE))
        )
        
        is_overview = str(section.get("video_mode", "comprehensive")).strip().lower() == "overview"

        result = await self.engine.generate(
            prompt=prompt,
            system_prompt=CHOREOGRAPHER_SYSTEM.template,
            config=PromptConfig(
                enable_thinking=not is_overview,
                timeout=OVERVIEW_CHOREOGRAPHY_TIMEOUT if is_overview else 300.0,
                temperature=BASE_GENERATION_TEMPERATURE,
                response_schema=CHOREOGRAPHY_SCHEMA,
                max_output_tokens=get_choreography_max_output_tokens(
                    duration_seconds=duration,
                    is_overview=is_overview,
                ),
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
