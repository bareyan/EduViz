"""
Choreographer Stage

Responsible for high-level visual planning using reasoning model.

Single Responsibility: Generate conceptual choreography plan
"""

import json
from typing import Dict, Any, Optional

from app.core import get_logger
from app.services.infrastructure.llm import PromptingEngine, PromptConfig

from ...config import BASE_GENERATION_TEMPERATURE
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
        prompt = CHOREOGRAPHY_USER.format(
            title=section.get("title", "Untitled"),
            narration=section.get("narration", ""),
            timing_info=json.dumps(section.get("narration_segments", []), indent=2),
            target_duration=duration
        )
        
        result = await self.engine.generate(
            prompt=prompt,
            system_prompt=CHOREOGRAPHER_SYSTEM.template,
            config=PromptConfig(
                enable_thinking=True,
                timeout=300.0,
                temperature=BASE_GENERATION_TEMPERATURE,
                response_schema=CHOREOGRAPHY_SCHEMA
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
