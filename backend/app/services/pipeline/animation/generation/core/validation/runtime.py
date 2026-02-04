"""
Runtime Validator - Executes Manim code in dry-run mode to catch runtime errors.
"""

import asyncio
import os
import re
import sys
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

    async def validate(self, code: str, temp_dir: Optional[str] = None) -> ValidationResult:
        """
        Executes the code in dry-run mode.
        """
        result = ValidationResult(valid=True)
        
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
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                # 30s timeout for dry run should be plenty
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30.0)
            except asyncio.TimeoutError:
                proc.kill()
                result.add_error("Runtime", "Execution timed out (possible infinite loop)")
                return result
                
            if proc.returncode != 0:
                error_msg = self._parse_manim_error(stderr.decode())
                result.add_error("Runtime", error_msg)
                
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
        # We want the last line (Exception: message) and maybe the line number in the script.
        
        lines = stderr.splitlines()
        if not lines:
            return "Unknown runtime error (no stderr output)"
            
        # Strategy: Look for the last line that isn't empty
        last_line = lines[-1].strip()
        
        # Look for the file reference in the traceback to get line number
        # File "...", line X, in construct
        line_num = None
        for line in reversed(lines):
            match = re.search(r'File ".*\.py", line (\d+),', line)
            if match:
                line_num = match.group(1)
                break
                
        prefix = f" (Line {line_num})" if line_num else ""
        return f"{last_line}{prefix}"
