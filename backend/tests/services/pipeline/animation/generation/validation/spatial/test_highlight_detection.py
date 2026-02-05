"""
Tests for highlight box detection heuristics.
"""

from types import SimpleNamespace

import numpy as np
import pytest

from app.services.pipeline.animation.generation.validation.spatial.events import SceneTracker
from app.services.pipeline.animation.generation.validation.spatial.reporters import IssueReporter
from app.services.pipeline.animation.generation.validation.spatial.validator import SpatialValidator
from app.services.pipeline.animation.generation.validation.spatial import highlight_boxes as highlight_boxes_module


class FakeRenderer:
    def __init__(self, time=1.0):
        self.time = time

    def get_frame(self):
        return np.zeros((10, 10, 3), dtype=np.uint8)


class FakeScene:
    def __init__(self, mobjects):
        self.mobjects = mobjects
        self.renderer = FakeRenderer()


class FakeMobject:
    def __init__(self, width=1.0, height=1.0, center=(0.0, 0.0, 0.0), stroke_width=1, fill_opacity=0.0):
        self.width = width
        self.height = height
        self._center = np.array(center, dtype=float)
        self.stroke_width = stroke_width
        self.fill_opacity = fill_opacity

    def get_center(self):
        return self._center


class Text(FakeMobject):
    pass


class Rectangle(FakeMobject):
    pass


class SurroundingRectangle(Rectangle):
    pass


class Create:
    def __init__(self, mobject):
        self.mobject = mobject


class Indicate:
    def __init__(self, mobject):
        self.mobject = mobject


@pytest.fixture
def validator():
    v = SpatialValidator()
    v.engine.config = SimpleNamespace(frame_width=14.0, frame_height=8.0)
    v._highlight_miss_seen.clear()
    return v


def _patch_atomic(monkeypatch):
    monkeypatch.setattr(highlight_boxes_module, "get_atomic_mobjects", lambda m, classes: [m])


def test_highlight_box_overlaps_text_no_warning(validator, monkeypatch):
    _patch_atomic(monkeypatch)

    text = Text(width=1.0, height=0.5, center=(0.0, 0.0, 0.0))
    box = Rectangle(width=1.2, height=0.7, center=(0.0, 0.0, 0.0), stroke_width=4, fill_opacity=0.1)
    scene = FakeScene([text, box])

    validator.trackers[scene] = SceneTracker()
    validator.trackers[scene]._scene = scene

    events, captures = validator.highlight_checker.detect(scene, (Create(box),), triggering_line=10)
    assert events
    assert any(ev.event_type == "highlight_target" for ev in events)
    assert not any(ev.event_type == "highlight_miss" for ev in events)
    for ev in events:
        if ev.frame_id:
            import os
            if os.path.exists(ev.frame_id):
                os.remove(ev.frame_id)


def test_highlight_box_miss_emits_warning(validator, monkeypatch):
    _patch_atomic(monkeypatch)

    text = Text(width=1.0, height=0.5, center=(0.0, 0.0, 0.0))
    box = Rectangle(width=1.2, height=0.7, center=(3.0, 3.0, 0.0), stroke_width=4, fill_opacity=0.1)
    scene = FakeScene([text, box])

    validator.trackers[scene] = SceneTracker()
    validator.trackers[scene]._scene = scene

    events, captures = validator.highlight_checker.detect(scene, (Create(box),), triggering_line=12)

    reporter = IssueReporter(code="")
    errors, warnings, info = [], [], []
    reporter.collect_issues(events, errors, warnings, info)

    assert len(warnings) == 1
    assert warnings[0].frame_id is not None
    if warnings[0].frame_id:
        import os
        if os.path.exists(warnings[0].frame_id):
            os.remove(warnings[0].frame_id)


def test_indicate_offscreen_target_warns(validator, monkeypatch):
    _patch_atomic(monkeypatch)

    target = Text(width=1.0, height=0.5, center=(10.0, 0.0, 0.0))
    scene = FakeScene([target])

    validator.trackers[scene] = SceneTracker()
    validator.trackers[scene]._scene = scene

    validator._detect_highlight_misses(scene, (Indicate(target),), triggering_line=20)

    assert any(ev.event_type == "highlight_miss" for ev in validator.trackers[scene].history)
    for ev in validator.trackers[scene].history:
        if ev.frame_id:
            import os
            if os.path.exists(ev.frame_id):
                os.remove(ev.frame_id)
