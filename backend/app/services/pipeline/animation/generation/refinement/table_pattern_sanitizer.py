"""Table-focused deterministic sanitization rules.

This module owns all table-specific rewrites:
- Dense header MathTex normalization
- Legacy table API compatibility fixes
- MathTex array highlight stabilization
- Decorative line overlay cleanup
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple


_HEADER_MATHTEX_ASSIGNMENT = re.compile(
    r"(?ms)^(\s*)([A-Za-z_]\w*)\s*=\s*MathTex\((.*?)\)\s*$"
)
_ARRAY_MATHTEX_ASSIGNMENT = re.compile(
    r"(?ms)^(\s*)([A-Za-z_]\w*)\s*=\s*MathTex\((.*?)\)\s*$"
)
_STRING_LITERAL = re.compile(
    r'(?:r|rf|fr|f)?(?:"[^"\\]*(?:\\.[^"\\]*)*"|\'[^\'\\]*(?:\\.[^\'\\]*)*\')',
    re.DOTALL,
)
_TABLE_GRID_LINES_REF = re.compile(r"\b([A-Za-z_]\w*table\w*|table)\.grid_lines\b")
_TABLE_DOUBLE_INDEX_REF = re.compile(r"\b([A-Za-z_]\w*table\w*|table)\[(\d+)\]\[(\d+)\]")
_TABLE_GROUP_WITH_LINES = re.compile(
    r"(?m)^(\s*)(\w+)\s*=\s*VGroup\(\s*([A-Za-z_]\w*table\w*|table\w*)\s*,\s*([^)]+)\)\s*$"
)


class TablePatternSanitizer:
    """Applies table-specific deterministic rewrites."""

    def apply(self, code: str) -> Tuple[str, List[Tuple[str, int]]]:
        """Run all table sanitizers in stable order."""
        changes: List[Tuple[str, int]] = []

        code, count = self._normalize_dense_header_mathtex(code)
        if count > 0:
            changes.append(("normalize dense header MathTex layout", count))

        code, count = self._fix_table_grid_lines_reference(code)
        if count > 0:
            changes.append(("table.grid_lines -> explicit line groups", count))

        code, count = self._fix_table_double_indexing(code)
        if count > 0:
            changes.append(("table[i][j] -> table.get_cell(i+1, j+1)", count))

        code, count = self._stabilize_mathtex_array_table_highlights(code)
        if count > 0:
            changes.append(("stabilize MathTex array table highlights", count))

        code, count = self._remove_decorative_table_line_groups(code)
        if count > 0:
            changes.append(("remove decorative line overlays on tables", count))

        return code, changes

    @staticmethod
    def _normalize_dense_header_mathtex(code: str) -> Tuple[str, int]:
        matches = list(_HEADER_MATHTEX_ASSIGNMENT.finditer(code))
        if not matches:
            return code, 0

        replacements: List[Tuple[int, int, str]] = []
        fixes = 0
        for match in matches:
            indent = match.group(1)
            var_name = match.group(2)
            body = match.group(3)

            if "header" not in var_name.lower():
                continue
            if "\\begin{" in body or "\\end{" in body:
                continue
            if len(_STRING_LITERAL.findall(body)) < 4:
                continue
            if re.search(rf"(?m)^\s*{re.escape(var_name)}\s*\.arrange\s*\(", code):
                continue

            replacement = (
                f"{match.group(0)}\n"
                f"{indent}{var_name}.arrange(RIGHT, buff=0.7)  # auto-fix: spread header labels\n"
                f"{indent}{var_name}.scale_to_fit_width(min({var_name}.width, 10.5))  # auto-fix: avoid header crowding"
            )
            replacements.append((match.start(), match.end(), replacement))
            fixes += 1

        for start, end, replacement in reversed(replacements):
            code = code[:start] + replacement + code[end:]
        return code, fixes

    @staticmethod
    def _fix_table_grid_lines_reference(code: str) -> Tuple[str, int]:
        replacement = r"VGroup(\1.get_horizontal_lines(), \1.get_vertical_lines())"
        return _TABLE_GRID_LINES_REF.subn(replacement, code)

    @staticmethod
    def _fix_table_double_indexing(code: str) -> Tuple[str, int]:
        def _repl(match: re.Match) -> str:
            table_name = match.group(1)
            row_idx = int(match.group(2)) + 1
            col_idx = int(match.group(3)) + 1
            return f"{table_name}.get_cell({row_idx}, {col_idx})"

        return _TABLE_DOUBLE_INDEX_REF.subn(_repl, code)

    @staticmethod
    def _stabilize_mathtex_array_table_highlights(code: str) -> Tuple[str, int]:
        fixes = 0
        tables: List[Tuple[str, int, int]] = []

        for match in _ARRAY_MATHTEX_ASSIGNMENT.finditer(code):
            table_var = match.group(2)
            cols, rows = TablePatternSanitizer._extract_array_shape(match.group(3))
            if cols >= 2 and rows >= 2:
                tables.append((table_var, cols, rows))

        for table_var, cols, rows in tables:
            col_candidates = re.findall(
                rf"(?m)^\s*(\w*col\w*highlight\w*)\s*=\s*SurroundingRectangle\(\s*{re.escape(table_var)}\b",
                code,
            )
            row_candidates = re.findall(
                rf"(?m)^\s*(\w*row\w*highlight\w*)\s*=\s*SurroundingRectangle\(\s*{re.escape(table_var)}\b",
                code,
            )
            cell_candidates = re.findall(
                r"(?m)^\s*(\w*cell\w*)\s*=\s*SurroundingRectangle\(",
                code,
            )

            col_var = TablePatternSanitizer._pick_preferred_var(col_candidates, "pivot")
            row_var = TablePatternSanitizer._pick_preferred_var(row_candidates, "pivot")
            cell_var = TablePatternSanitizer._pick_preferred_var(cell_candidates, "pivot")

            code, count = TablePatternSanitizer._normalize_table_divisor(
                code=code,
                table_var=table_var,
                axis="width",
                target_divisor=cols,
                var_filter="col",
            )
            fixes += count

            code, count = TablePatternSanitizer._normalize_table_divisor(
                code=code,
                table_var=table_var,
                axis="height",
                target_divisor=rows,
                var_filter="row",
            )
            fixes += count

            if col_var:
                code, count = TablePatternSanitizer._ensure_followup_line(
                    code=code,
                    base_pattern=(
                        rf"(?m)^(\s*){re.escape(col_var)}\.move_to\(\s*{re.escape(table_var)}\.get_left\(\)\s*,\s*"
                        rf"aligned_edge\s*=\s*LEFT\s*\)\.shift\(\s*RIGHT\s*\*\s*[-+]?\d+(?:\.\d+)?\s*\)\s*$"
                    ),
                    followup_template=(
                        "{indent}"
                        f"{col_var}.set_y({table_var}.get_y())"
                        "  # auto-fix: keep column highlight centered"
                    ),
                    dedupe_pattern=(
                        rf"(?m)^\s*{re.escape(col_var)}\.set_y\(\s*{re.escape(table_var)}\.get_y\(\)\s*\)"
                    ),
                )
                fixes += count

            if row_var:
                code, count = TablePatternSanitizer._ensure_followup_line(
                    code=code,
                    base_pattern=(
                        rf"(?m)^(\s*){re.escape(row_var)}\.move_to\(\s*{re.escape(table_var)}\.get_top\(\)\s*,\s*"
                        rf"aligned_edge\s*=\s*UP\s*\)\.shift\(\s*DOWN\s*\*\s*[-+]?\d+(?:\.\d+)?\s*\)\s*$"
                    ),
                    followup_template=(
                        "{indent}"
                        f"{row_var}.set_x({table_var}.get_x())"
                        "  # auto-fix: keep row highlight centered"
                    ),
                    dedupe_pattern=(
                        rf"(?m)^\s*{re.escape(row_var)}\.set_x\(\s*{re.escape(table_var)}\.get_x\(\)\s*\)"
                    ),
                )
                fixes += count

            if cell_var and col_var and row_var:
                move_pattern = re.compile(
                    rf"(?m)^(\s*){re.escape(cell_var)}\.move_to\(\s*{re.escape(col_var)}\.get_center\(\)\s*\)"
                    rf"\.shift\(\s*(?:UP|DOWN)\s*\*\s*[-+]?\d+(?:\.\d+)?\s*\)\s*$"
                )
                match = move_pattern.search(code)
                if match:
                    indent = match.group(1)
                    replacement = (
                        f"{indent}{cell_var}.move_to({col_var}.get_center())\n"
                        f"{indent}{cell_var}.set_y({row_var}.get_y())"
                        "  # auto-fix: align pivot cell to row/column intersection"
                    )
                    code = code[:match.start()] + replacement + code[match.end():]
                    fixes += 1

                if not re.search(rf"(?m)^\s*{re.escape(cell_var)}\.stretch_to_fit_height\(", code):
                    width_line = re.search(
                        rf"(?m)^(\s*){re.escape(cell_var)}\.stretch_to_fit_width\([^\n]*\)\s*$",
                        code,
                    )
                    if width_line:
                        indent = width_line.group(1)
                        insert = (
                            f"\n{indent}{cell_var}.stretch_to_fit_height({table_var}.height / {rows})"
                            "  # auto-fix: match table row height"
                        )
                        code = code[:width_line.end()] + insert + code[width_line.end():]
                        fixes += 1

        return code, fixes

    @staticmethod
    def _extract_array_shape(mathtex_body: str) -> Tuple[int, int]:
        chunks: List[str] = []
        for token in _STRING_LITERAL.findall(mathtex_body):
            literal = re.sub(r"^(?:[rRuUbBfF]{1,2})", "", token, count=1)
            if len(literal) >= 2 and literal[0] == literal[-1] and literal[0] in ("'", '"'):
                literal = literal[1:-1]
            chunks.append(literal)

        joined = "".join(chunks)
        m_spec = re.search(r"\\begin\{array\}\{([^}]*)\}", joined)
        m_content = re.search(r"\\begin\{array\}\{[^}]*\}(.*?)\\end\{array\}", joined, re.DOTALL)
        if not m_spec or not m_content:
            return 0, 0

        cols = len(re.findall(r"[clrm]", m_spec.group(1)))
        if cols <= 0:
            return 0, 0

        rows = len([row for row in re.split(r"\\\\", re.sub(r"\\hline", "", m_content.group(1))) if row.strip()])
        return cols, rows

    @staticmethod
    def _pick_preferred_var(candidates: List[str], preferred_substring: str) -> Optional[str]:
        if not candidates:
            return None
        needle = preferred_substring.lower()
        for candidate in candidates:
            if needle in candidate.lower():
                return candidate
        return candidates[0]

    @staticmethod
    def _normalize_table_divisor(
        code: str,
        table_var: str,
        axis: str,
        target_divisor: int,
        var_filter: str,
    ) -> Tuple[str, int]:
        if axis not in ("width", "height"):
            return code, 0

        method = f"stretch_to_fit_{axis}"
        pattern = re.compile(
            rf"(?m)^(\s*)(\w*{re.escape(var_filter)}\w*highlight\w*)\.{method}\(\s*{re.escape(table_var)}\.{axis}\s*/\s*([-+]?\d+(?:\.\d+)?)\s*\)\s*$"
        )
        replacements: List[Tuple[int, int, str]] = []
        count = 0

        for match in pattern.finditer(code):
            indent = match.group(1)
            var_name = match.group(2)
            current = float(match.group(3))
            if abs(current - float(target_divisor)) < 1e-6:
                continue
            replacement = (
                f"{indent}{var_name}.{method}({table_var}.{axis} / {target_divisor})"
                f"  # auto-fix: match table {axis} cells"
            )
            replacements.append((match.start(), match.end(), replacement))
            count += 1

        for start, end, replacement in reversed(replacements):
            code = code[:start] + replacement + code[end:]
        return code, count

    @staticmethod
    def _ensure_followup_line(
        code: str,
        base_pattern: str,
        followup_template: str,
        dedupe_pattern: str,
    ) -> Tuple[str, int]:
        if re.search(dedupe_pattern, code):
            return code, 0
        pattern = re.compile(base_pattern)
        match = pattern.search(code)
        if not match:
            return code, 0
        indent = match.group(1)
        followup = "\n" + followup_template.format(indent=indent)
        return code[:match.end()] + followup + code[match.end():], 1

    @staticmethod
    def _remove_decorative_table_line_groups(code: str) -> Tuple[str, int]:
        if "MathTable(" not in code and "Table(" not in code and "MobjectTable(" not in code:
            return code, 0

        replacements: List[Tuple[int, int, str]] = []
        fixes = 0
        for match in _TABLE_GROUP_WITH_LINES.finditer(code):
            indent = match.group(1)
            group_var = match.group(2)
            table_var = match.group(3)
            tail_args = match.group(4)
            if "line" not in tail_args.lower():
                continue
            replacement = (
                f"{indent}{group_var} = {table_var}"
                "  # auto-fix: avoid duplicate decorative grid lines"
            )
            replacements.append((match.start(), match.end(), replacement))
            fixes += 1

        for start, end, replacement in reversed(replacements):
            code = code[:start] + replacement + code[end:]
        return code, fixes

