"""Generic known-pattern sanitizer for deterministic code cleanup.

This module owns simple regex replacement rules that are not tied to any
specific visual domain (table, chart, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import List, Pattern, Tuple


@dataclass(frozen=True)
class RegexReplacementRule:
    """Single regex replacement rule."""

    pattern: Pattern[str]
    replacement: str
    description: str

    def apply(self, code: str) -> Tuple[str, int]:
        return self.pattern.subn(self.replacement, code)


class KnownPatternSanitizer:
    """Applies stable, generic regex rewrites to generated Manim code."""

    _RULES: List[RegexReplacementRule] = [
        RegexReplacementRule(
            pattern=re.compile(
                r"^(\s*)self\.(?:_monitored_)?wait\(\s*0(?:\.0*)?\s*\)\s*$",
                re.MULTILINE,
            ),
            replacement="",
            description="Remove self.wait(0)",
        ),
        RegexReplacementRule(
            pattern=re.compile(r"(\w+)\.number\b(?!\s*=)"),
            replacement=r"\1.get_value()",
            description="Fix tracker.number -> get_value()",
        ),
        RegexReplacementRule(
            pattern=re.compile(r"\bease_in_expo\b"),
            replacement="smooth",
            description="Fix invalid rate_func ease_in_expo",
        ),
        RegexReplacementRule(
            pattern=re.compile(r"\bCENTER\b"),
            replacement="ORIGIN",
            description="Fix CENTER -> ORIGIN",
        ),
        RegexReplacementRule(
            pattern=re.compile(r"\bTOP\b(?!\s*=)"),
            replacement="UP",
            description="Fix TOP -> UP",
        ),
        RegexReplacementRule(
            pattern=re.compile(r"\bBOTTOM\b(?!\s*=)"),
            replacement="DOWN",
            description="Fix BOTTOM -> DOWN",
        ),
    ]

    def apply(self, code: str) -> Tuple[str, List[Tuple[str, int]]]:
        """Run all generic rules.

        Returns:
            (updated_code, [(description, count), ...] for rules that fired)
        """
        changes: List[Tuple[str, int]] = []
        for rule in self._RULES:
            code, count = rule.apply(code)
            if count > 0:
                changes.append((rule.description, count))
        return code, changes

