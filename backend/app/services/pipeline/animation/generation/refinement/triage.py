"""Issue Router and Triage logic for the animation pipeline.

Adheres to SRP by separating the "decision making" (routing) from the 
"orchestration" (Refiner) and "action" (Fixers).
"""

from typing import List, Tuple, Dict, Any, Optional, Callable
from app.core import get_logger
from app.services.pipeline.animation.generation.core.validation.models import ValidationIssue, IssueCategory
from app.utils.section_status import SectionState

logger = get_logger(__name__, component="issue_router")

class IssueRouter:
    """Routes validation issues to appropriate handlers (deterministic, LLM, or Visual QC)."""

    def triage_issues(
        self,
        issues: List[ValidationIssue],
        whitelist_filter: Optional[Callable[[List[ValidationIssue]], Tuple[List[ValidationIssue], List[ValidationIssue]]]] = None
    ) -> Dict[str, List[ValidationIssue]]:
        """Partition issues based on certainty and fixability.
        
        Returns a dict:
            certain_auto_fixable: List[ValidationIssue]
            certain_llm_needed: List[ValidationIssue]
            uncertain: List[ValidationIssue]
            whitelisted: List[ValidationIssue]
        """
        certain_auto_fixable = [i for i in issues if i.is_certain and i.should_auto_fix]
        certain_llm_needed = [i for i in issues if i.is_certain and i.requires_llm]
        uncertain_raw = [i for i in issues if i.is_uncertain]
        
        need_visual_qc = uncertain_raw
        whitelisted = []
        
        if whitelist_filter:
            need_visual_qc, whitelisted = whitelist_filter(uncertain_raw)

        return {
            "certain_auto_fixable": certain_auto_fixable,
            "certain_llm_needed": certain_llm_needed,
            "uncertain": need_visual_qc,
            "whitelisted": whitelisted,
        }

    @staticmethod
    def only_spatial_remaining(issues: List[ValidationIssue]) -> bool:
        """Check if only spatial issues remain (safe to proceed to render)."""
        if not issues:
            return True
        return all(issue.is_spatial for issue in issues)

    @staticmethod
    def summarize_triage(partitions: Dict[str, List[ValidationIssue]]) -> Dict[str, int]:
        """Convert partitioned issues into a count summary."""
        return {k: len(v) for k, v in partitions.items()}
