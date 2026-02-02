"""
Animation Processors - Hybrid Agentic Architecture.

Pipeline:
1. Phase 1 (Planning): Deep choreography with gemini-3-pro-preview
2. Phase 2 (Generation): Single-shot code with gemini-3-flash-preview
3. Phase 3 (Fixes): Agentic loop with tools and memory
"""

import json
from typing import Dict, Any, List, Optional

from app.core import get_logger
from app.services.infrastructure.llm import PromptingEngine, PromptConfig, CostTracker
from app.services.infrastructure.llm.tools import create_tool_declaration

from ..prompts import (
    ANIMATOR_SYSTEM,
    CHOREOGRAPHER_SYSTEM,
    CHOREOGRAPHY_USER,
    FULL_IMPLEMENTATION_USER,
    SURGICAL_FIX_USER,
    get_compact_patterns
)
from .core import (
    clean_code,
    ChoreographyError,
    ImplementationError,
    RefinementError,
    ManimEditor
)
from .validation import CodeValidator, TimingAdjuster

logger = get_logger(__name__, component="animation_processors")


class Animator:
    """Hybrid Agentic Animation Generator.
    
    Uses different models for each phase:
    - Planning: gemini-3-pro-preview (deep thinking)
    - Generation: gemini-3-flash-preview (fast, accurate)
    - Fixes: gemini-3-flash-preview (tool-based surgical edits)
    """
    
    def __init__(
        self, 
        engine: PromptingEngine, 
        validator: CodeValidator, 
        max_fix_attempts: int = 5,
        cost_tracker: Optional[CostTracker] = None
    ):
        """Initializes the Animator with required infrastructure.
        
        Args:
            engine: Primary engine (used for generation and fixes)
            validator: Code validator instance
            max_fix_attempts: Maximum surgical fix attempts
            cost_tracker: Optional cost tracker for monitoring
        """
        self.engine = engine
        self.validator = validator
        self.timing_adjuster = TimingAdjuster()
        self.max_fix_attempts = max_fix_attempts
        self.editor = ManimEditor()
        self.cost_tracker = cost_tracker or engine.cost_tracker
        
        # Create separate engine for choreography (uses different model)
        self.choreography_engine = PromptingEngine(
            config_key="animation_choreography",
            cost_tracker=self.cost_tracker
        )
        
        # Fix memory for agentic loop
        self.fix_history: List[Dict[str, str]] = []

    async def animate(self, section: Dict[str, Any], duration: float) -> str:
        """Runs the hybrid animation generation pipeline.
        
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
        logger.info(f"Starting hybrid animation for '{section_title}'")
        
        # Clear fix history for new section
        self.fix_history = []
        
        # 1. Phase 1: Deep Choreography Planning (gemini-3-pro-preview)
        plan = await self._generate_plan(section, duration)
        logger.info(f"Choreography plan finalized for '{section_title}'")
        
        # 2. Phase 2: Full Implementation (gemini-3-flash-preview, single-shot)
        code = await self._generate_full_code(section, plan, duration)
        logger.info(f"Initial code generated for '{section_title}'")
        
        # 3. Phase 3: Agentic Fix Loop (with memory)
        code = await self._agentic_fix_loop(code, section_title, duration)
        
        return code


    async def _agentic_fix_loop(self, code: str, section_title: str, target_duration: float) -> str:
        """Agentic fix loop with memory and tool use.
        
        This loop:
        1. Corrects timing programmatically
        2. Validates the code
        3. If errors exist, applies surgical fix
        4. If only warnings/info, proceeds to render
        5. Stops when valid (no errors) or max attempts reached
        
        Severity behavior:
        - errors: MUST fix, blocks loop
        - warnings: Include in summary but don't block
        - info: Not sent to LLM, doesn't block
        """
        for attempt in range(1, self.max_fix_attempts + 1):
            # Deterministic timing fix (Post-processor)
            code = self.timing_adjuster.adjust(code, target_duration)
            
            validation = self.validator.validate(code)
            
            # Only errors block the loop - warnings and info don't
            has_errors = (not validation.static.valid) or (len(validation.spatial.errors) > 0)
            
            if not has_errors:
                if validation.spatial.warnings:
                    logger.info(f"Animation validated with {len(validation.spatial.warnings)} warnings (non-blocking)")
                else:
                    logger.info(f"Animation code validated successfully on attempt {attempt}")
                return code
            
            error_summary = validation.get_error_summary()
            logger.warning(f"Validation failed (Attempt {attempt}): {error_summary[:100]}...")
            
            # Record in fix history
            self.fix_history.append({
                "attempt": attempt,
                "error": error_summary[:200]
            })
            
            # Apply surgical fix with context
            code = await self._apply_surgical_fix(code, error_summary)
            
        # Final timing check and validation
        code = self.timing_adjuster.adjust(code, target_duration)
        final_validation = self.validator.validate(code)
        has_final_errors = (not final_validation.static.valid) or (len(final_validation.spatial.errors) > 0)
        
        if not has_final_errors:
            return code
        
        # Even on failure, return the code to allow a render attempt
        # The actual rendering may still work even with some issues
        logger.warning(
            f"Could not fully stabilize animation after {self.max_fix_attempts} attempts. "
            f"Proceeding with render anyway. Remaining issues: {final_validation.get_error_summary()[:100]}..."
        )
        return code


    async def _generate_plan(self, section: Dict[str, Any], duration: float) -> str:
        """Generates a visual choreography plan using deep thinking model."""
        prompt = CHOREOGRAPHY_USER.format(
            title=section.get("title", "Untitled"),
            narration=section.get("narration", ""),
            timing_info=self._format_timing_info(section),
            target_duration=duration
        )
        
        config = PromptConfig(enable_thinking=True, timeout=300.0)
        result = await self.choreography_engine.generate(
            prompt=prompt,
            system_prompt=CHOREOGRAPHER_SYSTEM.template,
            config=config
        )
        
        if not result.get("success") or not result.get("response"):
            raise ChoreographyError(
                f"Failed to generate animation plan: {result.get('error', 'Empty response')}"
            )
            
        return result["response"]


    async def _generate_full_code(self, section: Dict[str, Any], plan: str, duration: float) -> str:
        """Generates the full Manim code in one shot."""
        segment_timings = self._format_segment_timings(section)
        section_id_title = self._get_section_class_name(section)
        
        prompt = FULL_IMPLEMENTATION_USER.format(
            plan=plan,
            segment_timings=segment_timings,
            total_duration=duration,
            section_id_title=section_id_title,
            patterns=get_compact_patterns()
        )
        
        config = PromptConfig(enable_thinking=True, timeout=300.0)
        result = await self.engine.generate(
            prompt=prompt,
            system_prompt=ANIMATOR_SYSTEM.template,
            config=config
        )
        
        if not result.get("success") or not result.get("response"):
            raise ImplementationError(
                f"Failed to generate initial code: {result.get('error', 'Empty response')}"
            )
            
        return clean_code(result["response"])


    async def _apply_surgical_fix(self, code: str, errors: str) -> str:
        """Applies a surgical fix using tool calls with optional history context."""
        # Build prompt with optional history context
        history_context = ""
        if len(self.fix_history) > 1:
            recent = self.fix_history[-2:]  # Last 2 attempts
            history_context = "\n\nPREVIOUS FIX ATTEMPTS:\n" + "\n".join([
                f"- Attempt {h['attempt']}: {h['error'][:100]}..."
                for h in recent
            ])
        
        prompt = SURGICAL_FIX_USER.format(code=code, errors=errors) + history_context
        
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
            
        # Apply tool calls
        code = self._process_tool_calls(code, result)
        
        return code


    def _process_tool_calls(self, code: str, result: Dict[str, Any]) -> str:
        """Process tool calls from the LLM result."""
        tool_applied = False
        
        if result.get("function_calls"):
            for fc in result["function_calls"]:
                if fc["name"] == "apply_surgical_edit":
                    try:
                        fc["args"]["code"] = code
                        code = self.editor.execute(**fc["args"])
                        tool_applied = True
                        logger.info("Surgical edit applied successfully")
                    except Exception as e:
                        logger.warning(f"Surgical tool execution failed: {str(e)}")
        
        # Fallback: if no tool applied, check for code block in response
        if not tool_applied:
            raw_response = result.get("response")
            fallback_code = clean_code(raw_response) if raw_response else ""
            if fallback_code and len(fallback_code) > len(code) * 0.7:
                logger.info("Using fallback response code")
                return fallback_code
            
        return code


    def _format_timing_info(self, section: Dict[str, Any]) -> str:
        """Format segment timing info for the prompt."""
        segments = section.get("narration_segments", [])
        return json.dumps(segments, indent=2)


    def _format_segment_timings(self, section: Dict[str, Any]) -> str:
        """Format segment timings as readable text."""
        segments = section.get("narration_segments", [])
        return "\n".join([
            f"- Segment {i+1} ({s.get('start_time', 0):.1f}s - "
            f"{s.get('start_time', 0) + s.get('duration', 5):.1f}s): "
            f"{s.get('text', '')[:60]}..."
            for i, s in enumerate(segments)
        ])


    def _get_section_class_name(self, section: Dict[str, Any]) -> str:
        """Generate a valid Python class name from section ID."""
        section_index = section.get('index', 0)
        section_id = section.get("id", f"section_{section_index}")
        section_id = section_id.replace("-", "_").replace(" ", "_")
        return "".join(word.title() for word in section_id.split("_"))
