"""
Deterministic Timing Adjuster - Programmatically corrects Manim video duration.

This module provides a non-LLM based solution to the common "padding math" 
failure where LLMs incorrectly calculate the final self.wait() value.
"""

import ast
import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class TimingAdjuster:
    """
    Analyzes and corrects the timing of Manim animation code.
    
    Primary Goal: Ensure the video duration matches the target audio duration
    by programmatically adjusting the final wait call.
    """

    def adjust(self, code: str, target_duration: float) -> str:
        """
        Parses the code, calculates actual duration, and adjusts the final wait.
        
        Args:
            code: The Manim Python code to adjust.
            target_duration: The desired total duration in seconds.
            
        Returns:
            The adjusted code string.
        """
        if not code or target_duration <= 0:
            return code

        try:
            tree = ast.parse(code)
        except Exception as e:
            logger.warning(f"TimingAdjuster: Could not parse code for timing analysis: {e}")
            return code

        # 1. Find the construct method
        construct_node = None
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "construct":
                construct_node = node
                break
        
        if not construct_node:
            logger.warning("TimingAdjuster: Could not find 'construct' method.")
            return code

        # 2. Calculate current total duration and find the last wait call
        total_duration = 0.0
        last_wait_info = None
        
        # We walk all calls in the construct method
        all_calls = sorted(
            [n for n in ast.walk(construct_node) if isinstance(n, ast.Call)],
            key=lambda n: getattr(n, 'lineno', 0)
        )
        
        for call in all_calls:
            duration = self._extract_call_duration(call)
            if duration is not None:
                total_duration += duration
                if self._is_self_method(call, "wait"):
                    last_wait_info = {
                        "line": call.lineno,
                        "current_val": duration,
                        "indent": self._get_indent(code, call.lineno)
                    }

        if total_duration == 0 and not construct_node:
            return code

        # 2. Calculate the "other" duration (everything except the last wait)
        other_duration = total_duration
        if last_wait_info:
            other_duration -= last_wait_info["current_val"]

        # 3. Determine the needed wait
        # We ensure at least a small 0.5s padding if possible, 
        # but the primary goal is to hit target_duration.
        needed_wait = max(0.1, target_duration - other_duration)

        # 4. Apply correction
        lines = code.split('\n')
        
        if last_wait_info:
            # Update existing wait
            line_idx = last_wait_info["line"] - 1
            indent = last_wait_info["indent"]
            lines[line_idx] = f"{indent}self.wait({needed_wait:.2f})"
            logger.info(f"TimingAdjuster: Adjusted existing wait on line {last_wait_info['line']} to {needed_wait:.2f}s")
        elif construct_node:
            # Append new wait at the end of construct
            # Find the last line of the construct method to get indentation
            last_stmt = construct_node.body[-1]
            indent = self._get_indent(code, last_stmt.lineno)
            
            # Insert before any potential trailing comments or after the last statement
            insert_idx = last_stmt.end_lineno if hasattr(last_stmt, "end_lineno") else last_stmt.lineno
            lines.insert(insert_idx, f"{indent}self.wait({needed_wait:.2f})")
            logger.info(f"TimingAdjuster: Appended new wait of {needed_wait:.2f}s at end of construct")

        return '\n'.join(lines)

    def _is_self_method(self, call: ast.Call, method_name: str) -> bool:
        """Checks if a call is self.method_name()."""
        return (
            isinstance(call.func, ast.Attribute) and
            isinstance(call.func.value, ast.Name) and
            call.func.value.id == "self" and
            call.func.attr == method_name
        )

    def _extract_call_duration(self, call: ast.Call) -> Optional[float]:
        """Extracts run_time or wait duration from a Manim call."""
        if not isinstance(call.func, ast.Attribute) or not isinstance(call.func.value, ast.Name) or call.func.value.id != "self":
            return None

        method = call.func.attr
        if method == "wait":
            if call.args:
                return self._eval_const(call.args[0])
            for kw in call.keywords:
                if kw.arg == "duration":
                    return self._eval_const(kw.value)
            return 1.0  # Default wait()
        
        if method == "play":
            for kw in call.keywords:
                if kw.arg == "run_time":
                    return self._eval_const(kw.value)
            return 1.0  # Default play() run_time

        return None

    def _eval_const(self, node: ast.AST) -> Optional[float]:
        """Safely evaluates a numeric constant."""
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        # Handle simple unary minus like -1.0
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            val = self._eval_const(node.operand)
            return -val if val is not None else None
        return None

    def _get_indent(self, code: str, line_no: int) -> str:
        """Captures the indentation of a specific line."""
        lines = code.split('\n')
        if 0 <= line_no - 1 < len(lines):
            line = lines[line_no - 1]
            match = re.match(r'^(\s*)', line)
            return match.group(1) if match else "        "
        return "        "

