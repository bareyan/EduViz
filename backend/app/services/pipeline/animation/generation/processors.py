"""
Animation Processors - Specialized handlers for each stage of the animation pipeline.

Following Google-quality standards:
- SRP: Each class has a single, well-defined responsibility.
- No Silent Failures: Exceptions are raised instead of returning fallbacks.
- Strong Typing: All methods use type hints.
- Documentation: Google-style docstrings.
"""

import json
from typing import Dict, Any, List, Optional
from app.core import get_logger
from app.services.infrastructure.llm import PromptingEngine, PromptConfig
from ..prompts import (
    CHOREOGRAPHER_SYSTEM, CHOREOGRAPHER_USER,
    CODER_SYSTEM, CODER_USER,
    REPAIR_SYSTEM, REPAIR_USER
)
from .code_helpers import clean_code
from .validation import CodeValidator
from .exceptions import ChoreographyError, ImplementationError, RefinementError

logger = get_logger(__name__, component="animation_processors")

class AnimationStage:
    """Base class for all animation pipeline stages.
    
    Provides shared infrastructure for LLM interaction.
    """
    def __init__(self, engine: PromptingEngine):
        """Initializes the stage with a prompting engine.
        
        Args:
            engine: The PromptingEngine instance to use for LLM calls.
        """
        self.engine = engine

class Choreographer(AnimationStage):
    """Stage 1: Converts narration into a visual choreography plan.
    
    This stage handles the high-level 'Visual Pedagogy', deciding what
    objects appear and how they move to support the learning goals.
    """
    
    async def plan(self, section: Dict[str, Any]) -> str:
        """Generates a visual plan from narration text.
        
        Args:
            section: Dictionary containing 'title', 'narration', and 'narration_segments'.
            
        Returns:
            A string containing the detailed choreography plan.
            
        Raises:
            ChoreographyError: If the LLM call fails or returns empty results.
        """
        logger.info(f"Choreographing section: {section.get('title', 'Untitled')}")
        
        prompt = CHOREOGRAPHER_USER.format(
            title=section.get("title", f"Section {section.get('index', '')}"),
            narration=section.get("narration", ""),
            timing_info=json.dumps(section.get("narration_segments", []), indent=2)
        )
        
        config = PromptConfig(enable_thinking=True, timeout=300.0)
        result = await self.engine.generate(
            prompt, config, system_prompt=CHOREOGRAPHER_SYSTEM.template
        )
        
        if not result.get("success") or not result.get("response"):
            logger.error("Choreography failed to generate response")
            raise ChoreographyError(f"Failed to generate choreography plan: {result.get('error', 'Empty response')}")
            
        return result["response"]

class Implementer(AnimationStage):
    """Stage 2: Converts a choreography plan into Manim Python code.
    
    Focuses on technical implementation, syntax accuracy, and 
    precise synchronization with audio durations.
    """
    
    async def implement(self, section: Dict[str, Any], plan: str, duration: float) -> str:
        """Translates a visual plan into Manim construct() code.
        
        Args:
            section: Section metadata.
            plan: The output from the Choreographer stage.
            duration: The target duration in seconds for this animation section.
            
        Returns:
            The raw Python code for the construct() method body.
            
        Raises:
            ImplementationError: If code generation fails.
        """
        logger.info(f"Implementing Manim code for section: {section.get('title', 'Untitled')}")
        
        prompt = CODER_USER.format(
            title=section.get("title", "Section"),
            choreography_plan=plan,
            target_duration=duration
        )
        
        config = PromptConfig(enable_thinking=True, timeout=300.0)
        result = await self.engine.generate(
            prompt, config, system_prompt=CODER_SYSTEM.template
        )
        
        if not result.get("success") or not result.get("response"):
            logger.error("Code implementation failed to generate response")
            raise ImplementationError(f"Failed to implement Manim code: {result.get('error', 'Empty response')}")
            
        return clean_code(result["response"])

class Refiner(AnimationStage):
    """Stage 3: Iteratively fixes code based on validation feedback.
    
    Acts as the Quality Control gate. It receives errors from the 
    CodeValidator and prompts the LLM to fix them while preserving intent.
    """
    
    def __init__(self, engine: PromptingEngine, validator: CodeValidator, max_attempts: int = 3):
        """Initializes the refiner with a validator and safety limits.
        
        Args:
            engine: PromptingEngine for repair calls.
            validator: The CodeValidator instance for quality checks.
            max_attempts: Maximum number of repair iterations before failing.
        """
        super().__init__(engine)
        self.validator = validator
        self.max_attempts = max_attempts

    async def refine(self, code: str, section: Dict[str, Any]) -> str:
        """Refines code iteratively until it passes validation.
        
        Args:
            code: Initial Manim code to validate and fix.
            section: Section metadata for context.
            
        Returns:
            Hardware-verified Manim code that passed all checks.
            
        Raises:
            RefinementError: If valid code cannot be produced within max_attempts.
        """
        current_code = code
        
        for attempt in range(1, self.max_attempts + 1):
            validation = self.validator.validate(current_code)
            
            if validation.valid:
                logger.info(f"Code validated successfully on attempt {attempt}")
                return current_code
                
            logger.warning(f"Validation failed (Attempt {attempt}/{self.max_attempts}): "
                           f"{validation.get_error_summary()[:200]}...")
            
            errors = validation.get_error_summary()
            prompt = REPAIR_USER.format(
                errors=errors,
                code=current_code
            )
            
            config = PromptConfig(enable_thinking=False, timeout=300.0)
            result = await self.engine.generate(
                prompt, config, system_prompt=REPAIR_SYSTEM.template
            )
            
            if not result.get("success") or not result.get("response"):
                logger.error(f"Refinement LLM call failed on attempt {attempt}")
                raise RefinementError(f"Refinement failed during LLM call: {result.get('error', 'Empty response')}")
                
            current_code = clean_code(result["response"])
            
        # If we exit the loop, we failed to stabilize the code
        raise RefinementError(f"Refinement exceeded max attempts ({self.max_attempts}) without passing validation")
