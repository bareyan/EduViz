"""
Runtime preflight validation for Manim code.

Runs a lightweight execution pass to catch runtime/type errors before spatial validation.
"""

from dataclasses import dataclass, field
from typing import List, Optional
import tempfile
import traceback
import os
import linecache
from contextlib import contextmanager

from .spatial.engine import ManimEngine


@dataclass
class RuntimeValidationResult:
    """Result of runtime preflight validation."""
    valid: bool
    errors: List[str] = field(default_factory=list)
    exception_type: Optional[str] = None
    exception_message: Optional[str] = None
    line_number: Optional[int] = None


class RuntimeValidator:
    """Runs a fast runtime preflight to catch type/runtime errors."""

    def __init__(self, linter_path: str = "linter.py"):
        self.linter_path = linter_path
        self.engine = ManimEngine(self.linter_path)

    def validate(self, code: str) -> RuntimeValidationResult:
        if not code or not code.strip():
            return RuntimeValidationResult(valid=False, errors=["Code is empty"])

        try:
            self.engine.initialize()
        except ImportError:
            # If Manim isn't available, don't block validation
            return RuntimeValidationResult(valid=True)

        self._apply_preflight_config()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as f:
            f.write(code)
            temp_filename = f.name

        try:
            with self._patched_runtime():
                self.engine.run_scenes(temp_filename)
            return RuntimeValidationResult(valid=True)
        except Exception as exc:
            line_number = self._extract_line_number(exc, temp_filename)
            error_msg = f"{type(exc).__name__}: {exc}"
            return RuntimeValidationResult(
                valid=False,
                errors=[error_msg],
                exception_type=type(exc).__name__,
                exception_message=str(exc),
                line_number=line_number,
            )
        finally:
            try:
                os.unlink(temp_filename)
            except Exception:
                pass
            linecache.clearcache()

    def _apply_preflight_config(self) -> None:
        """Configure Manim for ultra-fast preflight."""
        if not self.engine.config:
            self.engine.initialize()

        self.engine.config.update({
            "write_to_movie": False,
            "save_last_frame": False,
            "preview": False,
            "verbosity": "CRITICAL",
            "renderer": "cairo",
            "frame_rate": 1,
            "pixel_width": 160,
            "pixel_height": 90,
            "quality": "low_quality",
        })

    @contextmanager
    def _patched_runtime(self):
        """Patch Scene.play/Scene.wait to be no-ops (advance time if provided)."""
        if not self.engine.Scene:
            self.engine.initialize()

        original_play = self.engine.Scene.play
        original_wait = self.engine.Scene.wait

        def _advance_time(scene_self, run_time: Optional[float] = None):
            if run_time is None:
                return
            try:
                scene_self.renderer.time += float(run_time)
            except Exception:
                pass

        def patched_play(scene_self, *args, **kwargs):
            _advance_time(scene_self, kwargs.get("run_time"))

        def patched_wait(scene_self, *args, **kwargs):
            _advance_time(scene_self, kwargs.get("run_time"))

        try:
            self.engine.Scene.play = patched_play
            self.engine.Scene.wait = patched_wait
            yield
        finally:
            self.engine.Scene.play = original_play
            self.engine.Scene.wait = original_wait

    def _extract_line_number(self, exc: Exception, temp_filename: str) -> Optional[int]:
        """Find the line number in the user temp file from traceback."""
        try:
            tb = traceback.TracebackException.from_exception(exc)
            for frame in tb.stack:
                if frame.filename == temp_filename:
                    return frame.lineno
        except Exception:
            pass
        return None
