"""
Tests for StaticValidator (AST analysis).
Matches backend/app/services/pipeline/animation/generation/validation/static_validator.py
"""

import pytest
from app.services.pipeline.animation.generation.validation.static_validator import StaticValidator

@pytest.fixture
def validator():
    return StaticValidator()

def test_clean_run(validator):
    """Test valid code passes with no issues."""
    code = '''from manim import *
class MyScene(Scene):
    def construct(self):
        self.play(Write(Text("Hello")))
'''
    result = validator.validate(code)
    assert result.valid is True
    assert not result.errors
    assert not result.warnings

def test_syntax_error(validator):
    """Test invalid Python syntax is caught."""
    code = "class MyScene(Scene):\n    def construct(self):\n        self.play(Write(Text('unclosed string)"
    result = validator.validate(code)
    assert result.valid is False
    assert any("Syntax Error" in e for e in result.errors)
    assert result.line_number == 3

def test_missing_scene_subclass(validator):
    """Test code without a Scene subclass is flagged."""
    code = "import manim\nprint('just code')"
    result = validator.validate(code)
    assert result.valid is False
    assert any("must define at least one class inheriting" in e for e in result.errors)

def test_missing_construct_method(validator):
    """Test Scene class without construct() method is flagged."""
    code = '''from manim import *
class MyScene(Scene):
    def other_method(self):
        pass
'''
    result = validator.validate(code)
    assert result.valid is False
    assert any("missing the 'construct(self)' method" in e for e in result.errors)

def test_forbidden_background_color(validator):
    """Test setting background_color generates a warning."""
    code = '''from manim import *
class MyScene(Scene):
    def construct(self):
        self.camera.background_color = WHITE
        self.wait(1)
'''
    result = validator.validate(code)
    assert result.valid is True
    assert any("background_color" in w for w in result.warnings)
