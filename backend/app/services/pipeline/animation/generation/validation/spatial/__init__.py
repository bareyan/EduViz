"""
Spatial validation package for Manim code.
"""

from .models import SpatialIssue, SpatialValidationResult
from .validator import SpatialValidator
from .formatter import format_spatial_issues

__all__ = [
    "SpatialIssue",
    "SpatialValidationResult",
    "SpatialValidator",
    "format_spatial_issues",
    "lint_manim_code",
    "lint_manim_file",
]


def lint_manim_file(filename: str) -> str:
    """Run the linter on a file path for CLI use."""
    with open(filename, 'r', encoding='utf-8') as f:
        code = f.read()

    validator = SpatialValidator()
    result = validator.validate(code)
    return format_spatial_issues(result)


def lint_manim_code(code: str) -> str:
    """Run the linter on in-memory code for API use."""
    validator = SpatialValidator()
    result = validator.validate(code)
    return format_spatial_issues(result)
