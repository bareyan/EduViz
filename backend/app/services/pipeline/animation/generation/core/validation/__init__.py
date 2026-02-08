"""
Validation Module - Validates Manim code before rendering.

Exports:
    StaticValidator: Main class for static code analysis.
    ValidationResult: Data structure for validation outcomes.
    ValidationIssue: Structured issue with severity/confidence classification.
    RuntimeValidator: Runtime execution validator.
"""

from .static import StaticValidator, ValidationResult
from .runtime import RuntimeValidator
from .vision import VisionValidator
from .models import (
    IssueCategory,
    IssueConfidence,
    IssueSeverity,
    ValidationIssue,
)
__all__ = [
    "StaticValidator",
    "ValidationResult",
    "RuntimeValidator",
    "VisionValidator",
    "IssueCategory",
    "IssueConfidence",
    "IssueSeverity",
    "ValidationIssue",
]