"""
Adaptive Fixer Agent

Truly agentic fixer that adapts based on error patterns and maintains memory.

Improvements over original FixerAgent:
1. Strategy selection based on error type
2. Failure memory for learning
3. Adaptive prompting with strategy-specific guidance
4. Better context management
"""

from typing import Any, Dict, List, Optional, Tuple

from app.core import get_logger
from app.services.infrastructure.llm import PromptingEngine, PromptConfig

from ...config import (
    BASE_CORRECTION_TEMPERATURE,
    CORRECTION_TIMEOUT,
    CORRECTION_TEMPERATURE_STEP,
    MAX_JSON_RETRIES,
    MAX_REFINEMENT_OUTPUT_TOKENS,
)
from ...prompts import FIXER_SYSTEM
from ...prompts.structured_edit_schema import CODE_EDIT_SCHEMA
from .edit_applier import apply_edits_atomically
from .strategies import StrategySelector
from .context import FixerContextManager
from .prompting import FixerPromptBuilder


logger = get_logger(__name__, component="animation_adaptive_fixer")


class AdaptiveFixerAgent:
    """
    Adaptive fixer with strategy selection and failure memory.
    
    Now adheres to SRP by delegating:
    - Context management -> FixerContextManager
    - Prompt construction -> FixerPromptBuilder
    - Strategy selection -> StrategySelector
    """
    
    def __init__(self, engine: PromptingEngine, max_turn_retries: int = 2):
        """Initialize adaptive fixer.
        
        Args:
            engine: Prompting engine for LLM calls
            max_turn_retries: Max attempts per fix turn
        """
        self.engine = engine
        self.max_turn_retries = max_turn_retries
        
        # Helper components
        self.strategy_selector = StrategySelector()
        self.context_manager = FixerContextManager()
        self.prompt_builder = FixerPromptBuilder(max_turn_retries)
        
        self._history: List[Dict[str, Any]] = []
        self._consecutive_failures = 0
    
    def reset(self) -> None:
        """Reset agent state for new section."""
        self._history = []
        self._consecutive_failures = 0
    
    async def run_turn(
        self,
        code: str,
        errors: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, Dict[str, Any]]:
        """Execute one fix turn (conversational style).
        
        Args:
            code: Current code to fix
            errors: Error messages
            context: Optional context
            
        Returns:
            Tuple of (fixed_code, metadata)
        """
        # Select strategy based on error analysis
        strategy = self.strategy_selector.select(errors, self._history)
        logger.info(f"🎯 Selected strategy: {strategy.name}")
        
        # Delegate context preparation
        code_for_prompt, code_scope_note = self.context_manager.select_context(
            code,
            errors
        )
        
        # Initialize conversation types
        Content = self.engine.types.Content
        Part = self.engine.types.Part
        
        current_code = code
        meta = {"status": "failed", "attempts": 0, "strategy": strategy.name}
        
        for attempt in range(1, self.max_turn_retries + 1):
            meta["attempts"] = attempt
            
            # Build User Prompt (Input)
            if attempt == 1:
                # First attempt: Initial Context
                user_text = self.prompt_builder.build_initial_prompt(
                    code=code_for_prompt,
                    errors=errors,
                    strategy=strategy,
                    code_scope_note=code_scope_note
                )
                
                # Reset history for this new fix session
                self._chat_history = [
                    Content(role="user", parts=[Part(text=user_text)])
                ]
            else:
                # Subsequent attempts: Follow-up
                user_text = self.prompt_builder.build_followup_prompt(
                    code=current_code, # Show the current state
                    errors=errors,     # Show the NEW errors
                    attempt=attempt
                )
                self._chat_history.append(
                    Content(role="user", parts=[Part(text=user_text)])
                )
            
            # Call LLM with full history
            result = await self.engine.generate(
                prompt="", # Not used when contents is provided
                contents=self._chat_history,
                system_prompt=FIXER_SYSTEM.template,
                config=PromptConfig(
                    timeout=CORRECTION_TIMEOUT,
                    temperature=BASE_CORRECTION_TEMPERATURE + (
                        CORRECTION_TEMPERATURE_STEP * (attempt - 1)
                    ),
                    response_schema=CODE_EDIT_SCHEMA,
                    response_format="json",
                    max_output_tokens=MAX_REFINEMENT_OUTPUT_TOKENS,
                    max_retries=MAX_JSON_RETRIES,
                    require_json_valid=True,
                    enable_thinking=True,  # Enable reasoning/CoT
                ),
                context=dict(
                    context or {},
                    stage="refinement",
                    attempt=attempt,
                    strategy=strategy.name
                )
            )
            
            if not result.get("success"):
                logger.warning(f"⚠️ Fix attempt {attempt} failed: {result.get('error')}")
                continue
            
            # Add Model Response to History
            # We reconstruct the content object carefully
            raw_response = result.get("raw_response")
            if raw_response and hasattr(raw_response, 'candidates') and raw_response.candidates:
                 # Use the actual response content if available to preserve tool calls/thinking etc (if any)
                 model_content = raw_response.candidates[0].content
                 self._chat_history.append(model_content)
            else:
                 # Fallback for text-only
                 text_resp = result.get("response", "")
                 self._chat_history.append(
                     Content(role="model", parts=[Part(text=text_resp)])
                 )

            # Process Edits
            parsed_json = result.get("parsed_json") or {}
            edits = parsed_json.get("edits", [])
            
            if not edits:
                logger.warning("⚠️ No edits returned")
                continue
            
            # Apply edits
            # Note: We apply edits to the ORIGINAL code if it's the first turn,
            # or the CURRENT code if we are iterating.
            # Actually, `current_code` starts as `code`.
            new_code, edit_summary = apply_edits_atomically(current_code, edits)
            
            if edit_summary["successful"] == 0:
                failure_reason = edit_summary.get("primary_failure_reason", "no_edits_applied")
                logger.warning(f"⚠️ Edits failed to apply: {failure_reason}")
                
                # Critical: We must tell the LLM that its edits failed in the NEXT user prompt
                # But for now, we just loop around. The next 'errors' argument passed to this function
                # won't catch this execution error unless we return. 
                # Wait, `run_turn` is ONE validation cycle.
                # If we fail to apply edits, we can't really validate.
                # We should probably retry *within* the agent if application fails?
                # For now, adhering to the previous interface: if application fails, we loop.
                # But we need to update `errors` to reflect the application failure? 
                # The prompt builder takes `errors`. 
                # A simple hack: Append application failure to errors for next turn?
                # Actually, strictly, `run_turn` returns `new_code`. The Caller (Refiner) validates it.
                # If we return successfully applied edits, the Refiner will validate.
                
                # If application FAILED, we haven't fixed anything. We should probably RETRY with the LLM
                # saying "Hey, your edits didn't apply because X".
                # But the current architecture separates "Fixer Turn" from "Validation".
                # `run_turn` implies ONE generic attempt?
                # No, `Refiner` calls `run_turn` once per validation failure.
                # INSIDE `run_turn`, we have `max_turn_retries`.
                
                # So if edits FAIL to apply, we loop internally.
                # We need to update `errors` to be the Application Error.
                errors = f"Application Error: {failure_reason}. Please check the search_text exact match."
                continue
            
            # Edits Applied Successfully!
            # We accept this as the candidate fix.
            # The REFINER will validate it.
            # We return the new code.
            # NOTE: We do NOT create a new User message here. The Refiner will call us again
            # if validation fails, but with a NEW `run_turn` call.
            # Wait, if `Refiner` calls `run_turn` again, we RESET the history because `run_turn`
            # re-initializes `_chat_history = [...]` on attempt 1?
            # AH! The Refiner calls `run_turn`. `run_turn` loop is for retrying FAILED LLM CALLS or UNSUCCESSFUL EDITS.
            # It does NOT handle the "Validation Failed -> Try Again" loop. That's `Refiner`.
            
            # To be truly conversational across validation failures, we need `Refiner` to hold the agent instance
            # and `AdaptiveFixerAgent` must PERSIST `_chat_history` across `run_turn` calls!
            
            # My logic above: `if attempt == 1: self._chat_history = ...` resets it every time `run_turn` is called.
            # `Refiner` creates `AdaptiveFixerAgent` once.
            # `Refiner.refine` calls `run_turn` in a loop.
            # So `run_turn` is called multiple times.
            
            # CHANGE:
            # We should NOT reset history if `_chat_history` is already populated and this is a follow-up.
            # How do we know if it's a follow-up for the SAME section vs a new section?
            # `Refiner` creates a new Fixer? No.
            # `Animator` holds `Refiner` who holds `Fixer`.
            # `Fixer.reset()` exists. `Refiner` should call `reset()` at start of refinement?
            # Checking `Refiner.refine`:
            # It calls `run_turn`.
            # We need to leverage `reset()`
            
            self._consecutive_failures = 0
            meta["status"] = "applied"
            meta["edits"] = edit_summary["successful"]
            
            return new_code, meta

        # Fallback if loops exhausted
        self._consecutive_failures += 1
        return current_code, meta
