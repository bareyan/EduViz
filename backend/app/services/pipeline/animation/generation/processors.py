"""
Animation Processors - specialized handlers for the animation pipeline.

Following Google-quality standards:
- Single-Shot Generation: Entire scene code generated in one call for consistency.
- Surgical Edits: Isolated, fresh-context fixes for validation errors.
- No Technical Debt: Zero legacy multi-turn code or segmented logic.
- Clean Architecture: Decoupled validation and rendering.
"""

import json
from typing import Dict, Any, Optional

from app.core import get_logger
from app.services.infrastructure.llm import PromptingEngine, PromptConfig
from app.services.infrastructure.llm.tools import create_tool_declaration

from ..prompts import (
    ANIMATOR_SYSTEM, 
    ANIMATOR_USER, 
    FULL_IMPLEMENTATION_USER,
    SURGICAL_FIX_USER
)
from .core import (
    clean_code,
    ChoreographyError,
    ImplementationError,
    RefinementError,
    ManimEditor
)
from .validation import CodeValidator

logger = get_logger(__name__, component="animation_processors")

class Animator:
    """Unified Animation Agent - Single-Shot Architecture.
    
    This agent manages the complete lifecycle of creating an animation:
    1. Visual Planning (Choreography)
    2. Full Code Implementation (Single-shot)
    3. Isolated Surgical Refinement (based on validator feedback)
    """
    
    def __init__(self, engine: PromptingEngine, validator: CodeValidator, max_fix_attempts: int = 3):
        """Initializes the Animator with required infrastructure."""
        self.engine = engine
        self.validator = validator
        self.max_fix_attempts = max_fix_attempts
        self.editor = ManimEditor()

    async def animate(self, section: Dict[str, Any], duration: float) -> str:
        """Runs the single-shot animation generation pipeline.
        
        Args:
            section: Section metadata from narration stage.
            duration: Target duration for the animation.
            
        Returns:
            The complete Manim code for the section.
            
        Raises:
            ChoreographyError: If planning fails.
            ImplementationError: If initial code generation fails.
            RefinementError: If surgical fixes fail to stabilize the code.
        """
        section_title = section.get("title", f"Section {section.get('index', '')}")
        logger.info(f"Starting single-shot animation for '{section_title}'")
        
        # 1. Phase 1: Holistic Planning
        plan = await self._generate_plan(section, duration)
        logger.info(f"Choreography plan finalized for '{section_title}'")
        
        # 2. Phase 2: Full Implementation (Single-Shot)
        code = await self._generate_full_code(section, plan, duration)
        logger.info(f"Initial code generated for '{section_title}'")
        logger.debug(f"Initial cleaned code:\n{code}")
        
        # 3. Phase 3: Surgical Refinement Loop
        for attempt in range(1, self.max_fix_attempts + 1):
            validation = self.validator.validate(code)
            
            if validation.valid:
                logger.info(f"Animation code validated successfully on attempt {attempt}")
                return code
            
            error_summary = validation.get_error_summary()
            logger.warning(f"Validation failed (Attempt {attempt}): {error_summary[:100]}...")
            
            if attempt > self.max_fix_attempts:
                break
                
            code = await self._apply_surgical_fix(code, error_summary)
            logger.debug(f"Code after surgical fix (attempt {attempt}):\n{code}")
            
        # Final validation check
        final_validation = self.validator.validate(code)
        if final_validation.valid:
            return code
            
        raise RefinementError(
            f"Could not stabilize animation code after {self.max_fix_attempts} surgical fix attempts. "
            f"Final errors: {final_validation.get_error_summary()}"
        )

    async def _generate_plan(self, section: Dict[str, Any], duration: float) -> str:
        """Generates a visual choreography plan."""
        prompt = ANIMATOR_USER.format(
            title=section.get("title", "Untitled"),
            narration=section.get("narration", ""),
            timing_info=json.dumps(section.get("narration_segments", []), indent=2),
            target_duration=duration
        )
        
        config = PromptConfig(enable_thinking=True, timeout=300.0)
        result = await self.engine.generate(
            prompt=prompt,
            system_prompt=ANIMATOR_SYSTEM.template,
            config=config
        )
        
        if not result.get("success") or not result.get("response"):
            raise ChoreographyError(f"Failed to generate animation plan: {result.get('error', 'Empty response')}")
            
        return result["response"]

    async def _generate_full_code(self, section: Dict[str, Any], plan: str, duration: float) -> str:
        """Generates the full Manim code in one call."""
        segments = section.get("narration_segments", [])
        segment_timings = "\n".join([
            f"- Segment {i+1} ({s.get('start_time', 0):.1f}s - {s.get('start_time', 0) + s.get('duration', 5):.1f}s): "
            f"{s.get('text', '')[:60]}..."
            for i, s in enumerate(segments)
        ])
        
        # Generate class name for the prompt
        section_index = section.get('index', 0)
        section_id = section.get("id", f"section_{section_index}").replace("-", "_").replace(" ", "_")
        section_id_title = "".join(word.title() for word in section_id.split("_"))
        
        prompt = FULL_IMPLEMENTATION_USER.format(
            plan=plan,
            segment_timings=segment_timings,
            total_duration=duration,
            section_id_title=section_id_title
        )
        
        config = PromptConfig(enable_thinking=True, timeout=300.0)
        result = await self.engine.generate(
            prompt=prompt,
            system_prompt=ANIMATOR_SYSTEM.template,
            config=config
        )
        
        if not result.get("success") or not result.get("response"):
            raise ImplementationError(f"Failed to generate initial code: {result.get('error', 'Empty response')}")
            
        return clean_code(result["response"])

    async def _apply_surgical_fix(self, code: str, errors: str) -> str:
        """Applies a surgical fix to existing code using tool calls."""
        prompt = SURGICAL_FIX_USER.format(code=code, errors=errors)
        
        tool_declarations = [create_tool_declaration(self.editor, self.engine.types)]
        config = PromptConfig(timeout=120.0)
        
        result = await self.engine.generate(
            prompt=prompt,
            system_prompt=ANIMATOR_SYSTEM.template,
            tools=tool_declarations,
            config=config
        )
        
        if not result.get("success"):
            logger.error(f"Surgical fix call failed: {result.get('error')}")
            return code
            
        # Handle tool calls for surgical edits
        tool_applied = False
        if result.get("function_calls"):
            for fc in result["function_calls"]:
                if fc["name"] == "apply_surgical_edit":
                    try:
                        # Ensure we use the current code context for the edit
                        fc["args"]["code"] = code
                        code = self.editor.execute(**fc["args"])
                        tool_applied = True
                        logger.info("Surgical edit applied successfully")
                    except Exception as e:
                        logger.warning(f"Surgical tool execution failed: {str(e)}")
        
        # Check if LLM also returned a code block as fallback
        # ONLY if tool wasn't applied or we want to allow hybrid (careful here)
        if not tool_applied:
            raw_response = result.get("response")
            fallback_code = clean_code(raw_response) if raw_response else ""
            if fallback_code and len(fallback_code) > len(code) * 0.7:
                # If the response contains a large valid-looking code block, assume it's a full fix
                logger.info("Using fallback response code as no tool was successfully applied")
                return fallback_code
            
        return code
