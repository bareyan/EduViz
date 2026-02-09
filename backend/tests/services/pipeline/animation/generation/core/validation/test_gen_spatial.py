
import pytest
from app.services.pipeline.animation.generation.core.validation.spatial import (
    INJECTED_METHOD,
    SpatialCheckInjector,
)

def test_inject_adds_spatial_checks():
    injector = SpatialCheckInjector()
    code = """
from manim import *
class MyScene(Scene):
    def construct(self):
        c = Circle()
        self.play(Create(c))
"""
    injected_code = injector.inject(code)
    
    assert "_perform_spatial_checks" in injected_code
    assert "SPATIAL_ISSUES_JSON" in injected_code
    # Monkey patch check
    assert "self._original_play = self.play" in injected_code
    assert "filled_shape_dominance" in injected_code
    assert "text_edge_clipping" in injected_code
    assert "stroke_through_text" in injected_code
    assert "long_equation_baseline_collision" in injected_code

def test_inject_failure_returns_original():
    injector = SpatialCheckInjector()
    bad_code = "this is not python"
    
    res = injector.inject(bad_code)
    assert res == bad_code

def test_find_scene_class():
    injector = SpatialCheckInjector()
    
    # explicit Scene inherit
    code1 = "class MyScene(Scene): pass"
    tree1 = injector._parse(code1)
    assert injector._find_scene_class(tree1).name == "MyScene"
    
    # construct method presence
    code2 = "class Foo:\n def construct(self): pass"
    tree2 = injector._parse(code2)
    assert injector._find_scene_class(tree2).name == "Foo"


def test_injected_text_oob_is_not_tolerated():
    assert "TEXT_OVERSHOOT_THRESHOLD = 0.0" in INJECTED_METHOD
    assert 'sev = "critical" if is_text_obj else "warning"' in INJECTED_METHOD
    assert "subject_label = _subject_label(m, is_text_obj=is_text_obj, text_label=text_label)" in INJECTED_METHOD
    assert "object_subject=subject_label" in INJECTED_METHOD


def test_injected_flattener_skips_text_glyph_submobjects():
    assert "_is_text_like = (\"Text\" in _name) or (\"Tex\" in _name) or hasattr(m, \"text\")" in INJECTED_METHOD
    assert "if _is_text_like:" in INJECTED_METHOD


def test_injected_stroke_crossing_is_active():
    assert "STROKE_THROUGH_RATIO = 0.12" in INJECTED_METHOD
    assert "STROKE_TEXT_NEAR_GAP = 0.08" in INJECTED_METHOD
    assert "def _stroke_path_hits_text" in INJECTED_METHOD
    assert "def _bbox_distance" in INJECTED_METHOD
    assert "path_crosses_text = _stroke_path_hits_text(t, o)" in INJECTED_METHOD
    assert "near_collision = (" in INJECTED_METHOD
    assert "if fill_op is not None and fill_op > 0.2 and not is_line_like:" in INJECTED_METHOD
    assert "\"Arrow\" in obj_type" in INJECTED_METHOD
    assert "\"Axes\" in obj_type" in INJECTED_METHOD
