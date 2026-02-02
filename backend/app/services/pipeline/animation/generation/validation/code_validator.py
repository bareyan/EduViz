"""
Composite code validator

Orchestrates all validators to provide complete code validation.
Single Responsibility: Coordinate static and spatial validators.
"""

from typing import Dict, Any
from dataclasses import dataclass

from .static_validator import StaticValidator, StaticValidationResult
from .spatial import SpatialValidator, SpatialValidationResult


@dataclass
class CodeValidationResult:
    """Aggregated validation result from all validators"""
    valid: bool
    static: StaticValidationResult
    spatial: SpatialValidationResult
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format for API responses"""
        return {
            "valid": self.valid,
            "static": {
                "valid": self.static.valid,
                "errors": self.static.errors,
                "warnings": self.static.warnings,
                "line_number": self.static.line_number,
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
                "info": [
                    {"line": i.line_number, "message": i.message, "code": i.code_snippet}
                    for i in self.spatial.info
                ],
            }
        }
    
    def get_error_summary(self) -> str:
        """Get LLM-friendly error summary - ONLY errors are sent to LLM for fixing.
        
        Severity levels:
        - errors: Blocking, MUST send to LLM
        - warnings: Include for awareness but don't block
        - info: NOT sent to LLM at all (may be intentional)
        """
        sections = []
        
        # Static errors (highest priority - blocks other validation)
        if not self.static.valid:
            static_lines = ["## STATIC ERRORS"]
            if self.static.line_number:
                static_lines.append(f"(Line {self.static.line_number})")
            for err in self.static.errors:
                static_lines.append(f"- {err}")
            sections.append("\n".join(static_lines))
        
        # Spatial errors (blocking - must fix)
        if self.spatial.errors:
            spatial_lines = ["## SPATIAL ERRORS (Must Fix)"]
            for err in self.spatial.errors:
                line_info = f"Line {err.line_number}" if err.line_number else "Unknown line"
                code_info = f"\n  Code: `{err.code_snippet}`" if err.code_snippet else ""
                fix_info = f"\n  FIX: {err.suggested_fix}" if err.suggested_fix else ""
                spatial_lines.append(f"- {line_info}: {err.message}{code_info}{fix_info}")
            sections.append("\n".join(spatial_lines))
            
        # Warnings are included but not blocking
        if self.spatial.warnings:
            warn_lines = ["## SPATIAL WARNINGS (Non-blocking)"]
            for warn in self.spatial.warnings:
                line_info = f"Line {warn.line_number}" if warn.line_number else "Unknown line"
                fix_info = f" (FIX: {warn.suggested_fix})" if warn.suggested_fix else ""
                warn_lines.append(f"- {line_info}: {warn.message}{fix_info}")
            sections.append("\n".join(warn_lines))
        
        # INFO level issues are NOT sent to LLM - they may be intentional
            
        if not sections:
            return "No errors found"
            
        return "\n\n".join(sections)


class CodeValidator:
    """Coordinates the full validation pipeline."""
    
    def __init__(self, linter_path: str = "linter.py"):
        self.static_validator = StaticValidator()
        self.spatial_validator = SpatialValidator(linter_path)
        
    def validate(self, code: str) -> CodeValidationResult:
        """Run complete validation pipeline."""
        static_res = self.static_validator.validate(code)
        
        # If static validation fails (syntax, structure, or policy), skip spatial execution
        if not static_res.valid:
            spatial_res = SpatialValidationResult(valid=True, errors=[], warnings=[], info=[])
        else:
            spatial_res = self.spatial_validator.validate(code)
            
        return CodeValidationResult(
            valid=static_res.valid and spatial_res.valid,
            static=static_res,
            spatial=spatial_res
        )

    def validate_code(self, code: str) -> Dict[str, Any]:
        """Backward-compatible wrapper returning a simple dict."""
        result = self.validate(code)
        return {
            "valid": result.valid,
            "error": None if result.valid else result.get_error_summary(),
            "details": result.to_dict()
        }
