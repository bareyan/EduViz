"""
Deterministic Fixer

Applies code-level fixes for spatial issues WITHOUT calling an LLM.

Handles high-confidence, auto-fixable issues via:
1. Regex-based pattern matching for positioning calls
2. Coordinate clamping for out-of-bounds objects
3. Smart spacing insertion for text overlaps
4. Known bad-pattern replacement (self.wait(0), tracker.number, etc.)

Architecture:
    Each fix type has a dedicated method.  The public ``fix()`` method
    iterates over auto-fixable issues and dispatches to the appropriate
    handler.  Issues that can't be fixed deterministically are returned
    as ``remaining`` for potential LLM escalation.
"""

import re
from typing import List, Optional, Tuple

from app.core import get_logger
from ...config import SAFE_X_LIMIT, SAFE_Y_LIMIT
from ..core.validation.models import (
    IssueCategory,
    ValidationIssue,
)

logger = get_logger(__name__, component="deterministic_fixer")

# ── Known bad patterns that can be fixed with simple regex ───────────────────
_KNOWN_PATTERNS: List[Tuple[re.Pattern, str, str]] = [
    # self.wait(0) or self._monitored_wait(0) → remove the line
    (re.compile(r"^(\s*)self\.(?:_monitored_)?wait\(\s*0(?:\.0*)?\s*\)\s*$", re.MULTILINE), "", "Remove self.wait(0)"),
    # tracker.number → tracker.get_value()
    (
        re.compile(r"(\w+)\.number\b(?!\s*=)"),
        r"\1.get_value()",
        "Fix tracker.number → get_value()",
    ),
    # ease_in_expo → smooth
    (re.compile(r"\bease_in_expo\b"), "smooth", "Fix invalid rate_func ease_in_expo"),
    # CENTER → ORIGIN
    (re.compile(r"\bCENTER\b"), "ORIGIN", "Fix CENTER → ORIGIN"),
    # TOP → UP
    (re.compile(r"\bTOP\b(?!\s*=)"), "UP", "Fix TOP → UP"),
    # BOTTOM → DOWN
    (re.compile(r"\bBOTTOM\b(?!\s*=)"), "DOWN", "Fix BOTTOM → DOWN"),
]


