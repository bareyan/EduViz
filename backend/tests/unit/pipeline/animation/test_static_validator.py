"""
Unit Tests for StaticValidator
"""
import pytest
from app.services.pipeline.animation.generation.core.validation.static import StaticValidator
from app.services.pipeline.animation.generation.core.validation.models import IssueCategory

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
        assert not result.issues

    async def test_syntax_error(self):
        validator = StaticValidator()
        result = await validator.validate(SYNTAX_ERROR_CODE)
        assert not result.valid
        assert any(i.category == IssueCategory.SYNTAX for i in result.issues)

    async def test_forbidden_import_os(self):
        validator = StaticValidator()
        result = await validator.validate(FORBIDDEN_IMPORT_CODE)
        assert not result.valid
        assert any(
            i.category == IssueCategory.SECURITY and "os" in i.message
            for i in result.issues
        )

    async def test_forbidden_import_subprocess(self):
        validator = StaticValidator()
        result = await validator.validate(FORBIDDEN_FROM_IMPORT_CODE)
        assert not result.valid
        assert any(
            i.category == IssueCategory.SECURITY and "subprocess" in i.message
            for i in result.issues
        )

    async def test_forbidden_builtin_exec(self):
        validator = StaticValidator()
        result = await validator.validate(FORBIDDEN_BUILTIN_CODE)
        assert not result.valid
        assert any(
            i.category == IssueCategory.SECURITY and "exec" in i.message
            for i in result.issues
        )

    async def test_dynamic_import(self):
        code = """
def sneaky():
    m = __import__("os")
    m.system("echo invalid")
"""
        validator = StaticValidator()
        result = await validator.validate(code)
        assert not result.valid
        assert any(
            i.category == IssueCategory.SECURITY and "__import__" in i.message
            for i in result.issues
        )

    async def test_nested_forbidden_call(self):
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
        assert any(
            i.category == IssueCategory.SECURITY and "eval" in i.message
            for i in result.issues
        )

    async def test_complex_imports(self):
        code = """
import sys as s
from os import path as p
import shutil
"""
        validator = StaticValidator()
        result = await validator.validate(code)
        assert not result.valid
        messages = " ".join(i.message for i in result.issues)
        assert "sys" in messages
        assert "shutil" in messages
        assert "os" in messages or "path" in messages
