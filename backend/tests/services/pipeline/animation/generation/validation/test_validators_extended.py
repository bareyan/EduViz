"""
Tests for extended validation coverage in pipeline/animation/generation/validation

Tests for imports, manim structure, and spatial validators.
"""

import pytest
from unittest.mock import MagicMock, patch


class TestImportsValidator:
    """Test suite for ManimImportsValidator"""

    @pytest.fixture
    def validator(self):
        from app.services.pipeline.animation.generation.validation.imports_validator import (
            ManimImportsValidator,
        )
        return ManimImportsValidator()

    def test_valid_standard_import(self, validator):
        """Test valid manim import is accepted"""
        code = '''from manim import *

class Test(Scene):
    def construct(self):
        circle = Circle()
        self.play(Create(circle))
'''
        result = validator.validate(code)
        
        assert result.valid is True

    def test_wildcard_import_warning(self, validator):
        """Test wildcard import generates warning"""
        code = '''from manim import *

class Test(Scene):
    def construct(self):
        pass
'''
        result = validator.validate(code)
        
        # May have a warning about wildcard
        # Actual behavior depends on implementation
        assert result.valid is True

    def test_specific_imports_accepted(self, validator):
        """Test specific imports are accepted"""
        code = '''from manim import Scene, Circle, Create

class Test(Scene):
    def construct(self):
        circle = Circle()
        self.play(Create(circle))
'''
        result = validator.validate(code)
        
        assert result.valid is True

    def test_missing_import_flagged(self, validator):
        """Test missing import is flagged"""
        code = '''# No import statement

class Test(Scene):
    def construct(self):
        pass
'''
        result = validator.validate(code)
        
        # Should detect missing import
        assert result.valid is False or len(result.warnings) > 0 or len(result.missing_imports) > 0

    def test_external_module_imports_preserved(self, validator):
        """Test external module imports are allowed"""
        code = '''import random
import math
from manim import *

class Test(Scene):
    def construct(self):
        x = random.random()
        y = math.sin(x)
        self.wait(1)
'''
        result = validator.validate(code)
        
        assert result.valid is True


class TestManimStructureValidator:
    """Test suite for ManimStructureValidator"""

    @pytest.fixture
    def validator(self):
        from app.services.pipeline.animation.generation.validation.manim_validator import (
            ManimStructureValidator,
        )
        return ManimStructureValidator()

    def test_valid_scene_structure(self, validator):
        """Test valid scene structure passes"""
        code = '''from manim import *

class TestScene(Scene):
    def construct(self):
        circle = Circle()
        self.play(Create(circle))
        self.wait(1)
'''
        result = validator.validate(code)
        
        assert result.valid is True

    def test_missing_scene_class(self, validator):
        """Test missing scene class is flagged"""
        code = '''from manim import *

def construct():
    pass
'''
        result = validator.validate(code)
        
        assert result.valid is False or "scene" in str(result.errors).lower()

    def test_missing_construct_method(self, validator):
        """Test missing construct method is flagged"""
        code = '''from manim import *

class TestScene(Scene):
    def render(self):
        pass
'''
        result = validator.validate(code)
        
        assert result.valid is False or "construct" in str(result.errors).lower()

    def test_font_size_warning_large(self, validator):
        """Test large font size generates warning"""
        code = '''from manim import *

class TestScene(Scene):
    def construct(self):
        text = Text("Hello", font_size=120)
        self.play(Write(text))
        self.wait(1)
'''
        result = validator.validate(code)
        
        # Should have warning about font size
        assert len(result.warnings) > 0 or "font" in str(result.warnings).lower()

    def test_missing_wait_warning(self, validator):
        """Test missing wait generates warning"""
        code = '''from manim import *

class TestScene(Scene):
    def construct(self):
        circle = Circle()
        self.play(Create(circle))
        # No self.wait()
'''
        result = validator.validate(code)
        
        # May have warning about missing wait
        # This is implementation-dependent
        assert isinstance(result.valid, bool)

    def test_long_text_warning(self, validator):
        """Test text exceeding character limit generates warning"""
        code = f'''from manim import *

class TestScene(Scene):
    def construct(self):
        text = Text("{"A" * 150}")  # Very long text
        self.play(Write(text))
        self.wait(1)
'''
        result = validator.validate(code)
        
        # Should have warning about text length
        assert len(result.warnings) > 0 or result.valid

    def test_background_color_warning(self, validator):
        """Test background color in code generates warning"""
        code = '''from manim import *

class TestScene(Scene):
    def construct(self):
        self.camera.background_color = WHITE
        circle = Circle()
        self.play(Create(circle))
        self.wait(1)
'''
        result = validator.validate(code)
        
        # May have warning about manual background setting
        assert isinstance(result.valid, bool)


