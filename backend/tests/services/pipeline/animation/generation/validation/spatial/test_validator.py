"""
Tests for SpatialValidator orchestration and IssueReporter logic.
"""

import pytest
from unittest.mock import MagicMock
from app.services.pipeline.animation.generation.validation.spatial.validator import SpatialValidator
from app.services.pipeline.animation.generation.validation.spatial.reporters import IssueReporter
from app.services.pipeline.animation.generation.validation.spatial.events import LintEvent

@pytest.fixture
def validator():
    return SpatialValidator()

def test_issue_reporter_text_text_overlap():
    """Test severity logic: Text/Text overlap = error."""
    code = "text1 = Text('A')\ntext2 = Text('B')"
    reporter = IssueReporter(code)
    
    ev = LintEvent(MagicMock(), MagicMock(), "overlap", 0.0, "code.py", 1)
    ev.m1_type = "Text"
    ev.m2_type = "Text"
    ev.m1_name = "TextObj1"
    ev.m2_name = "TextObj2"
    ev.details = "100% overlap"
    ev.finish(1)
    
    errors, warnings, info = [], [], []
    reporter.collect_issues([ev], errors, warnings, info)
    
    assert len(errors) == 1
    assert errors[0].severity == "error"
    assert "overlaps" in errors[0].message
    assert "Separate with .shift" in errors[0].suggested_fix

def test_issue_reporter_text_axes_overlap():
    """Test severity logic: Text/Axes overlap = info."""
    code = "label = Text('X')\ngraph = Axes()"
    reporter = IssueReporter(code)
    
    ev = LintEvent(MagicMock(), MagicMock(), "overlap", 0.0, "code.py", 1)
    ev.m1_type = "Text"
    ev.m2_type = "Axes"
    ev.m1_name = "label"
    ev.m2_name = "graph"
    ev.details = "5% overlap"
    ev.finish(1)
    
    errors, warnings, info = [], [], []
    reporter.collect_issues([ev], errors, warnings, info)
    
    assert len(errors) == 0
    assert len(info) == 1
    assert info[0].severity == "info"

def test_issue_reporter_quality_heuristics():
    """Test detection of font size and length issues in IssueReporter."""
    code = "text = Text('Huge')"
    reporter = IssueReporter(code)
    
    ev_font = LintEvent(MagicMock(), None, "font_size", 0.0, "code.py", 1)
    ev_font.m1_name = "HugeText"
    ev_font.details = "font_size 72 > 48"
    ev_font.finish(1)
    
    ev_len = LintEvent(MagicMock(), None, "length", 0.0, "code.py", 1)
    ev_len.m1_name = "LongText"
    ev_len.details = "length 150 > 60"
    ev_len.finish(1)
    
    errors, warnings, info = [], [], []
    reporter.collect_issues([ev_font, ev_len], errors, warnings, info)
    
    assert any("font size" in w.message for w in warnings)
    assert any("text too long" in w.message for w in warnings)

def test_issue_reporter_boundary_violation():
    """Test boundary violation reporting."""
    code = "text = Text('Offscreen')"
    reporter = IssueReporter(code)
    
    ev = LintEvent(MagicMock(), None, "boundary", 1.0, "code.py", 1)
    ev.m1_name = "OffscreenObj"
    ev.details = "Out of bounds on Right"
    ev.finish(1)
    
    errors, warnings, info = [], [], []
    reporter.collect_issues([ev], errors, warnings, info)
    
    assert len(errors) == 1
    assert "out of bounds" in errors[0].message
    assert "Shift left" in errors[0].suggested_fix

def test_validator_initialization(validator):
    """Check that engine is initialized."""
    assert validator.engine is not None
    assert validator.linter_path.endswith("validator.py")
