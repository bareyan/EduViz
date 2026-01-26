"""
Tests for Manim structure validator

Ensures Manim-specific structure validation works correctly.
"""

import pytest
from app.services.manim_generator.validation import ManimStructureValidator


class TestManimStructureValidator:
    """Test suite for ManimStructureValidator"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.validator = ManimStructureValidator()
    
    def test_valid_manim_scene(self):
        """Test validation of valid Manim scene"""
        code = """
from manim import *

class MyScene(Scene):
    def construct(self):
        text = Text("Hello", font_size=36)
        self.play(Write(text))
        self.wait()
"""
        result = self.validator.validate(code)
        
        assert result.valid is True
        assert len(result.errors) == 0
    
    def test_missing_scene_class(self):
        """Test detection of missing Scene class"""
        code = """
def construct():
    text = Text("Hello")
"""
        result = self.validator.validate(code)
        
        assert result.valid is False
        assert any("Scene" in err for err in result.errors)
    
    def test_missing_construct_method(self):
        """Test detection of missing construct method"""
        code = """
from manim import *

class MyScene(Scene):
    def render(self):
        text = Text("Hello")
"""
        result = self.validator.validate(code)
        
        assert result.valid is False
        assert any("construct" in err for err in result.errors)
    
    def test_background_color_warning(self):
        """Test warning for background_color setting"""
        code = """
from manim import *

class MyScene(Scene):
    def construct(self):
        self.camera.background_color = BLUE
        text = Text("Hello")
"""
        result = self.validator.validate(code)
        
        # Still valid, but should have warning
        assert result.valid is True
        assert len(result.warnings) > 0
        assert any("background" in warn.lower() for warn in result.warnings)
    
    def test_excessive_font_size_warning(self):
        """Test warning for font size > 48"""
        code = """
from manim import *

class MyScene(Scene):
    def construct(self):
        text = Text("Hello", font_size=60)
        self.play(Write(text))
"""
        result = self.validator.validate(code)
        
        assert result.valid is True
        assert len(result.warnings) > 0
        assert any("60" in warn and "font" in warn.lower() for warn in result.warnings)
    
    def test_large_font_size_warning(self):
        """Test warning for font size > 36 but < 48"""
        code = """
from manim import *

class MyScene(Scene):
    def construct(self):
        text = Text("Hello", font_size=42)
"""
        result = self.validator.validate(code)
        
        assert result.valid is True
        assert len(result.warnings) > 0
        assert any("42" in warn for warn in result.warnings)
    
    def test_acceptable_font_size_no_warning(self):
        """Test no warning for reasonable font size"""
        code = """
from manim import *

class MyScene(Scene):
    def construct(self):
        text = Text("Hello", font_size=36)
"""
        result = self.validator.validate(code)
        
        assert result.valid is True
        # Should have no font size warnings
        font_warnings = [w for w in result.warnings if "font" in w.lower()]
        assert len(font_warnings) == 0
    
    def test_long_text_warning(self):
        """Test warning for overly long text strings"""
        long_text = "A" * 70  # Over 60 character limit
        code = f'''
from manim import *

class MyScene(Scene):
    def construct(self):
        text = Text("{long_text}")
'''
        result = self.validator.validate(code)
        
        assert result.valid is True
        assert len(result.warnings) > 0
        assert any("too long" in warn.lower() for warn in result.warnings)
    
    def test_missing_wait_warning(self):
        """Test warning for animations without wait()"""
        code = """
from manim import *

class MyScene(Scene):
    def construct(self):
        text = Text("Hello")
        self.play(Write(text))
"""
        result = self.validator.validate(code)
        
        assert result.valid is True
        assert len(result.warnings) > 0
        assert any("wait" in warn.lower() for warn in result.warnings)
    
    def test_with_wait_no_warning(self):
        """Test no warning when wait() is present"""
        code = """
from manim import *

class MyScene(Scene):
    def construct(self):
        text = Text("Hello")
        self.play(Write(text))
        self.wait()
"""
        result = self.validator.validate(code)
        
        assert result.valid is True
        # Should have no wait-related warnings
        wait_warnings = [w for w in result.warnings if "wait" in w.lower()]
        assert len(wait_warnings) == 0
