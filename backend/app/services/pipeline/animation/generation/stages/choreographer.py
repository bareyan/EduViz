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
        section_data = (
            section.get("section_data")
            or section.get("visual_data")
            or section.get("metadata")
        )
        prompt = CHOREOGRAPHY_USER.format(
            title=section.get("title", "Untitled"),
            narration=section.get("narration", ""),
            timing_info=json.dumps(section.get("narration_segments", []), indent=2),
            target_duration=duration,
            theme_info=section.get("theme_info", "3b1b dark educational style"),
            visual_hints=CodeFormatter.serialize_for_prompt(
                section.get("visual_hints"),
                default="No explicit visual hints",
            ),
            section_data=CodeFormatter.serialize_for_prompt(section_data),
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
