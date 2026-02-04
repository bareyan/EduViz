"""
Fixer Context Manager

Responsible for preparing the code context for the fixer agent.
Handles slicing, windowing, and snippet extraction around failures.
"""

import re
from typing import List, Optional, Tuple

from ...config import (
    HEAD_TAIL_LINES,
    MAX_PROMPT_CODE_CHARS,
    SNIPPET_CONTEXT_RADIUS,
    SNIPPET_MAX_LINES,
)
from ...prompts.fixer_prompts import CODE_CONTEXT_NOTE, CODE_TRUNCATION_NOTE


class FixerContextManager:
    """Manages code context extraction and windowing."""

    def select_context(self, code: str, errors: str) -> Tuple[str, Optional[str]]:
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
                return "\n\n".join(snippets), CODE_CONTEXT_NOTE
        
        # Fallback: head + tail
        lines = code.splitlines()
        if not lines:
            return code, None
        
        head = "\n".join(lines[:HEAD_TAIL_LINES])
        tail = "\n".join(lines[-HEAD_TAIL_LINES:]) if len(lines) > HEAD_TAIL_LINES else ""
        
        trimmed = head if not tail else f"{head}\n\n# ...snip...\n\n{tail}"
        
        return trimmed, CODE_TRUNCATION_NOTE
    
    def _extract_error_line_numbers(self, errors: str) -> List[int]:
        """Extract line numbers from error messages.
        
        Args:
            errors: Error messages
            
        Returns:
            Sorted list of unique line numbers
        """
        line_nums = []
        # Matches "Line 123" or "line 123"
        for match in re.finditer(r"\b[Ll]ine\s+(\d+)\b", errors):
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
