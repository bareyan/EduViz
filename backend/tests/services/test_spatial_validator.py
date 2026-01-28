"""
Tests for spatial layout validator

Ensures spatial validation catches overlapping and out-of-bounds issues.
"""

import pytest
from app.services.pipeline.animation.generation.validation.spatial_validator import (
    SpatialValidator,
    format_spatial_issues
)


class TestSpatialValidator:
    """Test suite for SpatialValidator"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.validator = SpatialValidator()
    
    def test_valid_positioned_code(self):
        """Test code with properly positioned objects"""
        code = """
from manim import *

class MyScene(Scene):
    def construct(self):
        text1 = Text("Top").move_to([0, 2, 0])
        text2 = Text("Bottom").move_to([0, -2, 0])
        self.play(Write(text1), Write(text2))
"""
        result = self.validator.validate(code)
        
        assert result.valid is True
        assert len(result.errors) == 0
    
    def test_out_of_bounds_x_coordinate(self):
        """Test detection of X coordinate out of bounds"""
        code = """
from manim import *

class MyScene(Scene):
    def construct(self):
        text = Text("Far Right").move_to([10, 0, 0])
        self.play(Write(text))
"""
        result = self.validator.validate(code)
        
        assert result.valid is False
        assert len(result.errors) > 0
        assert any("out of screen bounds" in e.message for e in result.errors)
        assert any("10" in e.message for e in result.errors)
    
    def test_out_of_bounds_y_coordinate(self):
        """Test detection of Y coordinate out of bounds"""
        code = """
from manim import *

class MyScene(Scene):
    def construct(self):
        text = Text("Too High").move_to([0, 5, 0])
        self.play(Write(text))
"""
        result = self.validator.validate(code)
        
        assert result.valid is False
        assert len(result.errors) > 0
        assert any("5" in e.message and "Y coordinate" in e.message for e in result.errors)
    
    def test_objects_too_close_warning(self):
        """Test warning for objects positioned very close together"""
        code = """
from manim import *

class MyScene(Scene):
    def construct(self):
        text1 = Text("A").move_to([0, 0, 0])
        text2 = Text("B").move_to([0.1, 0.1, 0])
        self.play(Write(text1), Write(text2))
"""
        result = self.validator.validate(code)
        
        # Valid (no errors) but has warnings
        assert result.valid is True
        assert len(result.warnings) > 0
        assert any("very close" in w.message for w in result.warnings)
    
    def test_long_text_overflow_warning(self):
        """Test warning for text that might overflow"""
        long_text = "A" * 150
        code = f"""
from manim import *

class MyScene(Scene):
    def construct(self):
        text = Text("{long_text}", font_size=36)
        self.play(Write(text))
"""
        result = self.validator.validate(code)
        
        assert result.valid is True  # Warning, not error
        assert len(result.warnings) > 0
        assert any("overflow" in w.message for w in result.warnings)
    
    def test_multiple_unpositioned_texts(self):
        """Test warning for multiple texts without positioning"""
        code = """
from manim import *

class MyScene(Scene):
    def construct(self):
        text1 = Text("Hello")
        text2 = Text("World")
        text3 = Text("Overlap")
        self.play(Write(text1))
        self.play(Write(text2))
        self.play(Write(text3))
"""
        result = self.validator.validate(code)
        
        assert result.valid is True  # Warning, not error
        assert len(result.warnings) > 0
        assert any("unpositioned" in w.message.lower() for w in result.warnings)
        assert any("overlap" in w.message.lower() for w in result.warnings)
    
    def test_positioned_texts_no_warning(self):
        """Test no warning when texts are properly positioned"""
        code = """
from manim import *

class MyScene(Scene):
    def construct(self):
        text1 = Text("Hello").to_edge(UP)
        text2 = Text("World").to_edge(DOWN)
        text3 = Text("Side").next_to(text1, RIGHT)
        self.play(Write(text1), Write(text2), Write(text3))
"""
        result = self.validator.validate(code)
        
        assert result.valid is True
        # Should not warn about unpositioned texts
        unpositioned_warnings = [w for w in result.warnings if "unpositioned" in w.message.lower()]
        assert len(unpositioned_warnings) == 0
    
    def test_shift_out_of_bounds(self):
        """Test detection of shift that goes out of bounds"""
        code = """
from manim import *

class MyScene(Scene):
    def construct(self):
        text = Text("Hello").shift([8, 0, 0])
        self.play(Write(text))
"""
        result = self.validator.validate(code)
        
        assert result.valid is False
        assert len(result.errors) > 0
    
    def test_within_bounds_no_errors(self):
        """Test that coordinates within bounds don't trigger errors"""
        code = """
from manim import *

class MyScene(Scene):
    def construct(self):
        text1 = Text("Top").move_to([0, 3, 0])
        text2 = Text("Left").move_to([-5, 0, 0])
        text3 = Text("Right").move_to([5, 0, 0])
        text4 = Text("Bottom").move_to([0, -3, 0])
"""
        result = self.validator.validate(code)
        
        assert result.valid is True
        assert len(result.errors) == 0
    
    def test_format_spatial_issues_no_issues(self):
        """Test formatting when there are no issues"""
        code = """
from manim import *

class MyScene(Scene):
    def construct(self):
        text = Text("Hello").move_to([0, 0, 0])
"""
        result = self.validator.validate(code)
        formatted = format_spatial_issues(result)
        
        assert "No spatial layout issues" in formatted
    
    def test_format_spatial_issues_with_errors(self):
        """Test formatting with errors and warnings"""
        code = """
from manim import *

class MyScene(Scene):
    def construct(self):
        text1 = Text("Out").move_to([10, 0, 0])
        text2 = Text("A")
        text3 = Text("B")
"""
        result = self.validator.validate(code)
        formatted = format_spatial_issues(result)
        
        assert "ERRORS:" in formatted or "WARNINGS:" in formatted
        assert len(formatted) > 0
