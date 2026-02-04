"""
Validation Module - Validates Manim code before rendering.

Exports:
    StaticValidator: Main class for static code analysis.
    ValidationResult: Data structure for validation outcomes.
"""

from .static import StaticValidator, ValidationResult
from .runtime import RuntimeValidator
