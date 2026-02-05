"""
Composite code validator

Orchestrates all validators to provide complete code validation.
Single Responsibility: Coordinate static and spatial validators.
"""

from typing import Dict, Any
from dataclasses import dataclass

from .static_validator import StaticValidator, StaticValidationResult
from .spatial import SpatialValidator, SpatialValidationResult
from .runtime_validator import RuntimeValidator, RuntimeValidationResult
from app.core import get_logger
import time


@dataclass
class CodeValidationResult:
    """Aggregated validation result from all validators"""
    valid: bool
    static: StaticValidationResult
    runtime: RuntimeValidationResult
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
            "runtime": {
                "valid": self.runtime.valid,
                "errors": self.runtime.errors,
                "exception_type": self.runtime.exception_type,
                "exception_message": self.runtime.exception_message,
                "line_number": self.runtime.line_number,
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

        # Runtime errors (blocking)
        if not self.runtime.valid and self.runtime.errors:
            runtime_lines = ["## RUNTIME ERRORS"]
            if self.runtime.line_number:
                runtime_lines.append(f"(Line {self.runtime.line_number})")
            for err in self.runtime.errors:
                runtime_lines.append(f"- {err}")
            sections.append("\n".join(runtime_lines))
        
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
        self.runtime_validator = RuntimeValidator(linter_path)
        self.spatial_validator = SpatialValidator(linter_path)
        self.logger = get_logger(__name__, component="code_validator")
        
    def validate(self, code: str) -> CodeValidationResult:
        """Run complete validation pipeline."""
        start_total = time.perf_counter()

        start_static = time.perf_counter()
        static_res = self.static_validator.validate(code)
        static_duration_ms = (time.perf_counter() - start_static) * 1000.0
        
        # If static validation fails (syntax, structure, or policy), skip runtime/spatial execution
        if not static_res.valid:
            runtime_res = RuntimeValidationResult(valid=True, errors=[])
            spatial_res = SpatialValidationResult(valid=True, errors=[], warnings=[], info=[])
            runtime_duration_ms = 0.0
            spatial_duration_ms = 0.0
        else:
            start_runtime = time.perf_counter()
            runtime_res = self.runtime_validator.validate(code)
            runtime_duration_ms = (time.perf_counter() - start_runtime) * 1000.0

            if not runtime_res.valid:
                spatial_res = SpatialValidationResult(valid=True, errors=[], warnings=[], info=[])
                spatial_duration_ms = 0.0
            else:
                start_spatial = time.perf_counter()
                spatial_res = self.spatial_validator.validate(code)
                spatial_duration_ms = (time.perf_counter() - start_spatial) * 1000.0

        total_duration_ms = (time.perf_counter() - start_total) * 1000.0

        self.logger.info(
            "Validation timings",
            extra={
                "static_duration_ms": round(static_duration_ms, 2),
                "runtime_duration_ms": round(runtime_duration_ms, 2),
                "spatial_duration_ms": round(spatial_duration_ms, 2),
                "total_duration_ms": round(total_duration_ms, 2),
            },
        )
            
        return CodeValidationResult(
            valid=static_res.valid and runtime_res.valid and spatial_res.valid,
            static=static_res,
            runtime=runtime_res,
            spatial=spatial_res
        )
