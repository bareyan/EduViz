"""
Tests for Manim imports validator

Ensures import validation works correctly.
"""

import pytest
from app.services.manim_generator.validation import ManimImportsValidator


class TestManimImportsValidator:
    """Test suite for ManimImportsValidator"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.validator = ManimImportsValidator()
    
    def test_wildcard_import_valid(self):
        """Test that wildcard import is always valid"""
        code = """
from manim import *

class MyScene(Scene):
    def construct(self):
        text = Text("Hello")
        self.play(Write(text))
"""
        result = self.validator.validate(code)
        
        assert result.valid is True
        assert result.has_wildcard is True
        assert len(result.missing_imports) == 0
    
    def test_explicit_imports_all_used(self):
        """Test valid explicit imports with all used"""
        code = """
from manim import Scene, Text, Write

class MyScene(Scene):
    def construct(self):
        text = Text("Hello")
        self.play(Write(text))
"""
        result = self.validator.validate(code)
        
        assert result.valid is True
        assert len(result.missing_imports) == 0
        assert len(result.unused_imports) == 0
    
    def test_missing_imports(self):
        """Test detection of missing imports"""
        code = """
from manim import Scene

class MyScene(Scene):
    def construct(self):
        text = Text("Hello")
        self.play(Write(text))
"""
        result = self.validator.validate(code)
        
        assert result.valid is False
        assert "Text" in result.missing_imports
        assert "Write" in result.missing_imports
    
    def test_unused_imports(self):
        """Test detection of unused imports"""
        code = """
from manim import Scene, Text, Write, Circle, Square

class MyScene(Scene):
    def construct(self):
        text = Text("Hello")
        self.play(Write(text))
"""
        result = self.validator.validate(code)
        
        assert result.valid is True  # Valid even with unused imports
        assert "Circle" in result.unused_imports
        assert "Square" in result.unused_imports
    
    def test_color_constants(self):
        """Test detection of color constant usage"""
        code = """
from manim import Scene, Text

class MyScene(Scene):
    def construct(self):
        text = Text("Hello", color=BLUE)
"""
        result = self.validator.validate(code)
        
        assert result.valid is False
        assert "BLUE" in result.missing_imports
    
    def test_animation_classes(self):
        """Test detection of animation class usage"""
        code = """
from manim import Scene, Text, FadeIn

class MyScene(Scene):
    def construct(self):
        text = Text("Hello")
        self.play(FadeIn(text))
"""
        result = self.validator.validate(code)
        
        assert result.valid is True
        assert len(result.missing_imports) == 0
    
    def test_vgroup_usage(self):
        """Test detection of VGroup usage"""
        code = """
from manim import Scene, Text

class MyScene(Scene):
    def construct(self):
        t1 = Text("A")
        t2 = Text("B")
        group = VGroup(t1, t2)
"""
        result = self.validator.validate(code)
        
        assert result.valid is False
        assert "VGroup" in result.missing_imports
    
    def test_import_with_alias(self):
        """Test imports with aliases"""
        code = """
from manim import Scene, Text as T

class MyScene(Scene):
    def construct(self):
        text = T("Hello")
"""
        result = self.validator.validate(code)
        
        # Text is imported (as T), so should be valid
        assert result.valid is True
        assert "Text" not in result.missing_imports
    
    def test_multiple_import_lines(self):
        """Test handling of multiple import statements"""
        code = """
from manim import Scene, Text
from manim import Write, FadeIn

class MyScene(Scene):
    def construct(self):
        text = Text("Hello")
        self.play(Write(text))
"""
        result = self.validator.validate(code)
        
        assert result.valid is True
        assert len(result.missing_imports) == 0
