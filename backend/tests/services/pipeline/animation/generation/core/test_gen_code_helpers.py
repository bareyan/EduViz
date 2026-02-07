
import pytest
import textwrap
from app.services.pipeline.animation.generation.core.code_helpers import (
    clean_code,
    strip_theme_code_from_content,
    create_scene_file,
    fix_translated_code,
    extract_scene_name,
    extract_scene_names,
    ensure_manim_structure,
    get_theme_setup_code
)
from app.services.pipeline.animation.generation.constants import DEFAULT_THEME_CODE

def test_get_theme_setup_code():
    code = get_theme_setup_code(DEFAULT_THEME_CODE)
    assert isinstance(code, str)
    # Just ensure it returns something valid from the config
    assert len(code) > 0

def test_clean_code_full_markdown():
    markdown = textwrap.dedent("""
    Here is the code:
    ```python
    print("Hello")
    ```
    """)
    cleaned = clean_code(markdown)
    assert cleaned == 'print("Hello")'

def test_clean_code_raw():
    raw = 'print("Hello")'
    cleaned = clean_code(raw)
    assert cleaned == 'print("Hello")'

def test_clean_code_none():
    assert clean_code(None) == ""

def test_strip_theme_code():
    code = textwrap.dedent("""
    class Scene(Scene):
        def construct(self):
            self.camera.background_color = "#000000"
            circle = Circle()
            self.play(Create(circle))
    """)
    stripped = strip_theme_code_from_content(code)
    assert "self.camera.background_color" not in stripped
    assert "circle = Circle()" in stripped

def test_create_scene_file_inserts_theme():
    # Minimized code without theme
    code = textwrap.dedent("""
from manim import *
class MyScene(Scene):
    def construct(self):
        c = Circle()
""")
    # Assuming get_theme_setup_code returns something
    full = create_scene_file(code, "id", 10.0, DEFAULT_THEME_CODE)
    assert "config.background_color" in full or "self.camera.background_color" in full

def test_fix_translated_code():
    bad_code = textwrap.dedent("""
    Auto-generated Manim scene
    from manim import *
    """).strip()
    fixed = fix_translated_code(bad_code)
    assert '"""Auto-generated Manim scene"""' in fixed

    bad_code_2 = textwrap.dedent("""
    Some random text
    from manim import *
    """).strip()
    fixed_2 = fix_translated_code(bad_code_2)
    assert "# Some random text" in fixed_2

def test_fix_translated_code_adds_import():
    code = textwrap.dedent("""
class MyScene(Scene):
    pass
""")
    fixed = fix_translated_code(code)
    assert "from manim import *" in fixed

def test_extract_scene_name():
    code = "class MyScene(Scene):"
    assert extract_scene_name(code) == "MyScene"
    
    code = "class Test( Scene ):"
    assert extract_scene_name(code) == "Test"


def test_extract_scene_name_multiple_returns_none():
    code = textwrap.dedent("""
class SceneOne(Scene):
    pass
class SceneTwo(ThreeDScene):
    pass
""")
    assert extract_scene_name(code) is None
    assert extract_scene_names(code) == ["SceneOne", "SceneTwo"]


def test_create_scene_file_does_not_duplicate_background():
    code = textwrap.dedent("""
from manim import *
class MyScene(Scene):
    def construct(self):
        self.camera.background_color = "#171717"
        c = Circle()
""")
    full = create_scene_file(code, "id", 10.0, DEFAULT_THEME_CODE)
    assert full.count("background_color") == 1

def test_ensure_manim_structure():
    good = textwrap.dedent("""from manim import *
class S(Scene):
    def construct(self): pass""")
    assert ensure_manim_structure(good) is True
    
    bad = "print('hello')"
    assert ensure_manim_structure(bad) is False
