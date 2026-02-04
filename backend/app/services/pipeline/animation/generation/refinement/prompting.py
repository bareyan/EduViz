"""
Fixer Prompt Builder

Responsible for constructing the prompt for the adaptive fixer.
Handles retry notes, history formatting, and strategy guidance.
"""

from typing import Any, Dict, List, Optional

from ...prompts import SURGICAL_FIX_USER
from ...prompts.fixer_prompts import INITIAL_RETRY_NOTE, RETRY_FAILURE_NOTE


class FixerPromptBuilder:
    """Builds and formats prompts for the fixer agent."""

    def __init__(self, max_turn_retries: int):
        self.max_turn_retries = max_turn_retries

    def build_prompt(
        self,
        code: str,
        errors: str,
        strategy: Any,  # FixStrategy
        history: List[Dict[str, Any]],
        last_failure_reason: Optional[str],
        attempt: int,
        code_scope_note: Optional[str]
    ) -> str:
        """Build the complete adaptive prompt.
        
        Args:
            code: Code excerpt to fix
            errors: Error messages
            strategy: Selected fix strategy
            history: Failure history list
            last_failure_reason: Reason for last failure (if any)
            attempt: Current attempt number
            code_scope_note: Optional note about code truncation
            
        Returns:
            Formatted prompt string
        """
        extra_sections = []
        
        # 1. Strategy Guidance
        strategy_guidance = strategy.build_guidance()
        if strategy_guidance:
            extra_sections.append(strategy_guidance)
        
        # 2. Code Scope
        if code_scope_note:
            extra_sections.append(f"## CODE SCOPE\n{code_scope_note}")
        
        # 3. Retry Note
        retry_note = self._build_retry_note(last_failure_reason, attempt)
        if retry_note:
            extra_sections.append(f"## RETRY NOTE\n{retry_note}")
        
        # 4. History
        history_str = self._format_history(history)
        if history_str:
            extra_sections.append(history_str)
        
        # Combine
        visual_context = ""
        if extra_sections:
            visual_context = "\n" + "\n".join(extra_sections) + "\n"
        
        return SURGICAL_FIX_USER.format(
            code=code,
            errors=errors,
            visual_context=visual_context
        )

    def _build_retry_note(
        self,
        last_failure_reason: Optional[str],
        attempt: int
    ) -> Optional[str]:
        """Build retry guidance note."""
        if not last_failure_reason:
            # Even on first attempt, guide for conciseness
            return INITIAL_RETRY_NOTE.format()
        
        return RETRY_FAILURE_NOTE.format(
            failure_reason=last_failure_reason,
            attempt=attempt,
            max_retries=self.max_turn_retries
        )

    def _format_history(self, history: List[Dict[str, Any]]) -> str:
        """Format recent failure history for prompt."""
        if not history:
            return ""
        
        recent = history[-2:]  # Last 2 turns
        lines = []
        
        for h in recent:
            status = h.get("status") or "unknown"
            strategy = h.get("strategy", "unknown")
            reason = h.get("reason")
            edits = h.get("edits")
            
            line = f"Turn {h.get('turn')}: {status} | strategy: {strategy}"
            if edits is not None:
                line += f" | edits: {edits}"
            if reason:
                line += f" | reason: {reason}"
            line += f" | error: {h.get('error', '')[:60]}..."
            
            lines.append(line)
        
        return "\n## PREVIOUS ATTEMPTS\n" + "\n".join(lines)
