"""
Unit Tests for Spatial Validation (via Runtime Injection)
"""
import pytest
from app.services.pipeline.animation.generation.core.validation.runtime import RuntimeValidator

# Sample valid spatial code
VALID_SPATIAL_CODE = """
from manim import *

class TestScene(Scene):
    def construct(self):
        # Perfectly safe positions
        c = Circle().move_to(LEFT * 2)
        s = Square().move_to(RIGHT * 2)
        self.add(c, s)
"""

# Sample code with Out of Bounds (X > 7.1)
OUT_OF_BOUNDS_CODE = """
from manim import *

class TestScene(Scene):
    def construct(self):
        # Move way out of frame
        c = Circle().move_to(RIGHT * 8.0) 
        self.add(c)
"""

# Sample code with Text Overlap
TEXT_OVERLAP_CODE = """
from manim import *

class TestScene(Scene):
    def construct(self):
        t1 = Text("Hello").move_to(ORIGIN)
        t2 = Text("World").move_to(ORIGIN) # Exact overlap
        self.add(t1, t2)
"""

@pytest.mark.asyncio
class TestSpatialValidator:
    async def test_spatial_valid(self):
        validator = RuntimeValidator()
        result = await validator.validate(VALID_SPATIAL_CODE, enable_spatial_checks=True)
        assert result.valid
        assert not result.errors

    async def test_spatial_out_of_bounds(self):
        validator = RuntimeValidator()
        result = await validator.validate(OUT_OF_BOUNDS_CODE, enable_spatial_checks=True)
        assert not result.valid
        # We expect "Spatial Error" and "out of bounds"
        assert any("Spatial Error" in e and "out of bounds" in e for e in result.errors)

    async def test_spatial_text_overlap(self):
        validator = RuntimeValidator()
        result = await validator.validate(TEXT_OVERLAP_CODE, enable_spatial_checks=True)
        assert not result.valid
        # We expect "Spatial Error" and "Text overlap"
        assert any("Spatial Error" in e and "Text overlap" in e for e in result.errors)

    async def test_spatial_edge_case_vgroup(self):
        # Edge case: VGroup where content is strictly out of bounds
        code = """
from manim import *
class TestScene(Scene):
    def construct(self):
        # Center is at 6.0 (safe), but radius is 2.0 -> Right edge at 8.0 (FAIL)
        c = Circle(radius=2.0).move_to(RIGHT * 6.0)
        g = VGroup(c)
        self.add(g)
"""
        validator = RuntimeValidator()
        result = await validator.validate(code, enable_spatial_checks=True)
        assert not result.valid
        assert any("out of bounds" in e for e in result.errors)

    async def test_spatial_exact_boundary(self):
        # Edge case: Object exactly at limit (should fail if center + extent > limit)
        # Limit 7.1. Center 7.0. Width 0.2 -> Right edge 7.1. (PASS)
        # Center 7.01. Width 0.2 -> Right edge 7.11 (FAIL)
        code = """
from manim import *
class TestScene(Scene):
    def construct(self):
        # Center 7.05, Radius 0.1 -> Edge 7.15 (Limit 7.1)
        c = Circle(radius=0.1).move_to(RIGHT * 7.05)
        self.add(c)
"""
        validator = RuntimeValidator()
        result = await validator.validate(code, enable_spatial_checks=True)
        assert not result.valid
        assert any("out of bounds" in e for e in result.errors)
