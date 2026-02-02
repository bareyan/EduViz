"""
Tests for SpatialValidator orchestration.
Matches backend/app/services/pipeline/animation/generation/validation/spatial/validator.py
"""

import pytest
from unittest.mock import MagicMock
from app.services.pipeline.animation.generation.validation.spatial.validator import SpatialValidator

@pytest.fixture
def validator():
    return SpatialValidator()

def test_collect_issues_text_text_overlap(validator):
    """Test severity logic: Text/Text overlap = error."""
    from app.services.pipeline.animation.generation.validation.spatial.events import LintEvent
    
    mock_scene = MagicMock()
    tracker = MagicMock()
    ev = LintEvent(MagicMock(), MagicMock(), "overlap", 0.0, "code.py", 10)
    ev.m1_type = "Text"
    ev.m2_type = "Text"
    ev.m1_name = "TextObj1"
    ev.m2_name = "TextObj2"
    ev.details = "100% overlap"
    ev.finish(10)
    
    validator.trackers[mock_scene] = tracker
    tracker.history = [ev]
    
    errors, warnings = [], []
    validator._collect_issues(mock_scene, "text1 = Text('A')\ntext2 = Text('B')", errors, warnings)
    
    assert len(errors) == 1
    assert errors[0].severity == "error"

def test_collect_issues_text_axes_overlap(validator):
    """Test severity logic: Text/Axes overlap = info."""
    from app.services.pipeline.animation.generation.validation.spatial.events import LintEvent
    
    mock_scene = MagicMock()
    tracker = MagicMock()
    ev = LintEvent(MagicMock(), MagicMock(), "overlap", 0.0, "code.py", 10)
    ev.m1_type = "Text"
    ev.m2_type = "Axes"
    ev.m1_name = "label"
    ev.m2_name = "graph"
    ev.details = "5% overlap"
    ev.finish(10)
    
    validator.trackers[mock_scene] = tracker
    tracker.history = [ev]
    
    errors, warnings = [], []
    validator._collect_issues(mock_scene, "label = Text('X')\ngraph = Axes()", errors, warnings)
    
    assert len(errors) == 0
    assert len(warnings) == 1
    assert warnings[0].severity == "info"

def test_collect_quality_heuristics(validator):
    """Test detection of font size and length issues in _collect_issues."""
    from app.services.pipeline.animation.generation.validation.spatial.events import LintEvent
    
    mock_scene = MagicMock()
    tracker = MagicMock()
    
    ev_font = LintEvent(MagicMock(), None, "font_size", 0.0, "code.py", 2)
    ev_font.m1_name = "HugeText"
    ev_font.details = "font_size 72 > 48"
    ev_font.finish(2)
    
    ev_len = LintEvent(MagicMock(), None, "length", 0.0, "code.py", 4)
    ev_len.m1_name = "LongText"
    ev_len.details = "length 150 > 60"
    ev_len.finish(4)
    
    validator.trackers[mock_scene] = tracker
    tracker.history = [ev_font, ev_len]
    
    errors, warnings = [], []
    validator._collect_issues(mock_scene, "code", errors, warnings)
    
    assert any("font size" in w.message for w in warnings)
    assert any("text too long" in w.message for w in warnings)
