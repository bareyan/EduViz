
from app.services.pipeline.animation.generation.core.validation.models import (
    ValidationIssue,
    IssueSeverity,
    IssueConfidence,
    IssueCategory
)

def test_validation_issue_certainty():
    # High confidence -> Certain
    i1 = ValidationIssue(IssueSeverity.WARNING, IssueConfidence.HIGH, IssueCategory.TEXT_OVERLAP, "msg")
    assert i1.is_certain is True
    assert i1.is_uncertain is False
    
    # Critical + Medium -> Certain
    i2 = ValidationIssue(IssueSeverity.CRITICAL, IssueConfidence.MEDIUM, IssueCategory.TEXT_OVERLAP, "msg")
    assert i2.is_certain is True
    
    # Warning + Medium -> Uncertain (if spatial)
    i3 = ValidationIssue(IssueSeverity.WARNING, IssueConfidence.MEDIUM, IssueCategory.TEXT_OVERLAP, "msg")
    assert i3.is_certain is False
    assert i3.is_uncertain is True

    # Low confidence -> Uncertain
    i4 = ValidationIssue(IssueSeverity.WARNING, IssueConfidence.LOW, IssueCategory.TEXT_OVERLAP, "msg")
    assert i4.is_uncertain is True

def test_validation_issue_auto_fix():
    # Certain + AutoFixable -> Should Auto Fix
    i1 = ValidationIssue(
        IssueSeverity.CRITICAL, 
        IssueConfidence.HIGH, 
        IssueCategory.TEXT_OVERLAP, 
        "msg", 
        auto_fixable=True
    )
    assert i1.should_auto_fix is True
    assert i1.requires_llm is False

    # Certain + Not AutoFixable -> Requires LLM
    i2 = ValidationIssue(
        IssueSeverity.CRITICAL, 
        IssueConfidence.HIGH, 
        IssueCategory.TEXT_OVERLAP, 
        "msg", 
        auto_fixable=False
    )
    assert i2.should_auto_fix is False
    assert i2.requires_llm is True

def test_whitelist_key():
    i1 = ValidationIssue(
        IssueSeverity.WARNING, 
        IssueConfidence.LOW, 
        IssueCategory.TEXT_OVERLAP, 
        "msg",
        details={"obj": "Text", "ratio": 0.15}
    )
    key1 = i1.whitelist_key
    
    # Same details -> Same key
    i2 = ValidationIssue(
        IssueSeverity.WARNING, 
        IssueConfidence.LOW, 
        IssueCategory.TEXT_OVERLAP, 
        "msg",
        details={"obj": "Text", "ratio": 0.15}
    )
    assert i1.whitelist_key == i2.whitelist_key
    
    # Different details -> Different key
    i3 = ValidationIssue(
        IssueSeverity.WARNING, 
        IssueConfidence.LOW, 
        IssueCategory.TEXT_OVERLAP, 
        "msg",
        details={"obj": "Text", "ratio": 0.25}
    )
    assert i1.whitelist_key != i3.whitelist_key

def test_to_fixer_context():
    i1 = ValidationIssue(
        IssueSeverity.CRITICAL, 
        IssueConfidence.HIGH, 
        IssueCategory.TEXT_OVERLAP, 
        "Bad overlap",
        fix_hint="Move it",
        line=10
    )
    ctx = i1.to_fixer_context()
    assert "[text_overlap/critical] Bad overlap (Line 10)" in ctx
    assert "Suggested approach: Move it" in ctx
