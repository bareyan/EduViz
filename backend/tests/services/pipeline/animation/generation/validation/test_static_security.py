import pytest
from app.services.pipeline.animation.generation.validation.static import StaticValidator

@pytest.fixture
def validator():
    return StaticValidator()

def test_forbidden_eval(validator):
    code = '''from manim import *
class MyScene(Scene):
    def construct(self):
        eval("print('hello')")
'''
    result = validator.validate(code)
    assert result.valid is False
    assert any("Do not use eval()" in e for e in result.errors)

def test_forbidden_os_system(validator):
    code = '''from manim import *
class MyScene(Scene):
    def construct(self):
        import os
        os.system("rm -rf /")
'''
    result = validator.validate(code)
    assert result.valid is False
    assert any("Do not call os.system()" in e for e in result.errors)

def test_forbidden_sys_exit(validator):
    code = '''from manim import *
class MyScene(Scene):
    def construct(self):
        import sys
        sys.exit(1)
'''
    result = validator.validate(code)
    assert result.valid is False
    assert any("Do not call sys.exit()" in e for e in result.errors)

def test_forbidden_subprocess(validator):
    code = '''from manim import *
class MyScene(Scene):
    def construct(self):
        import subprocess
        subprocess.run(["ls"])
'''
    result = validator.validate(code)
    assert result.valid is False
    assert any("Do not use subprocess module" in e for e in result.errors)

def test_background_color_warning_remains(validator):
    code = '''from manim import *
class MyScene(Scene):
    def construct(self):
        self.camera.background_color = RED
'''
    result = validator.validate(code)
    assert result.valid is True
    assert any("background_color" in w for w in result.warnings)
