
import pytest
from app.services.pipeline.animation.generation.refinement.triage import IssueRouter
from app.services.pipeline.animation.generation.core.validation.models import ValidationIssue, IssueSeverity, IssueConfidence, IssueCategory

def test_triage_partitions():
    router = IssueRouter()
    
    # 1. Certain + AutoFix
    i1 = ValidationIssue(IssueSeverity.CRITICAL, IssueConfidence.HIGH, IssueCategory.TEXT_OVERLAP, "msg", auto_fixable=True)
    # 2. Certain + LLM
    i2 = ValidationIssue(IssueSeverity.CRITICAL, IssueConfidence.HIGH, IssueCategory.SYNTAX, "msg", auto_fixable=False)
    # 3. Uncertain
    i3 = ValidationIssue(IssueSeverity.WARNING, IssueConfidence.LOW, IssueCategory.TEXT_OVERLAP, "msg")

    issues = [i1, i2, i3]
    
    partitions = router.triage_issues(issues)
    
    assert i1 in partitions["certain_auto_fixable"]
    assert i2 in partitions["certain_llm_needed"]
    assert i3 in partitions["uncertain"]
    assert len(partitions["whitelisted"]) == 0

def test_triage_with_whitelist_filter():
    router = IssueRouter()
    i1 = ValidationIssue(IssueSeverity.WARNING, IssueConfidence.LOW, IssueCategory.TEXT_OVERLAP, "msg")
    
    # Mock whitelist filter
    def mock_filter(issues):
        # All form uncertain are whitelisted
        return [], issues
        
    partitions = router.triage_issues([i1], whitelist_filter=mock_filter)
    
    assert len(partitions["uncertain"]) == 0
    assert len(partitions["whitelisted"]) == 1

def test_only_spatial_remaining():
    # Only spatial
    i1 = ValidationIssue(IssueSeverity.WARNING, IssueConfidence.HIGH, IssueCategory.TEXT_OVERLAP, "msg")
    assert IssueRouter.only_spatial_remaining([i1]) is True
    
    # Mixed
    i2 = ValidationIssue(IssueSeverity.CRITICAL, IssueConfidence.HIGH, IssueCategory.SYNTAX, "msg")
    assert IssueRouter.only_spatial_remaining([i1, i2]) is False
