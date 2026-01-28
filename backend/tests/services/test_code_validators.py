"""
Tests for pipeline/animation/generation/validation module

Tests for code validation components including syntax, structure, imports, and spatial validation.
"""

import pytest
from app.services.pipeline.animation.generation.validation.syntax_validator import (
    PythonSyntaxValidator,
    SyntaxValidationResult,
)
from app.services.pipeline.animation.generation.validation.code_validator import (
    CodeValidator,
    CodeValidationResult,
)


class TestSyntaxValidationResult:
    """Test suite for SyntaxValidationResult dataclass"""

    def test_valid_result(self):
        """Test creating a valid result"""
        result = SyntaxValidationResult(valid=True)
        
        assert result.valid is True
        assert result.error_message is None
        assert result.line_number is None

    def test_invalid_result(self):
        """Test creating an invalid result"""
        result = SyntaxValidationResult(
            valid=False,
            error_message="Unexpected token",
            line_number=10,
            column=5,
            error_type="SyntaxError"
        )
        
        assert result.valid is False
        assert result.error_message == "Unexpected token"
        assert result.line_number == 10
        assert result.column == 5

    def test_default_optional_fields(self):
        """Test default values for optional fields"""
        result = SyntaxValidationResult(valid=False)
        
        assert result.error_message is None
        assert result.line_number is None
        assert result.error_type is None
        assert result.column is None


class TestPythonSyntaxValidator:
    """Test suite for PythonSyntaxValidator"""

    @pytest.fixture
    def validator(self):
        """Create a syntax validator"""
        return PythonSyntaxValidator()

    def test_valid_python_code(self, validator):
        """Test validation of valid Python code"""
        code = '''
def hello():
    print("Hello, World!")

class MyClass:
    def __init__(self):
        self.value = 42
'''
        result = validator.validate(code)
        
        assert result.valid is True
        assert result.error_message is None

    def test_valid_manim_code(self, validator):
        """Test validation of valid Manim code"""
        code = '''
from manim import *

class MyScene(Scene):
    def construct(self):
        circle = Circle()
        self.play(Create(circle))
        self.wait(1)
'''
        result = validator.validate(code)
        
        assert result.valid is True

    def test_syntax_error_missing_colon(self, validator):
        """Test detection of missing colon in function definition"""
        code = '''
def hello()
    print("missing colon")
'''
        result = validator.validate(code)
        
        assert result.valid is False
        assert result.error_type == "SyntaxError"
        assert result.line_number is not None

    def test_syntax_error_unmatched_paren(self, validator):
        """Test detection of unmatched parentheses"""
        code = '''
def hello():
    print("test"
'''
        result = validator.validate(code)
        
        assert result.valid is False
        assert result.error_type == "SyntaxError"

    def test_syntax_error_invalid_indentation(self, validator):
        """Test detection of invalid indentation"""
        code = '''
def hello():
print("wrong indent")
'''
        result = validator.validate(code)
        
        assert result.valid is False

    def test_empty_code(self, validator):
        """Test validation of empty code"""
        result = validator.validate("")
        
        assert result.valid is False
        assert result.error_type == "EmptyCodeError"

    def test_whitespace_only_code(self, validator):
        """Test validation of whitespace-only code"""
        result = validator.validate("   \n\n   \t")
        
        assert result.valid is False
        assert result.error_type == "EmptyCodeError"

    def test_unicode_in_code(self, validator):
        """Test validation of code with unicode characters"""
        code = '''
def greet():
    message = "Привет, 世界!"
    return message
'''
        result = validator.validate(code)
        
        assert result.valid is True


