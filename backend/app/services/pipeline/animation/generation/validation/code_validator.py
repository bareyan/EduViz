"""
Composite code validator

Orchestrates all validators to provide complete code validation.
Single Responsibility: Coordinate validators and aggregate results.
"""

from typing import Dict, Any
from dataclasses import dataclass

from .syntax_validator import PythonSyntaxValidator, SyntaxValidationResult
from .manim_validator import ManimStructureValidator, ManimValidationResult
from .imports_validator import ManimImportsValidator, ImportsValidationResult
from .spatial_validator import SpatialValidator, SpatialValidationResult


@dataclass
class CodeValidationResult:
    """Aggregated validation result from all validators"""
    valid: bool
    syntax: SyntaxValidationResult
    structure: ManimValidationResult
    imports: ImportsValidationResult
    spatial: SpatialValidationResult
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for API responses"""
        return {
            "valid": self.valid,
            "syntax": {
                "valid": self.syntax.valid,
                "error_message": self.syntax.error_message,
                "line_number": self.syntax.line_number,
                "error_type": self.syntax.error_type,
            },
            "structure": {
                "valid": self.structure.valid,
                "errors": self.structure.errors,
                "warnings": self.structure.warnings,
            },
            "imports": {
                "valid": self.imports.valid,
                "missing_imports": self.imports.missing_imports,
                "unused_imports": self.imports.unused_imports,
                "has_wildcard": self.imports.has_wildcard,
            },
            "spatial": {
                "valid": self.spatial.valid,
                "errors": [
                    {"line": e.line_number, "message": e.message, "code": e.code_snippet}
                    for e in self.spatial.errors
                ],
                "warnings": [
                    {"line": w.line_number, "message": w.message, "code": w.code_snippet}
                    for w in self.spatial.warnings
                ],
            }
        }
    
    def get_error_summary(self) -> str:
        """Get human-readable error summary"""
        errors = []
        
        if not self.syntax.valid:
            errors.append(f"Syntax Error: {self.syntax.error_message}")
        
        if self.structure.errors:
            errors.extend([f"Structure: {err}" for err in self.structure.errors])
        
        if self.imports.missing_imports:
            errors.append(f"Missing imports: {', '.join(self.imports.missing_imports)}")
        
        if self.spatial.errors:
            errors.extend([f"Spatial: {err.message}" for err in self.spatial.errors])
        
        return "\n".join(errors) if errors else "No errors"


class CodeValidator:
    """
    Orchestrates all code validators.
    
    Runs syntax, structure, import, and spatial validation in sequence,
    short-circuiting on syntax errors (no point checking structure
    if syntax is invalid).
    """
    
    def __init__(self):
        self.syntax_validator = PythonSyntaxValidator()
        self.structure_validator = ManimStructureValidator()
        self.imports_validator = ManimImportsValidator()
        self.spatial_validator = SpatialValidator()
    
    def validate(self, code: str) -> CodeValidationResult:
        """
        Run all validators on the code.
        
        Args:
            code: Python/Manim code to validate
            
        Returns:
            CodeValidationResult with aggregated results
        """
        # Validate syntax first (fast-fail)
        syntax_result = self.syntax_validator.validate(code)
        
        # If syntax is invalid, skip other validators
        if not syntax_result.valid:
            # Return with empty structure/imports/spatial results
            return CodeValidationResult(
                valid=False,
                syntax=syntax_result,
                structure=ManimValidationResult(valid=True),  # Skipped
                imports=ImportsValidationResult(valid=True),  # Skipped
                spatial=SpatialValidationResult(valid=True)   # Skipped
            )
        
        # Run structure, imports, and spatial validation
        structure_result = self.structure_validator.validate(code)
        imports_result = self.imports_validator.validate(code)
        spatial_result = self.spatial_validator.validate(code)
        
        # Overall validity requires all validators to pass
        overall_valid = (
            syntax_result.valid and
            structure_result.valid and
            imports_result.valid and
            spatial_result.valid
        )
        
        return CodeValidationResult(
            valid=overall_valid,
            syntax=syntax_result,
            structure=structure_result,
            imports=imports_result,
            spatial=spatial_result
        )
    
    def validate_and_get_dict(self, code: str) -> Dict[str, Any]:
        """Convenience method to validate and return dict"""
        return self.validate(code).to_dict()

    def validate_code(self, code: str) -> Dict[str, Any]:
        """Backward-compatible wrapper returning a simple dict.

        Returns:
            {
              "valid": bool,
              "error": str (summary if invalid),
              "details": full validation dict
            }
        """
        result = self.validate(code)
        return {
            "valid": result.valid,
            "error": None if result.valid else result.get_error_summary(),
            "details": result.to_dict()
        }
