"""
False Positive Whitelist

Session-scoped cache for tracking issues that Visual QC has confirmed as
non-problems. When the same issue signature appears in subsequent validation
passes, it's skipped entirely (no Visual QC call needed).

Key Design:
- Uses ValidationIssue.whitelist_key for stable identification
- Session-scoped: resets between section generations
- Prevents "learning" bad habits by being temporary

Usage:
    whitelist = FalsePositiveWhitelist()
    
    # Check if issue is whitelisted
    if whitelist.is_whitelisted(issue):
        skip_visual_qc()
    
    # After Visual QC says "not a problem"
    whitelist.add(issue)
    
    # New section? Reset the whitelist
    whitelist.reset()
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set

from app.core import get_logger
from ..core.validation.models import ValidationIssue

logger = get_logger(__name__, component="false_positive_whitelist")


@dataclass
class FalsePositiveWhitelist:
    """
    Session-scoped cache for tracking confirmed false positives.
    
    When Visual QC determines an uncertain issue is NOT a real problem,
    we add its key to this whitelist. Future validation passes will
    skip Visual QC for matching issues.
    """
    
    _entries: Set[str] = field(default_factory=set)
    _metadata: Dict[str, str] = field(default_factory=dict)  # key -> original message
    
    def reset(self) -> None:
        """Clear all whitelist entries. Call at the start of a new section."""
        count = len(self._entries)
        self._entries.clear()
        self._metadata.clear()
        if count > 0:
            logger.info(f"Whitelist reset (cleared {count} entries)")
    
    def add(self, issue: ValidationIssue) -> None:
        """Add an issue to the whitelist (Visual QC confirmed as false positive)."""
        key = issue.whitelist_key
        if key not in self._entries:
            self._entries.add(key)
            self._metadata[key] = issue.message[:80]
            logger.debug(f"Whitelisted: {key} ({issue.message[:50]}...)")
    
    def add_all(self, issues: List[ValidationIssue]) -> None:
        """Add multiple issues to the whitelist."""
        for issue in issues:
            self.add(issue)
    
    def is_whitelisted(self, issue: ValidationIssue) -> bool:
        """Check if an issue has been whitelisted as a false positive."""
        return issue.whitelist_key in self._entries
    
    def filter_uncertain(
        self,
        issues: List[ValidationIssue],
    ) -> tuple[List[ValidationIssue], List[ValidationIssue]]:
        """Partition uncertain issues into new (need QC) vs whitelisted (skip).
        
        Args:
            issues: List of uncertain issues to check
            
        Returns:
            Tuple of (need_qc, already_whitelisted)
        """
        need_qc: List[ValidationIssue] = []
        whitelisted: List[ValidationIssue] = []
        
        for issue in issues:
            if self.is_whitelisted(issue):
                whitelisted.append(issue)
            else:
                need_qc.append(issue)
        
        if whitelisted:
            logger.info(
                f"Skipping {len(whitelisted)} whitelisted false positives"
            )
        
        return need_qc, whitelisted
    
    @property
    def count(self) -> int:
        """Number of whitelisted issue keys."""
        return len(self._entries)
    
    def __contains__(self, issue: ValidationIssue) -> bool:
        """Enable `if issue in whitelist` syntax."""
        return self.is_whitelisted(issue)
