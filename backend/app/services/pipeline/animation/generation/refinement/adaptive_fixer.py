"""
Adaptive Fixer Agent

Truly agentic fixer that adapts based on error patterns and maintains memory.

Improvements over original FixerAgent:
1. Strategy selection based on error type
2. Failure memory for learning
3. Adaptive prompting with strategy-specific guidance
4. Better context management
"""

import re
from typing import Any, Dict, List, Optional, Tuple

from app.core import get_logger
from app.services.infrastructure.llm import PromptingEngine, PromptConfig

from ...config import (
    BASE_CORRECTION_TEMPERATURE,
    CORRECTION_TIMEOUT,
    CORRECTION_TEMPERATURE_STEP,
    HEAD_TAIL_LINES,
    MAX_JSON_RETRIES,
    MAX_PROMPT_CODE_CHARS,
    MAX_REFINEMENT_OUTPUT_TOKENS,
    SNIPPET_CONTEXT_RADIUS,
    SNIPPET_MAX_LINES,
)
from ...prompts import FIXER_SYSTEM, SURGICAL_FIX_USER
from ...prompts.structured_edit_schema import CODE_EDIT_SCHEMA
from .edit_applier import apply_edits_atomically
from .strategies import StrategySelector


logger = get_logger(__name__, component="animation_adaptive_fixer")


