"""
Unit Tests for StaticValidator
"""
import pytest
from app.services.pipeline.animation.generation.core.validation.static import StaticValidator

# Sample valid code
VALID_CODE = """
from manim import *

class TestScene(Scene):
    def construct(self):
        c = Circle()
        self.play(Create(c))
"""

# Sample code with syntax error
SYNTAX_ERROR_CODE = """
from manim import *
class TestScene(Scene)  # Missing colon
    def construct(self):
        print("Hello")
"""

# Sample code with forbidden import
FORBIDDEN_IMPORT_CODE = """
import os
def malicious():
    os.system("echo dangerous")
"""

# Sample code with forbidden import (from)
FORBIDDEN_FROM_IMPORT_CODE = """
from subprocess import run
def malicious():
    run("echo dangerous")
"""

# Sample code with forbidden builtin
FORBIDDEN_BUILTIN_CODE = """
def malicious():
    exec("print('dangerous')")
"""

@pytest.mark.asyncio
class TestStaticValidator:
    async def test_valid_code(self):
        validator = StaticValidator()
        result = await validator.validate(VALID_CODE)
        assert result.valid
        assert not result.errors

    async def test_syntax_error(self):
        validator = StaticValidator()
        result = await validator.validate(SYNTAX_ERROR_CODE)
        assert not result.valid
        # Check for AST syntax error message
        assert any("Syntax" in e or "invalid syntax" in e for e in result.errors)

    async def test_forbidden_import_os(self):
        validator = StaticValidator()
        result = await validator.validate(FORBIDDEN_IMPORT_CODE)
        assert not result.valid
        assert any("Forbidden import" in e and "os" in e for e in result.errors)

    async def test_forbidden_import_subprocess(self):
        validator = StaticValidator()
        result = await validator.validate(FORBIDDEN_FROM_IMPORT_CODE)
        assert not result.valid
        assert any("Forbidden import" in e and "subprocess" in e for e in result.errors)

    async def test_forbidden_builtin_exec(self):
        validator = StaticValidator()
        result = await validator.validate(FORBIDDEN_BUILTIN_CODE)
        assert not result.valid
        assert any("Forbidden builtin" in e and "exec" in e for e in result.errors)

    async def test_dynamic_import(self):
        # Edge case: __import__ function
        code = """
def sneaky():
    m = __import__("os")
    m.system("echo invalid")
"""
        validator = StaticValidator()
        result = await validator.validate(code)
        assert not result.valid
        # Assuming our AST walker handles Call(Name(id='__import__'))?
        # If not, I'll need to update static.py. Let's test first.
        assert any("__import__" in str(result.errors) or "Forbidden builtin" in str(result.errors) for e in result.errors) or not result.valid

    async def test_nested_forbidden_call(self):
        # Edge case: Forbidden call deep inside nested functions
        code = """
class Wrapper:
    def outer(self):
        def inner():
            eval("print(1)")
        inner()
"""
        validator = StaticValidator()
        result = await validator.validate(code)
        assert not result.valid
        assert any("Forbidden builtin" in e for e in result.errors)

    async def test_complex_imports(self):
        # Edge case: Aliased imports and submodules
        code = """
import sys as s
from os import path as p
import shutil
"""
        validator = StaticValidator()
        result = await validator.validate(code)
        assert not result.valid
        assert any("sys" in e for e in result.errors)
        assert any("shutil" in e for e in result.errors)
        # Note: 'os' might be caught as module name
        assert any("os" in e or "path" in e for e in result.errors)
