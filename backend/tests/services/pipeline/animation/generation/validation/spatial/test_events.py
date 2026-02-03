"""
Tests for event tracking logic.
Matches backend/app/services/pipeline/animation/generation/validation/spatial/events.py
"""

import pytest
from unittest.mock import MagicMock
from app.services.pipeline.animation.generation.validation.spatial.events import LintEvent, SceneTracker

def test_event_lifecycle():
    """Test starting, updating, and finishing an event."""
    m1 = MagicMock()
    m2 = MagicMock()
    ev = LintEvent(m1, m2, "overlap", 0.0, "code.py", 10)
    
    # Update at midpoint
    m1.width = 1.0; m1.height = 1.0; m1.get_center.return_value = [0,0,0]
    m2.width = 1.0; m2.height = 1.0; m2.get_center.return_value = [0.1,0.1,0]
    
    ev.update(0.5, m1, m2)
    assert ev.duration == 0.5
    
    # Finish
    ev.finish(12)
    assert ev.end_time == 0.5
    assert ev.end_line == 12

def test_tracker_report():
    """Test generating a report from history."""
    tracker = SceneTracker()
    m = MagicMock()
    ev = LintEvent(m, None, "boundary", 0.0, "code.py", 5)
    ev.m1_name = "Circle"
    ev.finish(5)
    
    tracker.history.append(ev)
    report = tracker.generate_report_string("TestScene")
    
    assert "TestScene" in report
    assert "Circle" in report
    assert "OUT OF FRAME" in report
