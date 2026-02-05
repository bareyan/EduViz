"""
Runtime Validator - Executes Manim code in dry-run mode to catch runtime errors.

Responsibilities:
- Execute Manim dry-run with optional spatial check injection
- Parse both standard Python tracebacks and structured spatial JSON
- Convert structured spatial output into typed ValidationIssue objects
"""

import asyncio
import json
import os
import re
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import List, Optional, Tuple

from app.core import get_logger
from .models import (
    IssueCategory,
    IssueConfidence,
    IssueSeverity,
    ValidationIssue,
)
from .spatial import SPATIAL_JSON_MARKER
from .static import ValidationResult

# Category map for the spatial JSON parser
_CATEGORY_MAP = {
    "out_of_bounds": IssueCategory.OUT_OF_BOUNDS,
    "text_overlap": IssueCategory.TEXT_OVERLAP,
    "object_occlusion": IssueCategory.OBJECT_OCCLUSION,
    "visibility": IssueCategory.VISIBILITY,
}
_SEVERITY_MAP = {
    "critical": IssueSeverity.CRITICAL,
    "warning": IssueSeverity.WARNING,
    "info": IssueSeverity.INFO,
}
_CONFIDENCE_MAP = {
    "high": IssueConfidence.HIGH,
    "medium": IssueConfidence.MEDIUM,
    "low": IssueConfidence.LOW,
}

logger = get_logger(__name__, component="runtime_validator")

