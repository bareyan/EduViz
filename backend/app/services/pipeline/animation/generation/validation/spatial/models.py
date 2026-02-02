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
    errors: List[SpatialIssue] = field(default_factory=list)
    warnings: List[SpatialIssue] = field(default_factory=list)
    raw_report: str = ""

    @property
    def has_issues(self) -> bool:
        """Check if any noteworthy items were found."""
        return len(self.errors) > 0 or len(self.warnings) > 0
