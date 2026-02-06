"""Deterministic fixer orchestrator.

Design:
- SRP: this class only orchestrates deterministic fix strategies.
- DRY: reusable pattern rewrites are delegated to dedicated sanitizer modules.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

from app.core import get_logger

from ...config import SAFE_X_LIMIT, SAFE_Y_LIMIT
from ..core.validation.models import IssueCategory, ValidationIssue
from .known_pattern_sanitizer import KnownPatternSanitizer
from .table_pattern_sanitizer import TablePatternSanitizer

logger = get_logger(__name__, component="deterministic_fixer")


class DeterministicFixer:
    """Fixes auto-fixable issues without LLM calls."""

    def __init__(self) -> None:
        self._known_patterns = KnownPatternSanitizer()
        self._table_patterns = TablePatternSanitizer()

    def fix(
        self,
        code: str,
        issues: List[ValidationIssue],
    ) -> Tuple[str, List[ValidationIssue], int]:
        """Apply deterministic fixes for auto-fixable validation issues."""
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
                    f"Deterministic fix applied: {issue.category.value} - "
                    f"{issue.message[:80]}"
                )
            else:
                remaining.append(issue)

        return code, remaining, fixes_applied

    def fix_known_patterns(self, code: str) -> Tuple[str, int]:
        """Apply generic and table-specific deterministic pattern rewrites."""
        total_fixes = 0

        code, generic_changes = self._known_patterns.apply(code)
        for description, count in generic_changes:
            total_fixes += count
            logger.info(f"Pattern fix ({count}x): {description}")

        code, table_changes = self._table_patterns.apply(code)
        for description, count in table_changes:
            total_fixes += count
            logger.info(f"Pattern fix ({count}x): {description}")

        return code, total_fixes

    def _dispatch_fix(self, code: str, issue: ValidationIssue) -> Optional[str]:
        """Route issue to category-specific deterministic handler."""
        handlers = {
            IssueCategory.OUT_OF_BOUNDS: self._fix_out_of_bounds,
            IssueCategory.TEXT_OVERLAP: self._fix_text_overlap,
            IssueCategory.OBJECT_OCCLUSION: self._fix_object_occlusion,
        }
        handler = handlers.get(issue.category)
        if handler is None:
            return None
        return handler(code, issue)

    def _fix_out_of_bounds(self, code: str, issue: ValidationIssue) -> Optional[str]:
        """Clamp coordinates or add scaling to bring objects back in bounds."""
        details = issue.details
        center_x = details.get("center_x")
        center_y = details.get("center_y")

        if details.get("is_group_overflow"):
            obj_type = details.get("object_type", "")
            result = self._insert_scale_for_type(code, obj_type)
            if result is not None:
                return result

        if center_x is None or center_y is None:
            return None

        result = self._clamp_coordinates(code)
        if result is not None:
            return result

        obj_type = details.get("object_type", "")
        width = details.get("width", 0)
        height = details.get("height", 0)
        if width > SAFE_X_LIMIT * 2 or height > SAFE_Y_LIMIT * 2:
            return self._insert_scale_for_type(code, obj_type)

        return None

    def _clamp_coordinates(self, code: str) -> Optional[str]:
        """Clamp numeric coordinate values in move/shift calls."""
        dir_pattern = re.compile(
            r"(\.(?:move_to|shift)\s*\(\s*)"
            r"((?:RIGHT|LEFT|UP|DOWN|UL|UR|DL|DR)\s*\*\s*)"
            r"([\d.]+)"
            r"(\s*\))",
        )

        def _clamp_direction(match: re.Match) -> str:
            prefix = match.group(1)
            direction_part = match.group(2)
            val = float(match.group(3))
            suffix = match.group(4)

            direction = direction_part.split("*")[0].strip()
            if direction in ("RIGHT", "LEFT"):
                clamped = min(val, SAFE_X_LIMIT)
            elif direction in ("UP", "DOWN"):
                clamped = min(val, SAFE_Y_LIMIT)
            else:
                clamped = min(val, min(SAFE_X_LIMIT, SAFE_Y_LIMIT))

            if abs(clamped - val) < 0.01:
                return match.group(0)
            return f"{prefix}{direction_part}{clamped:.1f}{suffix}"

        new_code = dir_pattern.sub(_clamp_direction, code)
        if new_code != code:
            return new_code

        array_pattern = re.compile(
            r"(\.(?:move_to|shift)\s*\(\s*(?:np\.array\s*\(\s*)?\[)"
            r"\s*([-\d.]+)\s*,\s*([-\d.]+)\s*,\s*([-\d.]+)\s*"
            r"(\](?:\s*\))?\s*\))",
        )

        def _clamp_array(match: re.Match) -> str:
            prefix = match.group(1)
            x, y, z = float(match.group(2)), float(match.group(3)), float(match.group(4))
            suffix = match.group(5)

            cx = max(-SAFE_X_LIMIT, min(SAFE_X_LIMIT, x))
            cy = max(-SAFE_Y_LIMIT, min(SAFE_Y_LIMIT, y))

            if abs(cx - x) < 0.01 and abs(cy - y) < 0.01:
                return match.group(0)
            return f"{prefix}{cx:.1f}, {cy:.1f}, {z:.1f}{suffix}"

        new_code = array_pattern.sub(_clamp_array, code)
        if new_code != code:
            return new_code
        return None

    @staticmethod
    def _insert_scale_for_type(code: str, obj_type: str) -> Optional[str]:
        """Insert scale_to_fit_width call after object creation."""
        if not obj_type:
            return None

        type_variants = [obj_type]
        if "Table" in obj_type:
            type_variants.extend(["Table", "MobjectTable", "IntegerTable", "DecimalTable", "MathTable"])
        if obj_type in ("VGroup", "Group"):
            type_variants.extend(["VGroup", "Group"])

        seen = set()
        unique_types = []
        for candidate in type_variants:
            if candidate not in seen:
                seen.add(candidate)
                unique_types.append(candidate)

        for variant in unique_types:
            pattern = re.compile(
                rf"^(\s*)(\w+)\s*=\s*{re.escape(variant)}\(([^)]*)\)\s*$",
                re.MULTILINE,
            )
            match = pattern.search(code)
            if not match:
                continue

            indent = match.group(1)
            var_name = match.group(2)
            insert = (
                f"\n{indent}{var_name}.scale_to_fit_width(min({var_name}.width, 12))"
                "  # auto-fix: fit within bounds"
            )
            return code[:match.end()] + insert + code[match.end():]

        return None

    def _fix_object_occlusion(self, code: str, issue: ValidationIssue) -> Optional[str]:
        """Convert likely text-occluding shapes into stroke-only visuals."""
        obj_type = issue.details.get("object_type", "")
        if not obj_type:
            return None

        if "Rectangle" in obj_type or "Square" in obj_type:
            pattern = re.compile(rf"(\w+)\s*=\s*{re.escape(obj_type)}\(([^)]*)\)", re.MULTILINE)
            for match in pattern.finditer(code):
                args = match.group(2)
                if "fill_opacity" in args:
                    continue
                new_args = args.rstrip() + ", fill_opacity=0" if args.strip() else "fill_opacity=0"
                new_call = f"{match.group(1)} = {obj_type}({new_args})"
                return code[:match.start()] + new_call + code[match.end():]

        pattern = re.compile(rf"^(\s*)(\w+)\s*=\s*{re.escape(obj_type)}\(.*$", re.MULTILINE)
        match = pattern.search(code)
        if not match:
            return None

        indent = match.group(1)
        var_name = match.group(2)
        insert = f"\n{indent}{var_name}.set_fill(opacity=0)  # auto-fix: prevent text occlusion"
        return code[:match.end()] + insert + code[match.end():]

    def _fix_text_overlap(self, code: str, issue: ValidationIssue) -> Optional[str]:
        """Separate overlapping text objects with relative placement."""
        text1 = issue.details.get("text1", "")
        text2 = issue.details.get("text2", "")
        if not text1 or not text2:
            return None

        var1 = self._find_text_variable(code, text1)
        var2 = self._find_text_variable(code, text2)
        if not var2:
            return None

        if var1:
            return self._add_next_to(code, var2, var1)
        return self._add_shift(code, var2, "DOWN", 0.8)

    @staticmethod
    def _find_text_variable(code: str, text_content: str) -> Optional[str]:
        escaped = re.escape(text_content[:40])
        pattern = re.compile(
            rf'^(\s*)(\w+)\s*=\s*(?:Text|Tex|MathTex)\s*\(\s*["\'].*{escaped}',
            re.MULTILINE,
        )
        match = pattern.search(code)
        return match.group(2) if match else None

    @staticmethod
    def _add_next_to(code: str, target_var: str, anchor_var: str) -> Optional[str]:
        pattern = re.compile(
            rf"^(\s*){re.escape(target_var)}\s*=\s*\w+\(.*$",
            re.MULTILINE,
        )
        match = pattern.search(code)
        if not match:
            return None

        indent = match.group(1)
        insert = (
            f"\n{indent}{target_var}.next_to({anchor_var}, DOWN, buff=0.4)"
            "  # auto-fix: prevent overlap"
        )
        return code[:match.end()] + insert + code[match.end():]

    @staticmethod
    def _add_shift(code: str, target_var: str, direction: str, amount: float) -> Optional[str]:
        pattern = re.compile(
            rf"^(\s*){re.escape(target_var)}\s*=\s*\w+\(.*$",
            re.MULTILINE,
        )
        match = pattern.search(code)
        if not match:
            return None

        indent = match.group(1)
        insert = (
            f"\n{indent}{target_var}.shift({direction} * {amount})"
            "  # auto-fix: prevent overlap"
        )
        return code[:match.end()] + insert + code[match.end():]

