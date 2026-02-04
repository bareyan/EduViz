import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union

from app.core import get_logger
from app.services.infrastructure.llm import PromptingEngine, PromptConfig, CostTracker

from ..config import MAX_CLEAN_RETRIES, MAX_SURGICAL_FIX_ATTEMPTS
from ..prompts import (
    IMPLEMENTER_SYSTEM,
    FIXER_SYSTEM,
    CHOREOGRAPHER_SYSTEM,
    CHOREOGRAPHY_USER,
    FULL_IMPLEMENTATION_USER,
    SURGICAL_FIX_USER
)
from .core import (
    clean_code,
    ChoreographyError,
    ImplementationError,
    RefinementError
)
# Integration: Import Validator
from .core.validation import StaticValidator, RuntimeValidator

logger = get_logger(__name__, component="animation_processors")


class Animator:
    """Orchestrates the hybrid agentic animation generation pipeline.
    
    Architecture:
    1. Conceptual Planning (Choreography): High-reasoning model establishes visuals.
    2. Primary Implementation: Balanced model produces initial code candidate.
    3. Refinement Cycle: Iterative surgical edits (currently stubbed to valid).
    """
    
    def __init__(
        self, 
        engine: PromptingEngine, 
        max_fix_attempts: int = MAX_SURGICAL_FIX_ATTEMPTS,
        cost_tracker: Optional[CostTracker] = None,
        keep_debug_frames: bool = False
    ):
        """Initializes dependencies and sub-engines.
        
        Args:
            engine: Primary engine for implementation.
            max_fix_attempts: Tolerance for iterative surgical refinements.
            cost_tracker: Monitor for token usage and latency.
            keep_debug_frames: If True, screenshot artifacts are not auto-cleaned.
        """
        self.engine = engine
        self.max_fix_attempts = max_fix_attempts
        self.cost_tracker = cost_tracker or engine.cost_tracker
        self.keep_debug_frames = keep_debug_frames
        
        # Choreography uses a specialized engine setup for high-fidelity planning.
        self.choreography_engine = PromptingEngine(
            config_key="animation_choreography",
            cost_tracker=self.cost_tracker
        )
        
        # Internal buffer for agent memory across a refinement session.
        self.fix_history: List[Dict[str, str]] = []
        self._consecutive_agent_failures = 0
        
        # Integration: Validator
        self.validator = StaticValidator()
        self.runtime_validator = RuntimeValidator()

    async def animate(self, section: Dict[str, Any], duration: float, context: Optional[Dict[str, Any]] = None) -> str:
        """Executes the animation lifecycle for a narrative section.
        
        Returns:
            Manim code string.
        """
        section_title = section.get("title", f"Section {section.get('index', '')}")
        
        for attempt_idx in range(MAX_CLEAN_RETRIES):
            if attempt_idx > 0:
                logger.warning(f"Strategy Pivot: Attempting clean regeneration for '{section_title}'")
            
            self.fix_history = []
            self._consecutive_agent_failures = 0
            
            try:
                # Stage 1: Choreography (Gemini 3 Pro Thinking)
                plan = await self._plan_visuals(section, duration, context)
                
                # Stage 2: Implementation (Gemini 3 Flash Thinking)
                code = await self._generate_implementation(section, plan, duration, context)

                # Stage 3: Refinement (Multi-turn Agent Loop)
                # We assume validity for now, effectively skipping the loop unless logic changes
                code, stabilized = await self._run_refinement_cycle(code, section_title, context)
                
                return code
                    
            except (ChoreographyError, ImplementationError) as e:
                logger.error(f"Stage failure in animation pipeline: {e}")
                continue
        
        # Graceful fallback: return empty if all retries fail.
        logger.error(f"All {MAX_CLEAN_RETRIES} regeneration attempts exhausted for '{section_title}'.")
        return ""

    async def _run_refinement_cycle(self, code: str, title: str, context: Optional[Dict[str, Any]] = None) -> Tuple[str, bool]:
        """Manages the iterative surgical fix cycle.
        
        Returns:
            Tuple of (current_code, stabilized_bool).
        """
        current_code = code
        
        # Initial validation (skipping the "always valid" stub)
        # is_valid = True
        
        # if is_valid:
        #     return current_code, True

        # NOTE: The code below is preserved for when we re-enable validation logic.
        # It is currently unreachable due to `is_valid = True`.
        
        for turn_idx in range(1, self.max_fix_attempts + 1):
            # Automated Validation
            # Phase 1: Static
            static_result = await self.validator.validate(current_code)
            if not static_result.valid:
                error_data = "\n".join(static_result.errors)
                logger.info(f"Static validation failed (Turn {turn_idx}): {error_data[:100]}...")
            else:
                # Phase 2: Runtime (Dry Run)
                runtime_result = await self.runtime_validator.validate(current_code)
                if runtime_result.valid:
                     logger.info(f"Structural stabilization achieved for '{title}' (Turn {turn_idx})")
                     return current_code, True
                
                error_data = "\n".join(runtime_result.errors)
                logger.info(f"Runtime validation failed (Turn {turn_idx}): {error_data[:100]}...")

            self.fix_history.append({"turn": turn_idx, "error": error_data[:200]})
            
            # Orchestrate a single agent turn with tool access.
            current_code = await self._execute_refinement_turn(current_code, error_data, context)
            
        return current_code, False

    async def _execute_refinement_turn(
        self, 
        code: str, 
        errors: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Orchestrates a single turn of the Fixer agent."""
        # Import schema locally to avoid circular dependencies
        from ..prompts.structured_edit_schema import CODE_EDIT_SCHEMA
        
        # Prepare context (no validation result passed now)
        prompt = self._prepare_agent_prompt(code, errors)
        
        current_code = code
        
        result = await self.engine.generate(
            prompt=prompt,
            system_prompt=FIXER_SYSTEM.template,
            config=PromptConfig(timeout=150.0, response_schema=CODE_EDIT_SCHEMA, response_format="json"),
            context=dict(context or {}, stage="refinement")
        )
        
        if not result.get("success"):
            self._consecutive_agent_failures += 1
            logger.error(f"Agent turn failed ({self._consecutive_agent_failures}x): {result.get('error')}")
            
            if self._consecutive_agent_failures >= 2:
                raise RefinementError(f"Agent failed {self._consecutive_agent_failures} consecutive turns: {result.get('error')}")
            return current_code

        # Parse structured output
        parsed_json = result.get("parsed_json", {})
        if not parsed_json:
            self._consecutive_agent_failures += 1
            logger.warning(f"Agent returned empty JSON response (failure {self._consecutive_agent_failures})")
            
            if self._consecutive_agent_failures >= 2:
                raise RefinementError("Agent failed - consistently returning empty JSON responses.")
            return current_code

        # Reset tracking on any TRULY successful LLM response
        self._consecutive_agent_failures = 0

        # Log agent's analysis
        analysis = parsed_json.get("analysis", "No analysis provided")
        logger.info(f"Agent Analysis: {analysis}")
        
        # Apply edits
        edits = parsed_json.get("edits", [])
        if edits and isinstance(edits, list):
            current_code = self._apply_edits_atomically(current_code, edits)
        elif edits:
            logger.warning(f"Agent returned invalid edits format: {type(edits)}")
                
        return current_code

    def _apply_edits_atomically(self, code: str, edits: List[Dict[str, str]]) -> str:
        """Sequentially applies code modifications."""
        buffer = code
        for edit in edits:
            try:
                search_text = edit.get("search_text", "")
                replacement_text = edit.get("replacement_text", "")
                
                if not search_text:
                    continue
                    
                occurrences = buffer.count(search_text)
                if occurrences == 0:
                    logger.warning(f"Edit failed: Search text not found: '{search_text[:50]}...'")
                    continue
                if occurrences > 1:
                    logger.warning(f"Edit failed: Search text ambiguous ({occurrences} matches): '{search_text[:50]}...'")
                    continue
                    
                buffer = buffer.replace(search_text, replacement_text)
                
            except Exception as e:
                logger.warning(f"Discarding failed atomic edit turn: {e}")
        return buffer

    def _prepare_agent_prompt(self, code: str, errors: str) -> str:
        """Synthesizes high-density context for the Fixer agent."""
        # No available screenshots in this stubbed version
        visual_hooks = ""
            
        history_str = ""
        if len(self.fix_history) > 1:
            recent = self.fix_history[-2:]
            history_str = "\n## PREVIOUS ATTEMPTS\n" + "\n".join(
                [f"- Turn {h['turn']}: {h['error'][:100]}" for h in recent]
            )
            
        return SURGICAL_FIX_USER.format(
            code=code, 
            errors=errors, 
            visual_context=visual_hooks
        ) + history_str

    async def _plan_visuals(self, section: Dict[str, Any], duration: float, context: Optional[Dict[str, Any]] = None) -> str:
        """Delegates conceptual design to high-reasoning model."""
        prompt = CHOREOGRAPHY_USER.format(
            title=section.get("title", "Untitled"),
            narration=section.get("narration", ""),
            timing_info=json.dumps(section.get("narration_segments", []), indent=2),
            target_duration=duration
        )
        
        result = await self.choreography_engine.generate(
            prompt=prompt,
            system_prompt=CHOREOGRAPHER_SYSTEM.template,
            config=PromptConfig(enable_thinking=True, timeout=300.0),
            context=dict(context or {}, stage="choreography")
        )
        
        if not result.get("success") or not result.get("response"):
            raise ChoreographyError(f"Stage fail: Plan generation returned null.")
            
        return result["response"]

    async def _generate_implementation(self, section: Dict[str, Any], plan: str, duration: float, context: Optional[Dict[str, Any]] = None) -> str:
        """Drives the primary implementation of the Manim scene."""
        prompt = FULL_IMPLEMENTATION_USER.format(
            plan=plan,
            segment_timings=self._summarize_segments(section),
            total_duration=duration,
            section_id_title=self._derive_class_name(section)
        )
        
        result = await self.engine.generate(
            prompt=prompt,
            system_prompt=IMPLEMENTER_SYSTEM.template,
            config=PromptConfig(enable_thinking=True, timeout=300.0),
            context=dict(context or {}, stage="implementation")
        )
        
        if not result.get("success") or not result.get("response"):
            raise ImplementationError(f"Stage fail: Manim implementation returned null.")
            
        return clean_code(result["response"])

    def _summarize_segments(self, section: Dict[str, Any]) -> str:
        """Formats narration segments for LLM context optimization."""
        segs = section.get("narration_segments", [])
        return "\n".join([
            f"- T+{s.get('start_time', 0):.1f}s: {s.get('text', '')[:60]}"
            for s in segs
        ])

    def _derive_class_name(self, section: Dict[str, Any]) -> str:
        """Converts arbitrary section IDs into valid PEP8 class names."""
        raw_id = section.get("id", f"section_{section.get('index', 0)}")
        normalized = raw_id.replace("-", "_").replace(" ", "_")
        return "".join(word.title() for word in normalized.split("_"))
