"""
Tests for Python syntax validator

Ensures syntax validation works correctly for valid and invalid code.
"""

import pytest
from app.services.pipeline.animation.generation.validation import PythonSyntaxValidator


class TestPythonSyntaxValidator:
    """Test suite for PythonSyntaxValidator"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.validator = PythonSyntaxValidator()
    
    def test_valid_simple_code(self):
        """Test validation of simple valid Python code"""
        code = """
def hello():
    print("Hello, World!")
"""
        result = self.validator.validate(code)
        
        assert result.valid is True
        assert result.error_message is None
        assert result.line_number is None
    
    def test_valid_manim_code(self):
        """Test validation of valid Manim code"""
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
        assert result.error_message is None
    
    def test_syntax_error_missing_colon(self):
        """Test detection of missing colon syntax error"""
        code = """
def hello()
    print("Hello")
"""
        result = self.validator.validate(code)
        
        assert result.valid is False
        assert result.error_type == "SyntaxError"
        assert result.line_number is not None
        assert ":" in result.error_message.lower() or "invalid" in result.error_message.lower()
    
    def test_syntax_error_invalid_indentation(self):
        """Test detection of indentation errors"""
        code = """
def hello():
print("Hello")
"""
        result = self.validator.validate(code)
        
        assert result.valid is False
        assert result.error_type == "SyntaxError"
        assert result.line_number == 3
    
    def test_syntax_error_unclosed_string(self):
        """Test detection of unclosed string"""
        code = '''
text = "Hello World
'''
        result = self.validator.validate(code)
        
        assert result.valid is False
        assert result.error_type == "SyntaxError"
    
    def test_empty_code(self):
        """Test validation of empty code"""
        result = self.validator.validate("")
        
        assert result.valid is False
        assert result.error_type == "EmptyCodeError"
        assert "empty" in result.error_message.lower()
    
    def test_whitespace_only_code(self):
        """Test validation of whitespace-only code"""
        result = self.validator.validate("   \n\n   \t  ")
        
        assert result.valid is False
        assert result.error_type == "EmptyCodeError"
    
    def test_valid_code_with_comments(self):
        """Test that comments don't affect validation"""
        code = """
# This is a comment
def hello():
    # Another comment
    print("Hello")  # Inline comment
"""
        result = self.validator.validate(code)
        
        assert result.valid is True
