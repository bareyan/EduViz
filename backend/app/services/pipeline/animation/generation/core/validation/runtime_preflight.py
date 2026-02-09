"""Runtime preflight checks for Manim code.

This module performs lightweight AST checks before invoking Manim. The goal is
to catch common runtime and severe visual failures early with precise line
numbers and actionable fix hints.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set, Tuple

from .models import (
    IssueCategory,
    IssueConfidence,
    IssueSeverity,
    ValidationIssue,
)
from ..latex_rendering import suggest_latex_rendering


@dataclass(frozen=True)
class _MathTableShape:
    """Known shape metadata for a MathTable variable."""

    row_count: Optional[int]
    col_count: Optional[int]
    has_row_labels: bool
    has_col_labels: bool
    include_outer_lines: bool

    @property
    def max_row_index(self) -> Optional[int]:
        """1-based max row index for get_cell((row, col))."""
        if self.row_count is None:
            return None
        return self.row_count + (1 if self.has_col_labels else 0)

    @property
    def max_col_index(self) -> Optional[int]:
        """1-based max col index for get_cell((row, col))."""
        if self.col_count is None:
            return None
        return self.col_count + (1 if self.has_row_labels else 0)


class RuntimePreflightChecker:
    """AST-based preflight validator for high-risk Manim patterns."""

    def check(self, code: str) -> List[ValidationIssue]:
        try:
            tree = ast.parse(code)
        except SyntaxError:
            # Static validator handles syntax errors.
            return []

        visitor = _RuntimePreflightVisitor(code)
        visitor.visit(tree)
        return visitor.issues


class _RuntimePreflightVisitor(ast.NodeVisitor):
    """Collect preflight issues with best-effort line numbers."""

    def __init__(self, code: str) -> None:
        self._code = code
        self._issues: List[ValidationIssue] = []
        self._dedupe: Set[Tuple[str, int, str]] = set()
        self._math_tables: Dict[str, _MathTableShape] = {}
        self._data_shapes: Dict[str, Tuple[int, int]] = {}

    @property
    def issues(self) -> List[ValidationIssue]:
        return self._issues

    def visit_Assign(self, node: ast.Assign) -> None:
        literal_shape = self._extract_matrix_shape_from_node(node.value)
        if literal_shape:
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self._data_shapes[target.id] = literal_shape

        call = node.value if isinstance(node.value, ast.Call) else None
        if call and self._call_name(call.func) == "MathTable":
            shape = self._extract_math_table_shape(call)
            if shape:
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        self._math_tables[target.id] = shape
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr == "grid_lines":
            self._add_issue(
                severity=IssueSeverity.CRITICAL,
                confidence=IssueConfidence.HIGH,
                category=IssueCategory.RUNTIME,
                message="MathTable has no attribute 'grid_lines'; use get_grid_lines() or get_horizontal_lines()/get_vertical_lines().",
                line=node.lineno,
                fix_hint="Replace '.grid_lines' with supported Table/MathTable accessors.",
            )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        call_name = self._call_name(node.func)
        if call_name in {"Text", "Tex"}:
            self._check_latex_rendering_constructor(node, call_name)

        if isinstance(node.func, ast.Attribute):
            attr = node.func.attr
            table_var = self._resolve_name(node.func.value)
            if attr in {"get_grid_lines", "get_horizontal_lines", "get_vertical_lines"} and table_var:
                self._check_duplicate_grid_lines(node, table_var, attr)
            elif attr == "get_cell" and table_var:
                self._check_get_cell_bounds(node, table_var)
            elif attr in {"wait", "_monitored_wait"}:
                self._check_negative_wait(node)
        self.generic_visit(node)

    def visit_Subscript(self, node: ast.Subscript) -> None:
        call_info = self._extract_get_rows_columns_index(node)
        if call_info:
            table_var, accessor, idx = call_info
            self._check_rows_columns_first_index(
                line=node.lineno,
                table_var=table_var,
                accessor=accessor,
                index=idx,
            )

        nested_info = self._extract_nested_rows_columns_index(node)
        if nested_info:
            table_var, accessor, first_idx, second_idx = nested_info
            self._check_rows_columns_nested_index(
                line=node.lineno,
                table_var=table_var,
                accessor=accessor,
                first_index=first_idx,
                second_index=second_idx,
            )
        self.generic_visit(node)

    @staticmethod
    def _call_name(func: ast.AST) -> Optional[str]:
        if isinstance(func, ast.Name):
            return func.id
        if isinstance(func, ast.Attribute):
            return func.attr
        return None

    @staticmethod
    def _resolve_name(node: ast.AST) -> Optional[str]:
        if isinstance(node, ast.Name):
            return node.id
        return None

    @staticmethod
    def _is_truthy_literal(node: ast.AST) -> bool:
        if isinstance(node, ast.Constant):
            return bool(node.value)
        return False

    @staticmethod
    def _extract_literal_int(node: ast.AST) -> Optional[int]:
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return node.value
        if (
            isinstance(node, ast.UnaryOp)
            and isinstance(node.op, ast.USub)
            and isinstance(node.operand, ast.Constant)
            and isinstance(node.operand.value, int)
        ):
            return -node.operand.value
        return None

    @staticmethod
    def _extract_literal_number(node: ast.AST) -> Optional[float]:
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if (
            isinstance(node, ast.UnaryOp)
            and isinstance(node.op, ast.USub)
            and isinstance(node.operand, ast.Constant)
            and isinstance(node.operand.value, (int, float))
        ):
            return -float(node.operand.value)
        if isinstance(node, ast.BinOp):
            left = _RuntimePreflightVisitor._extract_literal_number(node.left)
            right = _RuntimePreflightVisitor._extract_literal_number(node.right)
            if left is None or right is None:
                return None
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div) and right != 0:
                return left / right
        return None

    @staticmethod
    def _extract_literal_string(node: ast.AST) -> Optional[str]:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        return None

    def _extract_math_table_shape(self, call: ast.Call) -> Optional[_MathTableShape]:
        row_count: Optional[int] = None
        col_count: Optional[int] = None
        if call.args:
            data_arg = call.args[0]
            literal_shape = self._extract_matrix_shape_from_node(data_arg)
            if literal_shape:
                row_count, col_count = literal_shape
            elif isinstance(data_arg, ast.Name):
                resolved = self._data_shapes.get(data_arg.id)
                if resolved:
                    row_count, col_count = resolved

        has_row_labels = False
        has_col_labels = False
        include_outer_lines = False
        for kw in call.keywords:
            if kw.arg == "row_labels" and not (
                isinstance(kw.value, ast.Constant) and kw.value.value is None
            ):
                has_row_labels = True
            if kw.arg == "col_labels" and not (
                isinstance(kw.value, ast.Constant) and kw.value.value is None
            ):
                has_col_labels = True
            if kw.arg == "include_outer_lines":
                include_outer_lines = self._is_truthy_literal(kw.value)

        return _MathTableShape(
            row_count=row_count,
            col_count=col_count,
            has_row_labels=has_row_labels,
            has_col_labels=has_col_labels,
            include_outer_lines=include_outer_lines,
        )

    @staticmethod
    def _extract_matrix_shape_from_node(node: ast.AST) -> Optional[Tuple[int, int]]:
        if not isinstance(node, (ast.List, ast.Tuple)):
            return None

        row_count = len(node.elts)
        if row_count == 0:
            return None

        col_lengths: List[int] = []
        for row in node.elts:
            if isinstance(row, (ast.List, ast.Tuple)):
                col_lengths.append(len(row.elts))
        if not col_lengths:
            return None
        return row_count, max(col_lengths)

    def _extract_get_rows_columns_index(
        self, node: ast.Subscript
    ) -> Optional[Tuple[str, str, int]]:
        call = node.value
        if not isinstance(call, ast.Call):
            return None
        if not isinstance(call.func, ast.Attribute):
            return None
        if call.func.attr not in {"get_rows", "get_columns"}:
            return None
        table_var = self._resolve_name(call.func.value)
        if not table_var:
            return None
        idx = self._extract_literal_int(node.slice)
        if idx is None:
            return None
        return table_var, call.func.attr, idx

    def _extract_nested_rows_columns_index(
        self, node: ast.Subscript
    ) -> Optional[Tuple[str, str, int, int]]:
        inner = node.value
        if not isinstance(inner, ast.Subscript):
            return None
        first = self._extract_get_rows_columns_index(inner)
        if not first:
            return None
        second_idx = self._extract_literal_int(node.slice)
        if second_idx is None:
            return None
        table_var, accessor, first_idx = first
        return table_var, accessor, first_idx, second_idx

    def _check_duplicate_grid_lines(self, node: ast.Call, table_var: str, helper_name: str) -> None:
        shape = self._math_tables.get(table_var)
        if not shape or not shape.include_outer_lines:
            return
        self._add_issue(
            severity=IssueSeverity.CRITICAL,
            confidence=IssueConfidence.HIGH,
            category=IssueCategory.VISUAL_QUALITY,
            message=(
                f"{table_var}.{helper_name}() used with include_outer_lines=True; this often duplicates lines and creates visual artifacts."
            ),
            line=node.lineno,
            fix_hint=(
                "Use either include_outer_lines=True alone, or manual line drawing, not both."
            ),
            auto_fixable=True,
            details={"reason": "duplicate_grid_lines", "table_var": table_var},
        )

    def _check_get_cell_bounds(self, node: ast.Call, table_var: str) -> None:
        shape = self._math_tables.get(table_var)
        if not shape or not node.args:
            return
        arg = node.args[0]
        if not isinstance(arg, (ast.Tuple, ast.List)) or len(arg.elts) != 2:
            return
        row_idx = self._extract_literal_int(arg.elts[0])
        col_idx = self._extract_literal_int(arg.elts[1])
        if row_idx is None or col_idx is None:
            return

        if row_idx < 1 or col_idx < 1:
            self._add_issue(
                severity=IssueSeverity.CRITICAL,
                confidence=IssueConfidence.HIGH,
                category=IssueCategory.RUNTIME,
                message=f"{table_var}.get_cell(({row_idx}, {col_idx})) uses non-positive 1-based index.",
                line=node.lineno,
                fix_hint="Use 1-based positive indices for get_cell((row, col)).",
            )
            return

        max_row = shape.max_row_index
        max_col = shape.max_col_index
        if max_row is None or max_col is None:
            return

        if row_idx > max_row or col_idx > max_col:
            self._add_issue(
                severity=IssueSeverity.CRITICAL,
                confidence=IssueConfidence.HIGH,
                category=IssueCategory.RUNTIME,
                message=(
                    f"{table_var}.get_cell(({row_idx}, {col_idx})) exceeds table bounds "
                    f"(max row={max_row}, max col={max_col})."
                ),
                line=node.lineno,
                fix_hint="Recompute table dimensions and update get_cell indices.",
            )

    def _check_rows_columns_first_index(
        self,
        line: int,
        table_var: str,
        accessor: str,
        index: int,
    ) -> None:
        if index < 0:
            return
        shape = self._math_tables.get(table_var)
        if not shape:
            return
        limit = shape.max_row_index if accessor == "get_rows" else shape.max_col_index
        if limit is None:
            return
        if index >= limit:
            self._add_issue(
                severity=IssueSeverity.CRITICAL,
                confidence=IssueConfidence.HIGH,
                category=IssueCategory.RUNTIME,
                message=(
                    f"{table_var}.{accessor}()[{index}] is out of range "
                    f"(size={limit})."
                ),
                line=line,
                fix_hint=f"Use {table_var}.{accessor}() index < {limit}.",
            )

    def _check_rows_columns_nested_index(
        self,
        line: int,
        table_var: str,
        accessor: str,
        first_index: int,
        second_index: int,
    ) -> None:
        if first_index < 0 or second_index < 0:
            return
        shape = self._math_tables.get(table_var)
        if not shape:
            return

        first_limit = shape.max_row_index if accessor == "get_rows" else shape.max_col_index
        second_limit = shape.max_col_index if accessor == "get_rows" else shape.max_row_index
        if first_limit is None or second_limit is None:
            return

        if first_index >= first_limit:
            self._add_issue(
                severity=IssueSeverity.CRITICAL,
                confidence=IssueConfidence.HIGH,
                category=IssueCategory.RUNTIME,
                message=(
                    f"{table_var}.{accessor}()[{first_index}][{second_index}] first index is out of range "
                    f"(size={first_limit})."
                ),
                line=line,
                fix_hint=f"Use first index < {first_limit}.",
            )
            return

        if second_index >= second_limit:
            self._add_issue(
                severity=IssueSeverity.CRITICAL,
                confidence=IssueConfidence.HIGH,
                category=IssueCategory.RUNTIME,
                message=(
                    f"{table_var}.{accessor}()[{first_index}][{second_index}] second index is out of range "
                    f"(size={second_limit})."
                ),
                line=line,
                fix_hint=f"Use second index < {second_limit}.",
            )

    def _check_negative_wait(self, node: ast.Call) -> None:
        if not node.args:
            return
        wait_time = self._extract_literal_number(node.args[0])
        if wait_time is None:
            return
        if wait_time < 0:
            self._add_issue(
                severity=IssueSeverity.CRITICAL,
                confidence=IssueConfidence.HIGH,
                category=IssueCategory.RUNTIME,
                message=f"self.wait(...) resolves to negative duration ({wait_time:.3f}).",
                line=node.lineno,
                fix_hint="Clamp waits with max(0.01, duration_expr) before calling wait().",
            )

    def _check_latex_rendering_constructor(self, node: ast.Call, constructor: str) -> None:
        if not node.args:
            return
        literal = self._extract_literal_string(node.args[0])
        if literal is None:
            return

        suggestion = suggest_latex_rendering(constructor, literal)
        if not suggestion:
            return

        self._add_issue(
            severity=IssueSeverity.CRITICAL,
            confidence=IssueConfidence.HIGH,
            category=IssueCategory.VISUAL_QUALITY,
            message=(
                f"{constructor}(...) likely contains LaTeX math. "
                f"Use {suggestion.target_constructor}(...) for correct rendering."
            ),
            line=node.lineno,
            fix_hint=(
                f"Convert {constructor} to {suggestion.target_constructor} "
                "for this literal."
            ),
            auto_fixable=True,
            details={
                "reason": "latex_rendering",
                "constructor": constructor,
                "target_constructor": suggestion.target_constructor,
                "text": literal,
                "normalized_text": suggestion.normalized_text,
            },
        )

    def _add_issue(
        self,
        *,
        severity: IssueSeverity,
        confidence: IssueConfidence,
        category: IssueCategory,
        message: str,
        line: int,
        fix_hint: str,
        auto_fixable: bool = False,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        key = (category.value, line, message)
        if key in self._dedupe:
            return
        self._dedupe.add(key)
        issue = ValidationIssue(
            severity=severity,
            confidence=confidence,
            category=category,
            message=message,
            auto_fixable=auto_fixable,
            line=line,
            fix_hint=fix_hint,
            details=dict(details or {}),
        )
        self._issues.append(issue)
