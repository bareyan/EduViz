"""
Data models for spatial validation issues and results.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class FrameCapture:
    """A screenshot captured at a specific moment during validation."""
    screenshot_path: str  # Path to PNG file
    timestamp: float  # Scene time when captured
    event_ids: List[str] = field(default_factory=list)  # Events detected at this moment


@dataclass
class SpatialIssue:
    """A single spatial layout issue (overlap, boundary, etc.)."""
    line_number: int
    severity: str  # "error", "warning", or "info"
    message: str
    code_snippet: str
    suggested_fix: str = ""  # Actionable fix suggestion for LLM
    frame_id: Optional[str] = None  # Links to FrameCapture for visual context


@dataclass
class SpatialValidationResult:
    """Aggregated result of spatial validation across a script."""
    valid: bool
    errors: List[SpatialIssue] = field(default_factory=list)  # Blocking, must fix
    warnings: List[SpatialIssue] = field(default_factory=list)  # Try to fix, but don't block
    info: List[SpatialIssue] = field(default_factory=list)  # Informational only, don't send to LLM
    raw_report: str = ""
    frame_captures: List[FrameCapture] = field(default_factory=list)  # Screenshots for visual analysis

    def get_frame(self, frame_id: str) -> Optional[FrameCapture]:
        """Get a specific frame capture by ID."""
        for fc in self.frame_captures:
            if frame_id in fc.event_ids or fc.screenshot_path == frame_id:
                return fc
        return None

    def cleanup_screenshots(self) -> None:
        """Remove temporary screenshot files."""
        import os
        for fc in self.frame_captures:
            try:
                if os.path.exists(fc.screenshot_path):
                    os.unlink(fc.screenshot_path)
            except Exception:
                pass
        self.frame_captures.clear()

    @property
    def has_blocking_issues(self) -> bool:
        """Check if there are errors that must be fixed."""
        return len(self.errors) > 0
