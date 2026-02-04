"""
Static Validator - Wraps Ruff and Pyright for robust code analysis.
"""

import asyncio
import json
import subprocess
import tempfile
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional

from app.core import get_logger

logger = get_logger(__name__, component="static_validator")

@dataclass
class ValidationResult:
    """Outcome of a static validation run."""
    valid: bool
    errors: List[str] = field(default_factory=list)
    raw_data: Dict[str, Any] = field(default_factory=dict)

    def add_error(self, tool: str, message: str, line: Optional[int] = None):
        """Helper to format error messages consistently."""
        prefix = f"[{tool}]"
        location = f" (Line {line})" if line else ""
        self.errors.append(f"{prefix} {message}{location}")
        self.valid = False

class StaticValidator:
    """
    Validates Python code using industrial-strength static analysis tools.
    
    Tools:
    - Ruff: Fast linting (syntax, imports, basic bugs)
    - Pyright: Type checking (arguments, attributes, existence)
    """

    def __init__(self):
        # Resolve paths to tools (assuming they are in the same bin/Scripts dir as python)
        # This handles venv isolation correctly
        import sys
        import shutil
        
        bin_dir = Path(sys.executable).parent
        
        # Try to find in the same directory as python (venv/Scripts)
        self.ruff_cmd = str(bin_dir / "ruff")
        if not shutil.which(self.ruff_cmd):
             self.ruff_cmd = "ruff" # Fallback to PATH
             
        self.pyright_cmd = str(bin_dir / "pyright")
        if not shutil.which(self.pyright_cmd):
             self.pyright_cmd = "pyright" # Fallback to PATH
             
        # On Windows, they might have .exe extension
        if os.name == 'nt':
            if not self.ruff_cmd.endswith('.exe') and self.ruff_cmd != "ruff":
                self.ruff_cmd += ".exe"
            if not self.pyright_cmd.endswith('.exe') and self.pyright_cmd != "pyright":
                self.pyright_cmd += ".exe"
        
        # Check tool availability
        self.ruff_available = shutil.which(self.ruff_cmd) is not None
        self.pyright_available = shutil.which(self.pyright_cmd) is not None
        
        if not self.ruff_available:
            logger.warning("Ruff not found - syntax validation will be limited")
        if not self.pyright_available:
            logger.warning("Pyright not found - type checking disabled (install: npm install -g pyright)")

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
            # Run tools in parallel (only if available)
            tasks = []
            if self.ruff_available:
                tasks.append(self._run_ruff(tmp_path))
            else:
                tasks.append(asyncio.sleep(0))  # Dummy coroutine
            
            if self.pyright_available:
                tasks.append(self._run_pyright(tmp_path))
            else:
                tasks.append(asyncio.sleep(0))  # Dummy coroutine
            
            results = await asyncio.gather(*tasks)
            ruff_res = results[0] if self.ruff_available else []
            pyright_res = results[1] if self.pyright_available and len(results) > 1 else {}
            
            # Process Ruff Results
            if ruff_res:
                for check in ruff_res:
                    # Ruff JSON schema: { "code": "F401", "message": "...", "location": {"row": 1, ...} }
                    # We accept some lints but fail on errors. 
                    # For now, we trap everything that isn't ignored by configuration.
                    msg = check.get("message", "Unknown error")
                    code = check.get("code", "UNK")
                    row = check.get("location", {}).get("row")
                    result.add_error("Ruff", f"{code}: {msg}", line=row)

            # Process Pyright Results
            if pyright_res:
                # Pyright JSON schema: { "generalDiagnostics": [ { "message": "...", "range": {...} } ] }
                diagnostics = pyright_res.get("generalDiagnostics", [])
                for diag in diagnostics:
                    msg = diag.get("message", "Unknown type error")
                    # range.start.line is 0-indexed
                    line = diag.get("range", {}).get("start", {}).get("line", -1) + 1
                    result.add_error("Pyright", msg, line=line)
                    
            result.raw_data = {
                "ruff": ruff_res,
                "pyright": pyright_res
            }
            
            return result

        except Exception as e:
            logger.error(f"Validation failed with internal error: {e}")
            result.add_error("System", f"Internal validation error: {str(e)}")
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
            # Only check CRITICAL errors that break execution:
            # E999 = Syntax errors (missing colons, invalid syntax)
            # F821 = Undefined name (typos, missing imports)
            # 
            # IGNORE style and non-critical issues:
            # F403/F405 = Star imports (standard for Manim)
            # F841 = Unused variable (doesn't affect video output)
            # E501 = Line too long (doesn't matter for generated code)
            cmd = [
                self.ruff_cmd, 
                "check", 
                "--output-format", "json",
                "--select", "E999,F821",  # Only syntax errors and undefined names
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

    async def _run_pyright(self, file_path: Path) -> Dict[str, Any]:
        """Runs pyright and returns full JSON report."""
        try:
            # --outputjson return JSON report
            cmd = [self.pyright_cmd, "--outputjson", str(file_path)]
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if stdout:
                return json.loads(stdout.decode())
            return {}
            
        except FileNotFoundError:
            logger.debug("Pyright not found in PATH")
            return {}
        except json.JSONDecodeError:
            logger.error("Failed to parse Pyright JSON output")
            return {}
        except Exception as e:
            logger.debug(f"Pyright execution failed: {e}")
            return {}
