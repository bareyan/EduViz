"""
Runtime Validator - Executes Manim code in dry-run mode to catch runtime errors.
"""

import asyncio
import os
import re
import sys
import subprocess
import tempfile
import shutil
from pathlib import Path
from typing import Optional, Tuple

from app.core import get_logger
from .static import ValidationResult

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
            
            # Use subprocess.run via thread to avoid ProactorEventLoop issues on Windows
            result_proc = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=30.0  # 30s timeout
            )
            
            if result_proc.returncode != 0:
                error_msg = self._parse_manim_error(result_proc.stderr)
                result.add_error("Runtime", error_msg)
                
        except subprocess.TimeoutExpired:
            result.add_error("Runtime", "Execution timed out (possible infinite loop)")
            return result
                
        except Exception as e:
            logger.error(f"Runtime validation failed: {e}")
            result.add_error("System", f"Internal validation error: {str(e)}")
            
        finally:
            # Cleanup source file
            if tmp_path.exists():
                try:
                    os.unlink(tmp_path)
                except Exception as e:
                    logger.warning(f"Failed to delete temp file {tmp_path}: {e}")
            
            # Cleanup temp media dir
            if 'temp_media_dir' in locals() and temp_media_dir.exists():
                try:
                    shutil.rmtree(temp_media_dir)
                except Exception as e:
                    logger.warning(f"Failed to delete temp media dir {temp_media_dir}: {e}")
                    
        return result

    def _parse_manim_error(self, stderr: str) -> str:
        """Extracts the meaningful error message from Manim traceback."""
        # Manim tracebacks are standard Python tracebacks.
        # We want the exception type + message and the context around it.
        
        lines = stderr.splitlines()
        if not lines:
            return "Unknown runtime error (no stderr output)"
        
        # Also log the full stderr for debugging - do this first
        logger.debug(f"Full Manim stderr (first 2000 chars):\n{stderr[:2000]}")
        
        # Strategy 1: Look for standard Python exception pattern: "ExceptionType: message"
        exception_line = None
        for line in reversed(lines):
            stripped = line.strip()
            # Look for lines with exception pattern (colon after word)
            if re.match(r'^[A-Z][a-zA-Z]*Error:', stripped) or re.match(r'^[A-Z][a-zA-Z]*:', stripped):
                exception_line = stripped
                logger.debug(f"Found exception line via pattern: {exception_line}")
                break
        
        # Strategy 2: If no exception pattern found, look for last meaningful non-empty line
        if not exception_line:
            for line in reversed(lines):
                stripped = line.strip()
                if stripped and not stripped.startswith('During handling of'):
                    exception_line = stripped
                    logger.debug(f"Found fallback line (last meaningful): {exception_line}")
                    break
        
        if not exception_line:
            exception_line = "Unknown error"
        
        # Look for the file reference in the traceback to get line number
        # File "...", line X, in construct
        line_num = None
        for line in reversed(lines):
            match = re.search(r'File ".*\.py", line (\d+),', line)
            if match:
                line_num = match.group(1)
                break
        
        # Truncate if too long but preserve the key info
        # Most exceptions are short, but we allow up to 300 chars for detailed messages
        if len(exception_line) > 300:
            exception_line = exception_line[:300] + "..."
        
        prefix = f" (Line {line_num})" if line_num else ""
        
        return f"{exception_line}{prefix}"
