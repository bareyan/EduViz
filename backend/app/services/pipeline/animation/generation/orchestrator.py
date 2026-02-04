"""
Animation Orchestrator

Main coordinator for the animation generation pipeline.

Orchestrates the three stages:
1. Choreography (visual planning)
2. Implementation (code generation)  
3. Refinement (validation + fixing)

This is the new entry point, replacing the monolithic Animator class.
"""

import asyncio
from typing import Dict, Any, Optional

from app.core import get_logger
from app.services.infrastructure.llm import PromptingEngine, CostTracker

from ..config import (
    BASE_GENERATION_TEMPERATURE,
    MAX_CLEAN_RETRIES,
    TEMPERATURE_INCREMENT
)
from .stages import Choreographer, Implementer, Refiner
from .refinement import AdaptiveFixerAgent
from .core import ChoreographyError, ImplementationError


logger = get_logger(__name__, component="animation_orchestrator")


class AnimationOrchestrator:
    """
    Orchestrates the animation generation pipeline.
    
    Clean separation of concerns:
    - Manages retry logic
    - Coordinates stage execution
    - Delegates to specialized components
    - No business logic (formatting, validation, etc.)
    """
    
    def __init__(
        self,
        engine: PromptingEngine,
        cost_tracker: Optional[CostTracker] = None,
        keep_debug_frames: bool = False
    ):
        """Initialize orchestrator with dependencies.
        
        Args:
            engine: Primary prompting engine
            cost_tracker: Optional cost tracker
            keep_debug_frames: Whether to preserve debug artifacts
        """
        self.engine = engine
        self.cost_tracker = cost_tracker or engine.cost_tracker
        self.keep_debug_frames = keep_debug_frames
        
        # Initialize specialized engines for each stage
        self.choreography_engine = PromptingEngine(
            config_key="animation_choreography",
            cost_tracker=self.cost_tracker
        )
        
        # Initialize stages
        self.choreographer = Choreographer(self.choreography_engine)
        self.implementer = Implementer(self.engine)
        
        # Initialize refinement components (using adaptive fixer)
        self.fixer = AdaptiveFixerAgent(self.engine)
        self.refiner = Refiner(self.fixer)
    
    async def generate(
        self,
        section: Dict[str, Any],
        duration: float,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate animation code for a section.
        
        Main entry point for animation generation with retry logic.
        
        Args:
            section: Section dictionary with title, narration, segments
            duration: Target animation duration in seconds
            context: Optional context for logging
            
        Returns:
            Manim code string (empty string if all retries fail)
        """
        section_title = section.get("title", f"Section {section.get('index', '')}")
        last_error = None
        
        for attempt_idx in range(MAX_CLEAN_RETRIES):
            if attempt_idx > 0:
                logger.warning(
                    f"Retry attempt {attempt_idx + 1}/{MAX_CLEAN_RETRIES} "
                    f"for '{section_title}'",
                    extra={
                        "attempt": attempt_idx + 1,
                        "section_title": section_title
                    }
                )
            
            # Reset fixer state for clean retry
            self.fixer.reset()
            
            # Build retry context
            retry_context = self._build_retry_context(
                context,
                attempt_idx,
                last_error
            )
            
            try:
                # Execute pipeline stages
                code = await self._execute_pipeline(
                    section,
                    duration,
                    section_title,
                    attempt_idx,
                    retry_context
                )
                
                return code
                
            except (ChoreographyError, ImplementationError) as e:
                logger.error(
                    f"Stage failure: {e}",
                    extra={
                        "attempt": attempt_idx + 1,
                        "error_type": type(e).__name__
                    }
                )
                last_error = e
                
                # Exponential backoff before retry
                if attempt_idx < MAX_CLEAN_RETRIES - 1:
                    backoff_time = 2 ** attempt_idx
                    logger.info(f"Waiting {backoff_time}s before retry...")
                    await asyncio.sleep(backoff_time)
                continue
        
        # All retries exhausted
        logger.error(
            f"All {MAX_CLEAN_RETRIES} attempts exhausted for '{section_title}'"
        )
        return ""
    
    async def _execute_pipeline(
        self,
        section: Dict[str, Any],
        duration: float,
        section_title: str,
        attempt_idx: int,
        context: Dict[str, Any]
    ) -> str:
        """Execute the three-stage pipeline.
        
        Args:
            section: Section data
            duration: Target duration
            section_title: Section title for logging
            attempt_idx: Current retry attempt
            context: Retry context
            
        Returns:
            Final code string
        """
        # Stage 1: Choreography (visual planning)
        logger.info(f"Stage 1: Choreography for '{section_title}'")
        plan = await self.choreographer.plan(section, duration, context)
        
        # Stage 2: Implementation (code generation)
        logger.info(f"Stage 2: Implementation for '{section_title}'")
        retry_temperature = self._compute_retry_temperature(attempt_idx)
        code = await self.implementer.implement(
            section,
            plan,
            duration,
            context,
            temperature=retry_temperature
        )
        
        # Stage 3: Refinement (validation + fixing)
        logger.info(f"Stage 3: Refinement for '{section_title}'")
        code, stabilized = await self.refiner.refine(
            code,
            section_title,
            context
        )
        
        if not stabilized:
            logger.error(f"Code not stabilized for '{section_title}' after refinement")
            raise ImplementationError(
                f"Refinement failed to stabilize code for '{section_title}' - "
                f"max validation attempts exhausted"
            )
        
        return code
    
    def _build_retry_context(
        self,
        base_context: Optional[Dict[str, Any]],
        attempt_idx: int,
        last_error: Optional[Exception]
    ) -> Dict[str, Any]:
        """Build context dict for retry attempt.
        
        Args:
            base_context: Base context or None
            attempt_idx: Current retry attempt index
            last_error: Previous error if any
            
        Returns:
            Context dictionary
        """
        retry_context = dict(base_context or {})
        
        if attempt_idx > 0:
            retry_context["retry_attempt"] = attempt_idx + 1
            retry_context["retry_temperature"] = self._compute_retry_temperature(
                attempt_idx
            )
            
            if last_error:
                retry_context["previous_failure"] = str(last_error)
        
        return retry_context
    
    @staticmethod
    def _compute_retry_temperature(attempt_idx: int) -> float:
        """Compute temperature for retry attempt.
        
        Args:
            attempt_idx: Zero-based attempt index
            
        Returns:
            Temperature value
        """
        return BASE_GENERATION_TEMPERATURE + (attempt_idx * TEMPERATURE_INCREMENT)
