
import pytest
from app.services.pipeline.animation.generation.core.validation.spatial import SpatialCheckInjector

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