class TestCodeValidator:
    """Test suite for CodeValidator composite validator"""

    @pytest.fixture
    def validator(self):
        """Create a code validator"""
        return CodeValidator()

    def test_valid_manim_code(self, validator):
        """Test validation of valid Manim code"""
        code = '''
from manim import *

class MyScene(Scene):
    def construct(self):
        circle = Circle()
        self.play(Create(circle))
        self.wait(1)
'''
        result = validator.validate(code)
        
        assert result.syntax.valid is True
        assert isinstance(result, CodeValidationResult)

    def test_syntax_error_short_circuits(self, validator):
        """Test that syntax errors short-circuit other validations"""
        code = '''
def broken(
    print("syntax error")
'''
        result = validator.validate(code)
        
        assert result.valid is False
        assert result.syntax.valid is False
        # Other validators should be skipped (returned as valid)
        assert result.structure.valid is True
        assert result.imports.valid is True

    def test_validate_code_backward_compat(self, validator):
        """Test backward-compatible validate_code method"""
        code = '''
from manim import *

class TestScene(Scene):
    def construct(self):
        self.wait(1)
'''
        result = validator.validate_code(code)
        
        assert "valid" in result
        assert "error" in result
        assert "details" in result

    def test_validate_and_get_dict(self, validator):
        """Test validate_and_get_dict method"""
        code = '''
from manim import *

class TestScene(Scene):
    def construct(self):
        self.wait(1)
'''
        result = validator.validate_and_get_dict(code)
        
        assert isinstance(result, dict)
        assert "valid" in result
        assert "syntax" in result
        assert "structure" in result
        assert "imports" in result
        assert "spatial" in result


class TestCodeValidationResult:
    """Test suite for CodeValidationResult"""

    def test_to_dict_format(self):
        """Test to_dict returns correct format"""
        from app.services.pipeline.animation.generation.validation.syntax_validator import SyntaxValidationResult
        from app.services.pipeline.animation.generation.validation.manim_validator import ManimValidationResult
        from app.services.pipeline.animation.generation.validation.imports_validator import ImportsValidationResult
        from app.services.pipeline.animation.generation.validation.spatial_validator import SpatialValidationResult
        
        result = CodeValidationResult(
            valid=True,
            syntax=SyntaxValidationResult(valid=True),
            structure=ManimValidationResult(valid=True),
            imports=ImportsValidationResult(valid=True),
            spatial=SpatialValidationResult(valid=True)
        )
        
        d = result.to_dict()
        
        assert d["valid"] is True
        assert isinstance(d["syntax"], dict)
        assert isinstance(d["structure"], dict)
        assert isinstance(d["imports"], dict)
        assert isinstance(d["spatial"], dict)

    def test_get_error_summary_no_errors(self):
        """Test error summary with no errors"""
        from app.services.pipeline.animation.generation.validation.syntax_validator import SyntaxValidationResult
        from app.services.pipeline.animation.generation.validation.manim_validator import ManimValidationResult
        from app.services.pipeline.animation.generation.validation.imports_validator import ImportsValidationResult
        from app.services.pipeline.animation.generation.validation.spatial_validator import SpatialValidationResult
        
        result = CodeValidationResult(
            valid=True,
            syntax=SyntaxValidationResult(valid=True),
            structure=ManimValidationResult(valid=True),
            imports=ImportsValidationResult(valid=True),
            spatial=SpatialValidationResult(valid=True)
        )
        
        summary = result.get_error_summary()
        
        assert summary == "No errors"

    def test_get_error_summary_with_syntax_error(self):
        """Test error summary with syntax error"""
        from app.services.pipeline.animation.generation.validation.syntax_validator import SyntaxValidationResult
        from app.services.pipeline.animation.generation.validation.manim_validator import ManimValidationResult
        from app.services.pipeline.animation.generation.validation.imports_validator import ImportsValidationResult
        from app.services.pipeline.animation.generation.validation.spatial_validator import SpatialValidationResult
        
        result = CodeValidationResult(
            valid=False,
            syntax=SyntaxValidationResult(
                valid=False,
                error_message="Invalid syntax on line 5"
            ),
            structure=ManimValidationResult(valid=True),
            imports=ImportsValidationResult(valid=True),
            spatial=SpatialValidationResult(valid=True)
        )
        
        summary = result.get_error_summary()
        
        assert "Syntax Error" in summary
        assert "Invalid syntax on line 5" in summary