class AdaptiveFixerAgent:
    """
    Adaptive fixer with strategy selection and failure memory.
    
    Key features:
    - Analyzes error patterns
    - Selects specialized fix strategy
    - Maintains failure history for learning
    - Adapts prompts based on context
    """
    
    def __init__(self, engine: PromptingEngine, max_turn_retries: int = 2):
        """Initialize adaptive fixer.
        
        Args:
            engine: Prompting engine for LLM calls
            max_turn_retries: Max attempts per fix turn
        """
        self.engine = engine
        self.max_turn_retries = max_turn_retries
        self.strategy_selector = StrategySelector()
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
        
        # Prepare code for prompt (may truncate/excerpt)
        code_for_prompt, code_scope_note = self._select_code_for_prompt(
            code,
            errors
        )
        
        last_failure_reason = None
        
        for attempt in range(1, self.max_turn_retries + 1):
            retry_note = self._build_retry_note(last_failure_reason, attempt)
            
            prompt = self._build_adaptive_prompt(
                code=code_for_prompt,
                errors=errors,
                strategy=strategy,
                retry_note=retry_note,
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
            
            # Extract and validate edits
            parsed_json = result.get("parsed_json") or {}
            analysis = parsed_json.get("analysis", "")
            if analysis:
                logger.info(f"🔍 Analysis: {analysis}")
            
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
    
    def _build_adaptive_prompt(
        self,
        code: str,
        errors: str,
        strategy: Any,  # FixStrategy
        retry_note: Optional[str],
        code_scope_note: Optional[str]
    ) -> str:
        """Build prompt with strategy-specific guidance.
        
        Args:
            code: Code to fix
            errors: Error messages
            strategy: Selected fix strategy
            retry_note: Optional retry guidance
            code_scope_note: Optional code scope info
            
        Returns:
            Complete prompt string
        """
        extra_sections = []
        
        # Add strategy guidance
        strategy_guidance = strategy.build_guidance()
        if strategy_guidance:
            extra_sections.append(strategy_guidance)
        
        # Add code scope note
        if code_scope_note:
            extra_sections.append(f"## CODE SCOPE\n{code_scope_note}")
        
        # Add retry note
        if retry_note:
            extra_sections.append(f"## RETRY NOTE\n{retry_note}")
        
        # Add failure history
        history_str = self._format_history()
        if history_str:
            extra_sections.append(history_str)
        
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
        """Build retry guidance note.
        
        Args:
            last_failure_reason: Previous failure reason
            attempt: Current attempt number
            
        Returns:
            Retry note or None
        """
        if not last_failure_reason:
            # Even on first attempt, guide for conciseness
            return (
                "CRITICAL: Keep response SHORT and FOCUSED:\n"
                "- analysis: max 2 sentences\n"
                "- edits: 1-2 edits maximum\n"
                "- search_text: 5-10 lines context\n"
                "- replacement_text: only changed lines\n"
                "This prevents JSON truncation issues."
            )
        
        return (
            f"Previous attempt failed: {last_failure_reason}. "
            f"Attempt {attempt}/{self.max_turn_retries}. "
            "Return ONLY valid JSON. Keep edits MINIMAL (1 edit preferred). "
            "Short search_text (5-10 lines), brief analysis (1-2 sentences). "
            "Ensure complete JSON to avoid truncation."
        )
    
    def _format_history(self) -> str:
        """Format recent failure history for prompt.
        
        Returns:
            Formatted history string or empty
        """
        if not self._history:
            return ""
        
        recent = self._history[-2:]  # Last 2 turns
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
    
    def _record_success(
        self,
        errors: str,
        strategy: Any,
        meta: Dict[str, Any]
    ) -> None:
        """Record successful fix in history.
        
        Args:
            errors: Error messages
            strategy: Strategy used
            meta: Fix metadata
        """
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
        """Record failed fix in history.
        
        Args:
            errors: Error messages
            strategy: Strategy used
            meta: Fix metadata
        """
        self._history.append({
            "turn": len(self._history) + 1,
            "error": errors[:200],
            "status": "failed",
            "strategy": strategy.name,
            "edits": 0,
            "attempts": meta.get("attempts"),
            "reason": meta.get("reason")
        })
    
    def _select_code_for_prompt(
        self,
        code: str,
        errors: str
    ) -> Tuple[str, Optional[str]]:
        """Select relevant code excerpt for prompt.
        
        For large files, extracts relevant sections around error lines.
        
        Args:
            code: Full code
            errors: Error messages
            
        Returns:
            Tuple of (code_excerpt, scope_note)
        """
        if len(code) <= MAX_PROMPT_CODE_CHARS:
            return code, None
        
        # Try to extract error line numbers
        line_numbers = self._extract_error_line_numbers(errors)
        
        if line_numbers:
            snippets = self._build_code_snippets(code, line_numbers)
            if snippets:
                note = (
                    "Code below shows only snippets around error lines. "
                    "Keep search_text within shown lines."
                )
                return "\n\n".join(snippets), note
        
        # Fallback: head + tail
        lines = code.splitlines()
        if not lines:
            return code, None
        
        head = "\n".join(lines[:HEAD_TAIL_LINES])
        tail = "\n".join(lines[-HEAD_TAIL_LINES:]) if len(lines) > HEAD_TAIL_LINES else ""
        
        trimmed = head if not tail else f"{head}\n\n# ...snip...\n\n{tail}"
        note = (
            "Code is truncated (head/tail only). "
            "Keep search_text within shown lines."
        )
        
        return trimmed, note
    
    def _extract_error_line_numbers(self, errors: str) -> List[int]:
        """Extract line numbers from error messages.
        
        Args:
            errors: Error messages
            
        Returns:
            Sorted list of unique line numbers
        """
        line_nums = []
        for match in re.finditer(r"\\bLine\\s+(\\d+)\\b", errors):
            try:
                line_nums.append(int(match.group(1)))
            except ValueError:
                continue
        return sorted(set(line_nums))
    
    def _build_code_snippets(
        self,
        code: str,
        line_numbers: List[int],
        context_radius: int = SNIPPET_CONTEXT_RADIUS,
        max_total_lines: int = SNIPPET_MAX_LINES
    ) -> List[str]:
        """Build code snippets around error lines.
        
        Args:
            code: Full code
            line_numbers: Lines to excerpt around
            context_radius: Lines before/after each error line
            max_total_lines: Maximum total lines across all snippets
            
        Returns:
            List of code snippet strings
        """
        lines = code.splitlines()
        if not lines:
            return []
        
        # Build ranges around each error line
        ranges: List[Tuple[int, int]] = []
        for ln in line_numbers:
            start = max(1, ln - context_radius)
            end = min(len(lines), ln + context_radius)
            ranges.append((start, end))
        
        # Merge overlapping ranges
        ranges.sort()
        merged: List[Tuple[int, int]] = []
        for start, end in ranges:
            if not merged or start > merged[-1][1] + 1:
                merged.append((start, end))
            else:
                merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        
        # Extract snippets up to max_total_lines
        snippets = []
        total_lines = 0
        
        for start, end in merged:
            snippet_lines = lines[start - 1:end]
            if not snippet_lines:
                continue
            
            snippet_len = len(snippet_lines)
            if total_lines + snippet_len > max_total_lines:
                remaining = max_total_lines - total_lines
                if remaining <= 0:
                    break
                snippet_lines = snippet_lines[:remaining]
            
            snippets.append("\n".join(snippet_lines))
            total_lines += len(snippet_lines)
            
            if total_lines >= max_total_lines:
                break
        
        return snippets