class DeterministicFixer:
    """
    Fixes spatial/pattern issues deterministically (no LLM required).

    Token savings: every issue resolved here avoids a full LLM round-trip
    (typically ~$0.02–0.05 per call and 5–30 seconds latency).
    """

    def fix(
        self,
        code: str,
        issues: List[ValidationIssue],
    ) -> Tuple[str, List[ValidationIssue], int]:
        """Apply deterministic fixes for auto-fixable issues.

        Args:
            code: Current Manim source code.
            issues: List of ValidationIssues from spatial/runtime validation.

        Returns:
            Tuple of (fixed_code, remaining_issues, fixes_applied).
        """
        remaining: List[ValidationIssue] = []
        fixes_applied = 0

        for issue in issues:
            if not issue.should_auto_fix:
                remaining.append(issue)
                continue

            new_code = self._dispatch_fix(code, issue)
            if new_code is not None and new_code != code:
                code = new_code
                fixes_applied += 1
                logger.info(
                    f"🔧 Deterministic fix applied: {issue.category.value} — "
                    f"{issue.message[:80]}"
                )
            else:
                remaining.append(issue)

        return code, remaining, fixes_applied

    def fix_known_patterns(self, code: str) -> Tuple[str, int]:
        """Apply known bad-pattern regex fixes (no issue objects needed).

        Returns:
            Tuple of (fixed_code, number_of_fixes_applied).
        """
        total_fixes = 0
        for pattern, replacement, description in _KNOWN_PATTERNS:
            new_code, count = pattern.subn(replacement, code)
            if count > 0:
                code = new_code
                total_fixes += count
                logger.info(
                    f"🔧 Pattern fix ({count}x): {description}"
                )
        return code, total_fixes

    # ── Dispatch ─────────────────────────────────────────────────────────

    def _dispatch_fix(
        self, code: str, issue: ValidationIssue
    ) -> Optional[str]:
        """Route an issue to the appropriate fix handler."""
        handlers = {
            IssueCategory.OUT_OF_BOUNDS: self._fix_out_of_bounds,
            IssueCategory.TEXT_OVERLAP: self._fix_text_overlap,
        }
        handler = handlers.get(issue.category)
        if handler is None:
            return None
        return handler(code, issue)

    # ── Out-of-bounds fix ────────────────────────────────────────────────

    def _fix_out_of_bounds(
        self, code: str, issue: ValidationIssue
    ) -> Optional[str]:
        """Clamp coordinates or insert scaling for out-of-bounds objects.

        Strategy (ordered by reliability):
        1. Find move_to/shift with numeric coordinates near the reported
           position and clamp them inside the safe zone.
        2. If no positioning call is found, try inserting a .scale() call
           after the object's creation.
        """
        details = issue.details
        center_x = details.get("center_x")
        center_y = details.get("center_y")

        if center_x is None or center_y is None:
            return None

        # Strategy 1: Clamp numeric coordinates in move_to / shift
        result = self._clamp_coordinates(code)
        if result is not None:
            return result

        # Strategy 2: Try inserting .scale() for objects that are too large
        obj_type = details.get("object_type", "")
        width = details.get("width", 0)
        height = details.get("height", 0)
        if width > SAFE_X_LIMIT * 2 or height > SAFE_Y_LIMIT * 2:
            return self._insert_scale_for_type(code, obj_type)

        return None

    def _clamp_coordinates(self, code: str) -> Optional[str]:
        """Find and clamp coordinate values near the reported position."""
        # Match patterns like: .move_to(RIGHT * 8) or .move_to(np.array([8, 0, 0]))
        # or .move_to([8, 0, 0]) or .shift(RIGHT * 8)

        # Pattern 1: Direction * scalar  (e.g., RIGHT * 8.5)
        dir_pattern = re.compile(
            r"(\.(?:move_to|shift)\s*\(\s*)"
            r"((?:RIGHT|LEFT|UP|DOWN|UL|UR|DL|DR)\s*\*\s*)"
            r"([\d.]+)"
            r"(\s*\))",
        )

        def _clamp_direction(m: re.Match) -> str:
            prefix = m.group(1)
            direction_part = m.group(2)
            val = float(m.group(3))
            suffix = m.group(4)

            # Determine which axis
            dir_text = direction_part.split("*")[0].strip()
            if dir_text in ("RIGHT", "LEFT"):
                clamped = min(val, SAFE_X_LIMIT)
            elif dir_text in ("UP", "DOWN"):
                clamped = min(val, SAFE_Y_LIMIT)
            else:
                clamped = min(val, min(SAFE_X_LIMIT, SAFE_Y_LIMIT))

            if abs(clamped - val) < 0.01:
                return m.group(0)  # No change needed
            return f"{prefix}{direction_part}{clamped:.1f}{suffix}"

        new_code = dir_pattern.sub(_clamp_direction, code)
        if new_code != code:
            return new_code

        # Pattern 2: Explicit array coordinates [x, y, z] or np.array([x, y, z])
        array_pattern = re.compile(
            r"(\.(?:move_to|shift)\s*\(\s*(?:np\.array\s*\(\s*)?\[)"
            r"\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*"
            r"(\](?:\s*\))?\s*\))",
        )

        def _clamp_array(m: re.Match) -> str:
            prefix = m.group(1)
            x, y, z = float(m.group(2)), float(m.group(3)), float(m.group(4))
            suffix = m.group(5)

            cx = max(-SAFE_X_LIMIT, min(SAFE_X_LIMIT, x))
            cy = max(-SAFE_Y_LIMIT, min(SAFE_Y_LIMIT, y))

            if abs(cx - x) < 0.01 and abs(cy - y) < 0.01:
                return m.group(0)
            return f"{prefix}{cx:.1f}, {cy:.1f}, {z:.1f}{suffix}"

        new_code = array_pattern.sub(_clamp_array, code)
        if new_code != code:
            return new_code

        return None

    @staticmethod
    def _insert_scale_for_type(code: str, obj_type: str) -> Optional[str]:
        """Insert a .scale() call after the creation of objects of this type."""
        if not obj_type:
            return None

        # Find pattern: variable = ObjType(...)
        pattern = re.compile(
            rf"^(\s*)(\w+)\s*=\s*{re.escape(obj_type)}\(([^)]*)\)\s*$",
            re.MULTILINE,
        )

        match = pattern.search(code)
        if match:
            indent = match.group(1)
            var_name = match.group(2)
            # Insert .scale() on the next line
            insert = f"\n{indent}{var_name}.scale_to_fit_width(11)  # auto-fix: fit within bounds"
            return code[: match.end()] + insert + code[match.end() :]

        return None

    # ── Text overlap fix ─────────────────────────────────────────────────

    def _fix_text_overlap(
        self, code: str, issue: ValidationIssue
    ) -> Optional[str]:
        """Separate overlapping texts by inserting spatial offsets.

        Strategy:
        1. Find the two text objects by their content strings.
        2. If both have the same or similar positioning, modify the second
           to use .next_to() relative to the first, or add .shift().
        """
        details = issue.details
        text1 = details.get("text1", "")
        text2 = details.get("text2", "")

        if not text1 or not text2:
            return None

        # Find variable names for both texts
        var1 = self._find_text_variable(code, text1)
        var2 = self._find_text_variable(code, text2)

        if not var2:
            return None  # Can't determine which variable to fix

        # Strategy 1: If we know both vars, use .next_to()
        if var1:
            return self._add_next_to(code, var2, var1)

        # Strategy 2: Add a .shift(DOWN * 0.8) to the second text
        return self._add_shift(code, var2, "DOWN", 0.8)

    @staticmethod
    def _find_text_variable(code: str, text_content: str) -> Optional[str]:
        """Find the variable name assigned to a Text with given content."""
        # Escape regex-special characters in the text content
        escaped = re.escape(text_content[:40])  # Truncate for matching
        pattern = re.compile(
            rf'^(\s*)(\w+)\s*=\s*(?:Text|Tex|MathTex)\s*\(\s*["\'].*{escaped}',
            re.MULTILINE,
        )
        match = pattern.search(code)
        return match.group(2) if match else None

    @staticmethod
    def _add_next_to(code: str, target_var: str, anchor_var: str) -> Optional[str]:
        """Add .next_to(anchor, DOWN, buff=0.4) after the target's creation."""
        # Find the line where target_var is created
        pattern = re.compile(
            rf"^(\s*){re.escape(target_var)}\s*=\s*\w+\(.*$",
            re.MULTILINE,
        )
        match = pattern.search(code)
        if not match:
            return None

        indent = match.group(1)
        insert_line = (
            f"\n{indent}{target_var}.next_to("
            f"{anchor_var}, DOWN, buff=0.4)"
            f"  # auto-fix: prevent overlap"
        )
        return code[: match.end()] + insert_line + code[match.end() :]

    @staticmethod
    def _add_shift(
        code: str, target_var: str, direction: str, amount: float
    ) -> Optional[str]:
        """Add .shift(direction * amount) after the target's creation."""
        pattern = re.compile(
            rf"^(\s*){re.escape(target_var)}\s*=\s*\w+\(.*$",
            re.MULTILINE,
        )
        match = pattern.search(code)
        if not match:
            return None

        indent = match.group(1)
        insert_line = (
            f"\n{indent}{target_var}.shift("
            f"{direction} * {amount})"
            f"  # auto-fix: prevent overlap"
        )
        return code[: match.end()] + insert_line + code[match.end() :]
