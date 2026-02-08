"""
Fixer Prompt Builder

Responsible for constructing the prompt for the adaptive fixer.
Handles retry notes, history formatting, and strategy guidance.
"""

from typing import Any, Optional

from ...prompts import SURGICAL_FIX_USER, SURGICAL_FIX_FOLLOWUP
from ...prompts.fixer_prompts import INITIAL_RETRY_NOTE


class FixerPromptBuilder:
    """Builds and formats prompts for the fixer agent."""

    def __init__(self, max_turn_retries: int):
        self.max_turn_retries = max_turn_retries

    def build_initial_prompt(
        self,
        code: str,
        errors: str,
        strategy: Any,  # FixStrategy
        code_scope_note: Optional[str] = None
    ) -> str:
        """Build the INITIAL prompt for the new conversation.
        
        Args:
            code: Code excerpt to fix
            errors: Error messages
            strategy: Selected fix strategy
            code_scope_note: Optional note about code truncation
            
        Returns:
            Formatted initial user prompt
        """
        extra_sections = []
        
        # 1. Strategy Guidance
        strategy_guidance = strategy.build_guidance()
        if strategy_guidance:
            extra_sections.append(strategy_guidance)
        
        # 2. Code Scope
        if code_scope_note:
            extra_sections.append(f"## CODE SCOPE\n{code_scope_note}")
            
        # 3. Initial Guidance Note
        # We always provide the initial retry note for the first message
        extra_sections.append(f"## GUIDANCE\n{INITIAL_RETRY_NOTE.format()}")
        
        # Combine
        visual_context = ""
        if extra_sections:
            visual_context = "\n" + "\n".join(extra_sections) + "\n"
        
        return SURGICAL_FIX_USER.format(
            code=code,
            errors=errors,
            visual_context=visual_context
        )

    def build_followup_prompt(
        self,
        code: str,
        errors: str,
        attempt: int
    ) -> str:
        """Build a FOLLOW-UP prompt for the ongoing conversation.
        
        Args:
            code: The current state of the code (after previous edits)
            errors: The new error messages
            attempt: Current attempt number
            
        Returns:
            Formatted follow-up prompt
        """
        return SURGICAL_FIX_FOLLOWUP.format(
            code=code,
            errors=errors
        )
