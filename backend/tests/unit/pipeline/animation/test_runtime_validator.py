"""
Unit Tests for RuntimeValidator
"""
import pytest
from app.services.pipeline.animation.generation.core.validation.runtime import RuntimeValidator
from app.services.pipeline.animation.generation.core.validation.models import IssueCategory

# Sample valid code
VALID_CODE = """
from manim import *

class TestScene(Scene):
    def construct(self):
        c = Circle()
        self.play(Create(c))
"""

# Sample code with runtime crash
RUNTIME_CRASH_CODE = """
from manim import *

class TestScene(Scene):
    def construct(self):
        x = 1 / 0
        self.add(Circle())
"""

# Sample code with Manim logic error (invalid argument)
MANIM_ERROR_CODE = """
from manim import *

class TestScene(Scene):
    def construct(self):
        # Text requires a string argument
        t = Text(123) 
        self.add(t)
"""

@pytest.mark.asyncio
class TestRuntimeValidator:
    async def test_valid_execution(self):
        validator = RuntimeValidator()
        result = await validator.validate(VALID_CODE)
        assert result.valid
        assert not result.issues

    async def test_runtime_crash_division(self):
        validator = RuntimeValidator()
        result = await validator.validate(RUNTIME_CRASH_CODE)
        assert not result.valid
        assert any(
            i.category == IssueCategory.RUNTIME and "ZeroDivisionError" in i.message
            for i in result.issues
        )

    async def test_manim_logic_error(self):
        bad_code = """
from manim import *
class TestScene(Scene):
    def construct(self):
        c = Circle()
        c.non_existent_method()
"""
        validator = RuntimeValidator()
        result = await validator.validate(bad_code)
        assert not result.valid
        assert any(
            i.category == IssueCategory.RUNTIME and "AttributeError" in i.message
            for i in result.issues
        )

    async def test_latex_error(self):
        bad_code = r"""
from manim import *
class TestScene(Scene):
    def construct(self):
        t = MathTex(r"\badcommand") 
        self.add(t)
"""
        validator = RuntimeValidator()
        result = await validator.validate(bad_code)
        assert not result.valid
        assert any(
            "latex" in i.message.lower() or "error" in i.message.lower()
            for i in result.issues
        )
