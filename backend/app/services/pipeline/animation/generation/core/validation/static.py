"""
Static Validator - Wraps Ruff and Pyright for robust code analysis.
"""

import asyncio
import json
import tempfile
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional

from app.core import get_logger
from .models import IssueCategory, IssueConfidence, IssueSeverity, ValidationIssue

logger = get_logger(__name__, component="static_validator")


@dataclass
class ValidationResult:
    """Outcome of a validation run.

    Uses only structured ``ValidationIssue`` objects.
    ``valid`` is False when any CRITICAL issue exists.
    """

    valid: bool = True
    issues: List[ValidationIssue] = field(default_factory=list)
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def add_issue(self, issue: ValidationIssue) -> None:
        """Add a structured ValidationIssue."""
        self.issues.append(issue)
        if issue.severity == IssueSeverity.CRITICAL:
            self.valid = False

    @property
    def critical_issues(self) -> List[ValidationIssue]:
        """All CRITICAL-severity issues."""
        return [i for i in self.issues if i.severity == IssueSeverity.CRITICAL]

    @property
    def spatial_issues(self) -> List[ValidationIssue]:
        """All spatial/visual issues."""
        return [i for i in self.issues if i.is_spatial]

    @property
    def non_spatial_issues(self) -> List[ValidationIssue]:
        """All non-spatial issues (syntax, runtime, security, lint)."""
        return [i for i in self.issues if not i.is_spatial]

    def error_summary(self) -> str:
        """Human-readable summary of all issues for LLM context."""
        if not self.issues:
            return ""
        return "\n".join(issue.to_fixer_context() for issue in self.issues)

class StaticValidator:
    """
    Validates Python code using Ruff for fast static analysis.
    
    Focus: Only check errors that prevent animation rendering.
    """

    def __init__(self):
        # Resolve paths to Ruff (assuming it's in the same bin/Scripts dir as python)
        import sys
        import shutil
        
        bin_dir = Path(sys.executable).parent
        
        # Try to find in the same directory as python (venv/Scripts)
        self.ruff_cmd = str(bin_dir / "ruff")
        if not shutil.which(self.ruff_cmd):
             self.ruff_cmd = "ruff" # Fallback to PATH
             
        # On Windows, it might have .exe extension
        if os.name == 'nt':
            if not self.ruff_cmd.endswith('.exe') and self.ruff_cmd != "ruff":
                self.ruff_cmd += ".exe"
        
        # Check tool availability
        self.ruff_available = shutil.which(self.ruff_cmd) is not None
        
        if not self.ruff_available:
            logger.warning("Ruff not found - syntax validation will be limited")

    async def validate(self, code: str, temp_dir: Optional[str] = None) -> ValidationResult:
        """
        Runs validation on the provided code string.
        
        Args:
            code: The Python code to validate.
            temp_dir: Optional directory to write the temp file (default: system temp).
            
        Returns:
            ValidationResult with success status and list of errors.
        """
        result = ValidationResult(valid=True)
        
        # Create a temporary file for the code
        # We use a context manager but need the file path for subprocesses
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, dir=temp_dir, encoding='utf-8') as tmp_file:
            tmp_path = Path(tmp_file.name)
            tmp_file.write(code)
            
        try:
            # 1. AST Checks (Syntax + Security) - Fast & Reliable
            try:
                import ast
                tree = ast.parse(code)
                
                # Security Scan
                for node in ast.walk(tree):
                    # Check imports
                    if isinstance(node, (ast.Import, ast.ImportFrom)):
                        names = [alias.name for alias in node.names]
                        if isinstance(node, ast.ImportFrom) and node.module:
                            names.append(node.module)
                        
                        for name in names:
                            if name.split('.')[0] in ['os', 'subprocess', 'sys', 'shutil']:
                                result.add_issue(ValidationIssue(
                                    severity=IssueSeverity.CRITICAL,
                                    confidence=IssueConfidence.HIGH,
                                    category=IssueCategory.SECURITY,
                                    message=f"Forbidden import: {name}",
                                    line=node.lineno,
                                ))
                    
                    # Check builtins
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                        if node.func.id in ['exec', 'eval', 'open', '__import__']:
                            result.add_issue(ValidationIssue(
                                severity=IssueSeverity.CRITICAL,
                                confidence=IssueConfidence.HIGH,
                                category=IssueCategory.SECURITY,
                                message=f"Forbidden builtin: {node.func.id}",
                                line=node.lineno,
                            ))

            except SyntaxError as e:
                result.add_issue(ValidationIssue(
                    severity=IssueSeverity.CRITICAL,
                    confidence=IssueConfidence.HIGH,
                    category=IssueCategory.SYNTAX,
                    message=f"{e.msg}",
                    line=e.lineno,
                ))
                return result # Stop here if syntax is bad
            except Exception as e:
                result.add_issue(ValidationIssue(
                    severity=IssueSeverity.CRITICAL,
                    confidence=IssueConfidence.HIGH,
                    category=IssueCategory.SYSTEM,
                    message=f"AST analysis failed: {e}",
                ))

            # 2. Run Ruff for critical errors
            if self.ruff_available:
                ruff_res = await self._run_ruff(tmp_path)
                
                # Process Ruff Results
                if ruff_res:
                    for check in ruff_res:
                        msg = check.get("message", "Unknown error")
                        code_id = check.get("code", "UNK")
                        row = check.get("location", {}).get("row")
                        result.add_issue(ValidationIssue(
                            severity=IssueSeverity.CRITICAL,
                            confidence=IssueConfidence.HIGH,
                            category=IssueCategory.LINT,
                            message=f"{code_id}: {msg}",
                            line=row,
                        ))
                    
                result.raw_data = {"ruff": ruff_res}
            
            return result

        except Exception as e:
            logger.error(f"Validation failed with internal error: {e}")
            result.add_issue(ValidationIssue(
                severity=IssueSeverity.CRITICAL,
                confidence=IssueConfidence.HIGH,
                category=IssueCategory.SYSTEM,
                message=f"Internal validation error: {str(e)}",
            ))
            return result
            
        finally:
            # Cleanup
            if tmp_path.exists():
                try:
                    os.unlink(tmp_path)
                except Exception as e:
                    logger.warning(f"Failed to delete temp file {tmp_path}: {e}")

    async def _run_ruff(self, file_path: Path) -> List[Dict[str, Any]]:
        """Runs ruff and returns list of violation dicts."""
        try:
            # Only check CRITICAL errors that BREAK RENDERING:
            # E999 = Syntax errors (missing colons, invalid syntax)
            # F821 = Undefined name (typos, missing imports)
            # F822 = Undefined name in __all__
            # E902 = IOError/SyntaxError (file issues)
            # 
            # IGNORE everything else - we only care if the animation will render:
            # F403/F405 = Star imports (standard for Manim)
            # F841 = Unused variable (doesn't affect video output)
            # E501 = Line too long (doesn't matter for generated code)
            # All style/formatting issues
            cmd = [
                self.ruff_cmd, 
                "check", 
                "--output-format", "json",
                "--select", "E999,F821,F822,E902",  # Only execution-blocking errors
                str(file_path)
            ]
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if stdout:
                return json.loads(stdout.decode())
            return []
            
        except FileNotFoundError:
            logger.debug("Ruff not found in PATH")
            return []
        except json.JSONDecodeError:
            logger.error("Failed to parse Ruff JSON output")
            return []
        except Exception as e:
            logger.debug(f"Ruff execution failed: {e}")
            return []
