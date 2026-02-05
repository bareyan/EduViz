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
from ...prompts import CODE_EDIT_SCHEMA
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
        strategy = self.strategy_selector.select(errors)
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
                errors = f"Application Error: {failure_reason}. Please check the search_text exact match."
                continue
            self._consecutive_failures = 0
            meta["status"] = "applied"
            meta["edits"] = edit_summary["successful"]
            
            return new_code, meta

        # Fallback if loops exhausted
        self._consecutive_failures += 1
        return current_code, meta
