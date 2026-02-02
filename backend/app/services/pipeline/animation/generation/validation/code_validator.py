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
        """Get LLM-friendly error summary with line numbers and code context.
        
        This summary is designed to be sent to the LLM for surgical fixes,
        so it must include:
        1. Line numbers where issues occur
        2. The actual code snippet causing the issue
        3. Clear description of what's wrong
        4. Actionable fix suggestions where possible
        """
        sections = []
        
        # Syntax errors (highest priority - blocks other validation)
        if not self.syntax.valid:
            sections.append(
                f"## SYNTAX ERROR (Line {self.syntax.line_number or 'unknown'})\n"
                f"Type: {self.syntax.error_type}\n"
                f"Message: {self.syntax.error_message}"
            )
        
        # Structure errors
        if self.structure.errors:
            struct_lines = ["## STRUCTURE ERRORS"]
            for err in self.structure.errors:
                struct_lines.append(f"- {err}")
            sections.append("\n".join(struct_lines))
        
        # Missing imports
        if self.imports.missing_imports:
            sections.append(
                f"## MISSING IMPORTS\n"
                f"Add these imports: {', '.join(self.imports.missing_imports)}"
            )
        
        # Spatial errors (with full context)
        if self.spatial.errors:
            spatial_lines = ["## SPATIAL ERRORS (Objects out of frame)"]
            for err in self.spatial.errors:
                line_info = f"Line {err.line_number}" if err.line_number else "Unknown line"
                code_info = f"\n  Code: `{err.code_snippet}`" if err.code_snippet else ""
                spatial_lines.append(
                    f"\n### {line_info}\n"
                    f"Issue: {err.message}{code_info}\n"
                    f"Fix: Scale down or reposition the object to stay within bounds (x: -5.5 to 5.5, y: -3.0 to 3.0)"
                )
            sections.append("\n".join(spatial_lines))
        
        # Spatial warnings (included for context but marked as warnings)
        if self.spatial.warnings:
            warn_lines = ["## WARNINGS (Optional fixes)"]
            for warn in self.spatial.warnings[:5]:  # Limit to 5 to avoid overwhelming
                line_info = f"Line {warn.line_number}" if warn.line_number else "Unknown line"
                warn_lines.append(f"- {line_info}: {warn.message}")
            if len(self.spatial.warnings) > 5:
                warn_lines.append(f"- ... and {len(self.spatial.warnings) - 5} more warnings")
            sections.append("\n".join(warn_lines))
        
        if not sections:
            return "No errors found"
        
        return "\n\n".join(sections)


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
            code: Python/Manim code to validate. Assumed to be a full file.
            
        Returns:
            CodeValidationResult with aggregated results
        """
        # Validate syntax first (fast-fail)
        syntax_result = self.syntax_validator.validate(code)
        
        # If syntax is invalid, skip other validators
        if not syntax_result.valid:
            return CodeValidationResult(
                valid=False,
                syntax=syntax_result,
                structure=ManimValidationResult(valid=True),  # Skipped
                imports=ImportsValidationResult(valid=True),  # Skipped
                spatial=SpatialValidationResult(valid=True)   # Skipped
            )
        
        # Run structure and imports validation
        structure_result = self.structure_validator.validate(code)
        imports_result = self.imports_validator.validate(code)
        
        # Short-circuit: If structure or imports fail, skip spatial validation
        if not structure_result.valid or not imports_result.valid:
            return CodeValidationResult(
                valid=False,
                syntax=syntax_result,
                structure=structure_result,
                imports=imports_result,
                spatial=SpatialValidationResult(valid=True) # Skipped
            )
            
        # Run spatial validation (expensive)
        spatial_result = self.spatial_validator.validate(code)
        
        # Overall validity requires all validators to pass
        overall_valid = spatial_result.valid
        
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