class RuntimeValidator:
    """
    Validates Manim code by executing it in a dry-run environment.
    
    This catches:
    - Runtime TypeErrors (wrong arguments)
    - Logic bugs (division by zero)
    - LaTeX compilation errors
    - Missing resources/assets
    
    It uses 'manim -ql --dry_run' to execute the construct() method 
    without performing expensive video rendering/encoding.
    """
    
    def __init__(self):
        # Resolve manim executable
        # We prefer 'python -m manim' to ensure we use the same environment
        self.python_exe = sys.executable

    async def validate(self, code: str, temp_dir: Optional[str] = None, enable_spatial_checks: bool = False) -> ValidationResult:
        """
        Executes the code in dry-run mode.
        """
        result = ValidationResult(valid=True)

        if enable_spatial_checks:
            try:
                from .spatial import SpatialCheckInjector
                injector = SpatialCheckInjector()
                # Inject logic before writing to file
                code = injector.inject(code)
            except ImportError:
                 logger.warning("Spatial validation module not found, skipping checks.")
            except Exception as e:
                 logger.warning(f"Failed to inject spatial checks: {e}")
        
        # Create temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, dir=temp_dir, encoding='utf-8') as tmp_file:
            tmp_path = Path(tmp_file.name)
            tmp_file.write(code)
        
        # Initialize temp_media_dir to None
        temp_media_dir = None
            
        try:
            # We need to find the scene name to be robust, 
            # but Manim can often auto-discover if there's only one scene.
            # For robustness, we let Manim discover.
            
            # Command: python -m manim -ql --dry_run --media_dir <tmp> <file>
            # We use a temp media dir to avoid polluting the workspace
            temp_media_dir = tmp_path.parent / f"manim_dry_run_{tmp_path.stem}"
            
            cmd = [
                self.python_exe, "-m", "manim", 
                "-ql",             # Low quality (faster init)
                "--dry_run",       # Do not write video files
                "--media_dir", str(temp_media_dir),
                str(tmp_path)
            ]

            env = os.environ.copy()
            env["PYTHONWARNINGS"] = "ignore::SyntaxWarning"
            
            # Use subprocess.run via thread to avoid ProactorEventLoop issues on Windows
            result_proc = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                env=env,
                timeout=180.0  # 180s timeout - dry-run can be slow with complex loops
            )
            
            if result_proc.returncode != 0:
                # Check for structured spatial JSON first
                spatial_issues = self._parse_spatial_json(result_proc.stderr)
                if spatial_issues:
                    for issue in spatial_issues:
                        result.add_issue(issue)
                else:
                    error_msg, error_line = self._parse_manim_error(result_proc.stderr)
                    result.add_issue(ValidationIssue(
                        severity=IssueSeverity.CRITICAL,
                        confidence=IssueConfidence.HIGH,
                        category=IssueCategory.RUNTIME,
                        message=error_msg,
                        line=error_line,
                    ))
                
        except subprocess.TimeoutExpired:
            result.add_issue(ValidationIssue(
                severity=IssueSeverity.CRITICAL,
                confidence=IssueConfidence.HIGH,
                category=IssueCategory.RUNTIME,
                message="Execution timed out after 180s - check for large loops or complex operations",
            ))
            return result
                
        except Exception as e:
            logger.error(f"Runtime validation failed: {e}")
            result.add_issue(ValidationIssue(
                severity=IssueSeverity.CRITICAL,
                confidence=IssueConfidence.HIGH,
                category=IssueCategory.SYSTEM,
                message=f"Internal validation error: {str(e)}",
            ))
            
        finally:
            # Cleanup source file
            if tmp_path.exists():
                try:
                    os.unlink(tmp_path)
                except Exception as e:
                    logger.warning(f"Failed to delete temp file {tmp_path}: {e}")
            
            # Cleanup temp media dir
            if temp_media_dir is not None and temp_media_dir.exists():
                try:
                    shutil.rmtree(temp_media_dir)
                except Exception as e:
                    logger.warning(f"Failed to delete temp media dir {temp_media_dir}: {e}")
                    
        return result

    def _parse_spatial_json(self, stderr: str) -> List[ValidationIssue]:
        """Extract structured spatial issues from stderr.

        The injected spatial validator outputs a JSON payload prefixed with
        SPATIAL_ISSUES_JSON: when critical issues are found.  This method
        parses that payload into typed ValidationIssue objects.

        Returns:
            List of ValidationIssue objects, or empty list if no marker found.
        """
        marker_pos = stderr.find(SPATIAL_JSON_MARKER)
        if marker_pos == -1:
            return []

        json_str = stderr[marker_pos + len(SPATIAL_JSON_MARKER):].strip()
        # The JSON may be followed by additional stderr lines; take first line
        first_newline = json_str.find("\n")
        if first_newline != -1:
            json_str = json_str[:first_newline]

        try:
            raw_issues = json.loads(json_str)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning(f"Failed to parse spatial JSON: {exc}")
            return []

        if not isinstance(raw_issues, list):
            return []

        issues: List[ValidationIssue] = []
        for raw in raw_issues:
            try:
                issues.append(self._raw_to_validation_issue(raw))
            except (KeyError, ValueError) as exc:
                logger.debug(f"Skipping malformed spatial issue: {exc}")
        return issues

    @staticmethod
    def _raw_to_validation_issue(raw: dict) -> ValidationIssue:
        """Convert a raw dict from the injected code into a ValidationIssue."""
        return ValidationIssue(
            severity=_SEVERITY_MAP[raw["severity"]],
            confidence=_CONFIDENCE_MAP[raw["confidence"]],
            category=_CATEGORY_MAP[raw["category"]],
            message=raw["message"],
            auto_fixable=raw.get("auto_fixable", False),
            fix_hint=raw.get("fix_hint"),
            details=raw.get("details", {}),
        )

    def _parse_manim_error(self, stderr: str) -> tuple[str, Optional[int]]:
        """Extract the meaningful error message and line from Manim traceback.

        Returns:
            Tuple of (error_message, line_number_or_None).
        """
        lines = stderr.splitlines()
        if not lines:
            return "Unknown runtime error (no stderr output)", None

        logger.debug(f"Full Manim stderr (first 2000 chars):\n{stderr[:2000]}")

        # Strategy 1: Standard Python exception pattern
        exception_line = None
        for line in reversed(lines):
            stripped = line.strip()
            if re.match(r'^[A-Z][a-zA-Z]*Error:', stripped) or re.match(r'^[A-Z][a-zA-Z]*:', stripped):
                exception_line = stripped
                break

        # Strategy 2: Last meaningful non-empty line
        if not exception_line:
            for line in reversed(lines):
                stripped = line.strip()
                if stripped and not stripped.startswith('During handling of'):
                    exception_line = stripped
                    break

        if not exception_line:
            exception_line = "Unknown error"

        # Extract line number from traceback
        line_num: Optional[int] = None
        for line in reversed(lines):
            match = re.search(r'File ".*\.py", line (\d+),', line)
            if match:
                line_num = int(match.group(1))
                break

        if len(exception_line) > 300:
            exception_line = exception_line[:300] + "..."

        return exception_line, line_num
