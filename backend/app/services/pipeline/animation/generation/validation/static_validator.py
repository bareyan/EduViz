"""
Static AST-based validation for Manim code.

Checks for:
- Python syntax correctness.
- Required Manim structure (Scene subclass, construct method).
- Forbidden patterns (manual background settings).
"""

import ast
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class StaticValidationResult:
    """Result of static AST validation."""
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    line_number: Optional[int] = None


class StaticValidator:
    """Performs non-execution AST checks on Manim code."""

    def validate(self, code: str) -> StaticValidationResult:
        """Run AST parsing and structural analysis."""
        if not code or not code.strip():
            return StaticValidationResult(valid=False, errors=["Code is empty"])

        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return StaticValidationResult(
                valid=False,
                errors=[f"Syntax Error: {exc.msg}"],
                line_number=exc.lineno
            )

        errors: List[str] = []
        warnings: List[str] = []

        # Check for Scene class
        scene_classes = [
            node for node in tree.body
            if isinstance(node, ast.ClassDef) and self._is_scene_subclass(node)
        ]

        if not scene_classes:
            errors.append("Code must define at least one class inheriting from 'Scene'")
        else:
            for node in scene_classes:
                if not self._has_construct_method(node):
                    errors.append(f"Class '{node.name}' is missing the 'construct(self)' method")

        # Check for forbidden patterns
        self._check_forbidden_patterns(tree, errors, warnings)

        return StaticValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            warnings=warnings
        )

    def _is_scene_subclass(self, node: ast.ClassDef) -> bool:
        """Determine if a class inherits from Scene or ThreeDScene."""
        for base in node.bases:
            # Handle direct Scene or manim.Scene
            if isinstance(base, ast.Name) and base.id in ('Scene', 'ThreeDScene'):
                return True
            if isinstance(base, ast.Attribute) and base.attr in ('Scene', 'ThreeDScene'):
                return True
        return False

    def _has_construct_method(self, node: ast.ClassDef) -> bool:
        """Check if class has a construct(self) method."""
        for item in node.body:
            if isinstance(item, ast.FunctionDef) and item.name == 'construct':
                # Check for 'self' arg
                if item.args.args and item.args.args[0].arg == 'self':
                    return True
        return False

    def _check_forbidden_patterns(self, tree: ast.AST, errors: List[str], warnings: List[str]) -> None:
        """Walk the tree to find banned operations."""
        for node in ast.walk(tree):
            # Check for background_color assignment
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Attribute) and target.attr == 'background_color':
                        warnings.append("Don't set 'background_color' manually; it is pre-configured in the pipeline.")
                    if isinstance(target, ast.Name) and target.id == 'background_color':
                        warnings.append("Don't set 'background_color' manually; it is pre-configured.")
