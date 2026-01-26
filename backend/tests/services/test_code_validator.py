"""
Tests for composite code validator

Ensures the orchestrating validator works correctly.
"""

import pytest
from app.services.manim_generator.validation import CodeValidator


class TestCodeValidator:
    """Test suite for CodeValidator"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.validator = CodeValidator()
    
    def test_fully_valid_code(self):
        """Test validation of completely valid code"""
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
        assert result.syntax.valid is True
        assert result.structure.valid is True
        assert result.imports.valid is True
    
    def test_syntax_error_short_circuits(self):
        """Test that syntax errors skip other validations"""
        code = """
from manim import *

class MyScene(Scene)
    def construct(self):
        text = Text("Hello")
"""
        result = self.validator.validate(code)
        
        assert result.valid is False
        assert result.syntax.valid is False
        # Structure and imports should be skipped (marked as valid)
        assert result.structure.valid is True  # Skipped
        assert result.imports.valid is True    # Skipped
    
    def test_structure_errors(self):
        """Test detection of structure errors with valid syntax"""
        code = """
from manim import *

def my_function():
    text = Text("Hello")
"""
        result = self.validator.validate(code)
        
        assert result.valid is False
        assert result.syntax.valid is True
        assert result.structure.valid is False
        assert len(result.structure.errors) > 0
    
    def test_import_errors(self):
        """Test detection of import errors"""
        code = """
from manim import Scene

class MyScene(Scene):
    def construct(self):
        text = Text("Hello")
        self.play(Write(text))
"""
        result = self.validator.validate(code)
        
        assert result.valid is False
        assert result.syntax.valid is True
        assert result.structure.valid is True
        assert result.imports.valid is False
        assert len(result.imports.missing_imports) > 0
    
    def test_to_dict_conversion(self):
        """Test conversion to dictionary format"""
        code = """
from manim import *

class MyScene(Scene):
    def construct(self):
        text = Text("Hello")
        self.play(Write(text))
        self.wait()
"""
        result = self.validator.validate(code)
        result_dict = result.to_dict()
        
        assert isinstance(result_dict, dict)
        assert "valid" in result_dict
        assert "syntax" in result_dict
        assert "structure" in result_dict
        assert "imports" in result_dict
        assert result_dict["valid"] is True
    
    def test_error_summary_with_errors(self):
        """Test error summary generation with errors"""
        code = """
from manim import Scene

def my_function()
    text = Text("Hello")
"""
        result = self.validator.validate(code)
        summary = result.get_error_summary()
        
        assert isinstance(summary, str)
        assert len(summary) > 0
        assert "syntax" in summary.lower() or "error" in summary.lower()
    
    def test_error_summary_no_errors(self):
        """Test error summary with no errors"""
        code = """
from manim import *

class MyScene(Scene):
    def construct(self):
        text = Text("Hello")
        self.play(Write(text))
        self.wait()
"""
        result = self.validator.validate(code)
        summary = result.get_error_summary()
        
        assert summary == "No errors"
    
    def test_validate_and_get_dict(self):
        """Test convenience method"""
        code = """
from manim import *

class MyScene(Scene):
    def construct(self):
        text = Text("Hello")
        self.wait()
"""
        result_dict = self.validator.validate_and_get_dict(code)
        
        assert isinstance(result_dict, dict)
        assert result_dict["valid"] is True