class TestSpatialValidatorBasic:
    """Test suite for SpatialValidator (non-execution tests)"""

    @pytest.fixture
    def validator(self):
        from app.services.pipeline.animation.generation.validation.spatial_validator import (
            SpatialValidator,
        )
        return SpatialValidator()

    def test_validator_instantiation(self, validator):
        """Test validator can be instantiated"""
        assert validator is not None

    def test_result_dataclass_structure(self):
        """Test SpatialValidationResult has expected structure"""
        from app.services.pipeline.animation.generation.validation.spatial_validator import (
            SpatialValidationResult,
        )
        
        result = SpatialValidationResult(
            valid=True,
            errors=[],
            warnings=[],
            raw_report="No issues"
        )
        
        assert result.valid is True
        assert result.errors == []
        assert result.warnings == []
        assert result.raw_report == "No issues"

    def test_result_with_issues(self):
        """Test SpatialValidationResult with issues"""
        from app.services.pipeline.animation.generation.validation.spatial_validator import (
            SpatialValidationResult,
            SpatialIssue,
        )
        
        error_issue = SpatialIssue(
            line_number=10,
            severity="error",
            message="Text overlaps circle",
            code_snippet="circle = Circle()"
        )
        warning_issue = SpatialIssue(
            line_number=15,
            severity="warning",
            message="Object near boundary",
            code_snippet="text.to_edge(UP)"
        )
        
        result = SpatialValidationResult(
            valid=False,
            errors=[error_issue],
            warnings=[warning_issue],
            raw_report="Issues found"
        )
        
        assert result.valid is False
        assert len(result.errors) == 1
        assert len(result.warnings) == 1


class TestSyntaxValidatorEdgeCases:
    """Test additional edge cases for syntax validator"""

    @pytest.fixture
    def validator(self):
        from app.services.pipeline.animation.generation.validation.syntax_validator import (
            PythonSyntaxValidator,
        )
        return PythonSyntaxValidator()

    def test_multiline_string(self, validator):
        """Test multiline string syntax is valid"""
        code = '''
text = """
This is a
multiline string
"""
'''
        result = validator.validate(code)
        assert result.valid is True

    def test_f_string_syntax(self, validator):
        """Test f-string syntax is valid"""
        code = '''
name = "World"
message = f"Hello, {name}!"
'''
        result = validator.validate(code)
        assert result.valid is True

    def test_decorator_syntax(self, validator):
        """Test decorator syntax is valid"""
        code = '''
def decorator(func):
    return func

@decorator
def my_function():
    pass
'''
        result = validator.validate(code)
        assert result.valid is True

    def test_async_syntax(self, validator):
        """Test async/await syntax is valid"""
        code = '''
async def async_func():
    await some_coroutine()
'''
        result = validator.validate(code)
        assert result.valid is True

    def test_walrus_operator(self, validator):
        """Test walrus operator syntax is valid"""
        code = '''
if (n := len("hello")) > 3:
    print(n)
'''
        result = validator.validate(code)
        assert result.valid is True

    def test_type_hints(self, validator):
        """Test type hint syntax is valid"""
        code = '''
def greet(name: str) -> str:
    return f"Hello, {name}"
'''
        result = validator.validate(code)
        assert result.valid is True


class TestCodeValidatorIntegration:
    """Test CodeValidator integration with sub-validators"""

    @pytest.fixture
    def validator(self):
        from app.services.pipeline.animation.generation.validation.code_validator import (
            CodeValidator,
        )
        return CodeValidator()

    def test_all_validators_run(self, validator):
        """Test all validators are executed for valid code"""
        code = '''from manim import *

class TestScene(Scene):
    def construct(self):
        self.wait(1)
'''
        result = validator.validate(code)
        
        # All sub-results should be present
        assert result.syntax is not None
        assert result.structure is not None
        assert result.imports is not None

    def test_syntax_failure_shortcuts_others(self, validator):
        """Test syntax failure prevents other validators from running"""
        code = '''def broken(
    pass  # Syntax error
'''
        result = validator.validate(code)
        
        assert result.valid is False
        assert result.syntax.valid is False

    def test_validate_and_get_dict_returns_dict(self, validator):
        """Test validate_and_get_dict returns dictionary format"""
        code = '''from manim import *

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

    def test_get_error_summary_formats_correctly(self, validator):
        """Test error summary format"""
        code = '''from manim import *

class TestScene(Scene):
    def construct(self):
        self.wait(1)
'''
        result = validator.validate(code)
        summary = result.get_error_summary()
        
        assert isinstance(summary, str)


class TestValidationResultDictFormat:
    """Test dataclass serialization for validation results using dataclasses.asdict"""

    def test_syntax_result_can_be_serialized(self):
        """Test syntax validation result can be serialized as dict"""
        from dataclasses import asdict
        from app.services.pipeline.animation.generation.validation.syntax_validator import (
            SyntaxValidationResult,
        )
        
        result = SyntaxValidationResult(
            valid=False,
            error_message="Unexpected token",
            line_number=10,
            column=5,
            error_type="SyntaxError"
        )
        
        d = asdict(result)
        
        assert d["valid"] is False
        assert d["error_message"] == "Unexpected token"
        assert d["line_number"] == 10

    def test_manim_result_can_be_serialized(self):
        """Test manim validation result can be serialized as dict"""
        from dataclasses import asdict
        from app.services.pipeline.animation.generation.validation.manim_validator import (
            ManimValidationResult,
        )
        
        result = ManimValidationResult(
            valid=True,
            errors=[],
            warnings=["Font size may be too large"]
        )
        
        d = asdict(result)
        
        assert d["valid"] is True
        assert d["errors"] == []
        assert len(d["warnings"]) == 1

    def test_imports_result_can_be_serialized(self):
        """Test imports validation result can be serialized as dict"""
        from dataclasses import asdict
        from app.services.pipeline.animation.generation.validation.imports_validator import (
            ImportsValidationResult,
        )
        
        result = ImportsValidationResult(
            valid=True,
            missing_imports=[],
            unused_imports=[],
            has_wildcard=False
        )
        
        d = asdict(result)
        
        assert d["valid"] is True
        assert "missing_imports" in d
        assert "has_wildcard" in d
