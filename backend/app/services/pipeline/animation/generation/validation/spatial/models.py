"""
Data models for spatial validation issues and results.
"""

from dataclasses import dataclass, field
from typing import List


@dataclass
class SpatialIssue:
    """A single spatial layout issue (overlap, boundary, etc.)."""
    line_number: int
    severity: str  # "error", "warning", or "info"
    message: str
    code_snippet: str
    suggested_fix: str = ""  # Actionable fix suggestion for LLM


@dataclass
class SpatialValidationResult:
    """Aggregated result of spatial validation across a script."""
    valid: bool
    errors: List[SpatialIssue] = field(default_factory=list)  # Blocking, must fix
    warnings: List[SpatialIssue] = field(default_factory=list)  # Try to fix, but don't block
    info: List[SpatialIssue] = field(default_factory=list)  # Informational only, don't send to LLM
    raw_report: str = ""

    @property
    def has_blocking_issues(self) -> bool:
        """Check if there are errors that must be fixed."""
        return len(self.errors) > 0
