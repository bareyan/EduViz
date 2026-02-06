
import pytest
from app.services.pipeline.animation.generation.refinement.false_positive_whitelist import FalsePositiveWhitelist
from app.services.pipeline.animation.generation.core.validation.models import ValidationIssue, IssueSeverity, IssueConfidence, IssueCategory

def test_whitelist_add_check():
    wl = FalsePositiveWhitelist()
    i1 = ValidationIssue(IssueSeverity.WARNING, IssueConfidence.LOW, IssueCategory.TEXT_OVERLAP, "msg")
    
    assert wl.is_whitelisted(i1) is False
    
    wl.add(i1)
    assert wl.is_whitelisted(i1) is True
    assert i1 in wl # Test __contains__

def test_whitelist_reset():
    wl = FalsePositiveWhitelist()
    i1 = ValidationIssue(IssueSeverity.WARNING, IssueConfidence.LOW, IssueCategory.TEXT_OVERLAP, "msg")
    wl.add(i1)
    
    wl.reset()
    assert wl.is_whitelisted(i1) is False
    assert wl.count == 0

def test_filter_uncertain():
    wl = FalsePositiveWhitelist()
    i1 = ValidationIssue(IssueSeverity.WARNING, IssueConfidence.LOW, IssueCategory.TEXT_OVERLAP, "msg")
    i2 = ValidationIssue(IssueSeverity.WARNING, IssueConfidence.LOW, IssueCategory.VISIBILITY, "msg2")
    
    wl.add(i1)
    
    uncertain_issues = [i1, i2]
    need_qc, whitelisted = wl.filter_uncertain(uncertain_issues)
    
    assert len(need_qc) == 1
    assert need_qc[0] == i2
    assert len(whitelisted) == 1
    assert whitelisted[0] == i1
