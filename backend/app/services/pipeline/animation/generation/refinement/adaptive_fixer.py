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
        """Execute one fix turn with strategy selection.
        
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
        
        last_failure_reason = None
        
        for attempt in range(1, self.max_turn_retries + 1):
            
            # Delegate prompt building
            prompt = self.prompt_builder.build_prompt(
                code=code_for_prompt,
                errors=errors,
                strategy=strategy,
                history=self._history,
                last_failure_reason=last_failure_reason,
                attempt=attempt,
                code_scope_note=code_scope_note
            )
            
            result = await self.engine.generate(
                prompt=prompt,
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
                ),
                context=dict(
                    context or {},
                    stage="refinement",
                    attempt=attempt,
                    strategy=strategy.name
                )
            )
            
            if not result.get("success"):
                last_failure_reason = result.get("error") or "llm_error"
                logger.warning(
                    f"⚠️ Fix attempt {attempt} failed: {last_failure_reason}"
                )
                continue
            
            if not self._process_result(code, result, strategy, attempt):
                # If processing failed (e.g. no edits), update reason and retry
                last_failure_reason = "edits_application_failed"
                continue

            # If success (process_result handled application and return)
            # Actually _process_result helps but to keep flow clear, let's keep logic here
            # Or better, refactor this loop body slightly.
            
            # Let's keep strict parity with previous logic for safety
            parsed_json = result.get("parsed_json") or {}
            edits = parsed_json.get("edits", [])
            
            if not edits:
                last_failure_reason = "missing_edits"
                logger.warning("⚠️ No edits returned")
                continue
            
            # Apply edits
            new_code, edit_summary = apply_edits_atomically(code, edits)
            
            if edit_summary["successful"] == 0:
                last_failure_reason = edit_summary.get(
                    "primary_failure_reason",
                    "no_edits_applied"
                )
                logger.warning(f"⚠️ Edits failed to apply: {last_failure_reason}")
                continue
            
            # Success!
            meta = {
                "status": "applied",
                "reason": None,
                "edits": edit_summary["successful"],
                "attempts": attempt,
                "strategy": strategy.name
            }
            self._record_success(errors, strategy, meta)
            self._consecutive_failures = 0
            
            return new_code, meta
        
        # All attempts failed
        self._consecutive_failures += 1
        if self._consecutive_failures >= 2:
            logger.warning(
                "Multiple consecutive failures, may need different approach"
            )
        
        meta = {
            "status": "failed",
            "reason": last_failure_reason,
            "edits": 0,
            "attempts": self.max_turn_retries,
            "strategy": strategy.name
        }
        self._record_failure(errors, strategy, meta)
        
        return code, meta

    def _record_success(
        self,
        errors: str,
        strategy: Any,
        meta: Dict[str, Any]
    ) -> None:
        """Record successful fix in history."""
        self._history.append({
            "turn": len(self._history) + 1,
            "error": errors[:200],
            "status": "success",
            "strategy": strategy.name,
            "edits": meta.get("edits"),
            "attempts": meta.get("attempts"),
            "reason": None
        })
    
    def _record_failure(
        self,
        errors: str,
        strategy: Any,
        meta: Dict[str, Any]
    ) -> None:
        """Record failed fix in history."""
        self._history.append({
            "turn": len(self._history) + 1,
            "error": errors[:200],
            "status": "failed",
            "strategy": strategy.name,
            "edits": 0,
            "attempts": meta.get("attempts"),
            "reason": meta.get("reason")
        })
