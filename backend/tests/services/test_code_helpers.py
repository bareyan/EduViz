"""
Tests for pipeline/animation/generation/code_helpers module

Tests for code utilities including cleaning, normalization, and scene file creation.
"""

import pytest
from app.services.pipeline.animation.generation.core.code_helpers import (
    clean_code,
    strip_theme_code_from_content,
    create_scene_file,
    fix_translated_code,
    extract_scene_name,
    remove_markdown_blocks,
    ensure_manim_structure,
)
from app.services.infrastructure.parsing.code_parser import normalize_indentation


class TestCleanCode:
    """Test suite for clean_code function"""

    def test_removes_markdown_blocks(self):
        """Test that markdown code blocks are removed"""
        code = '''```python
circle = Circle()
self.play(Create(circle))
```'''
        result = clean_code(code)
        
        assert "```" not in result
        assert "circle" in result.lower()

    def test_removes_import_statements(self):
        """Test that import statements are removed"""
        code = '''from manim import *
import math

circle = Circle()
'''
        result = clean_code(code)
        
        assert "from manim" not in result
        assert "import math" not in result
        assert "circle" in result.lower()

    def test_removes_class_definition(self):
        """Test that class definitions are removed"""
        code = '''class MyScene(Scene):
    def construct(self):
        circle = Circle()
        self.play(Create(circle))
'''
        result = clean_code(code)
        
        assert "class MyScene" not in result
        assert "def construct" not in result
        assert "circle" in result.lower()

    def test_preserves_code_content(self):
        """Test that code content is preserved"""
        code = '''circle = Circle()
square = Square()
self.play(Create(circle), Create(square))
'''
        result = clean_code(code)
        
        assert "Circle" in result
        assert "Square" in result
        assert "Create" in result


class TestNormalizeIndentation:
    """Test suite for normalize_indentation function"""

    def test_tabs_converted_to_spaces(self):
        """Test that tabs are converted to spaces"""
        code = "def test():\n\tprint('hello')"
        result = normalize_indentation(code, base_spaces=0)
        
        assert "\t" not in result
        assert "    " in result

    def test_consistent_4_space_indentation(self):
        """Test that indentation preserves relative structure"""
        code = """def test():
  print("2 spaces")
"""
        result = normalize_indentation(code, base_spaces=0)
        
        # Infrastructure version preserves actual indentation structure
        # Just verify it's normalized (no tabs, clean structure)
        assert "\t" not in result
        lines = result.split("\n")
        # First line should have no indent, second should have some indent
        assert not lines[0].startswith(" ")
        assert lines[1].startswith(" ")

    def test_empty_lines_preserved(self):
        """Test that empty lines are preserved"""
        code = """def test():
    pass

def test2():
    pass"""
        result = normalize_indentation(code, base_spaces=0)
        
        assert "\n\n" in result


class TestStripThemeCodeFromContent:
    """Test suite for strip_theme_code_from_content function"""

    def test_removes_camera_background_settings(self):
        """Test that camera background settings are removed"""
        code = '''circle = Circle()
self.camera.background_color = BLACK
self.play(Create(circle))
'''
        result = strip_theme_code_from_content(code)
        
        assert "background_color" not in result
        assert "Circle" in result

    def test_preserves_other_code(self):
        """Test that non-theme code is preserved"""
        code = '''circle = Circle()
circle.set_color(RED)
self.play(Create(circle))
'''
        result = strip_theme_code_from_content(code)
        
        assert "Circle" in result
        assert "set_color" in result
        assert "RED" in result


class TestCreateSceneFile:
    """Test suite for create_scene_file function"""

    def test_creates_valid_scene_structure(self):
        """Test that created scene has valid structure"""
        code = "circle = Circle()\nself.play(Create(circle))"
        result = create_scene_file(code, "test_section", 10.0)
        
        assert "from manim import *" in result
        assert "class Scene" in result
        assert "def construct" in result

    def test_includes_duration_comment(self):
        """Test that target duration is included in comments"""
        code = "circle = Circle()"
        result = create_scene_file(code, "test", 15.0)
        
        assert "15.0" in result or "TARGET DURATION" in result

    def test_includes_padding_wait(self):
        """Test that padding wait is added"""
        code = "circle = Circle()"
        result = create_scene_file(code, "test", 10.0)
        
        assert "DURATION PADDING" in result or "self.wait" in result

    def test_class_name_from_section_id(self):
        """Test that class name is derived from section_id"""
        code = "pass"
        result = create_scene_file(code, "intro_section", 5.0)
        
        assert "SceneIntroSection" in result


class TestFixTranslatedCode:
    """Test suite for fix_translated_code function"""

    def test_fixes_bare_comment_first_line(self):
        """Test that bare text on first line is fixed"""
        code = """Auto-generated Manim scene for section
from manim import *

class TestScene(Scene):
    pass
"""
        result = fix_translated_code(code)
        
        # Should have quotes or # for the first line
        first_line = result.strip().split('\n')[0]
        assert first_line.startswith('#') or first_line.startswith('"""')

    def test_adds_missing_import(self):
        """Test that missing import is added"""
        code = """class TestScene(Scene):
    def construct(self):
        pass
"""
        result = fix_translated_code(code)
        
        assert "from manim import" in result

    def test_preserves_valid_code(self):
        """Test that valid code is preserved"""
        code = '''"""Test scene"""
from manim import *

class TestScene(Scene):
    def construct(self):
        circle = Circle()
        self.play(Create(circle))
'''
        result = fix_translated_code(code)
        
        assert "Circle" in result
        assert "Create" in result


class TestExtractSceneName:
    """Test suite for extract_scene_name function"""

    def test_extracts_scene_name(self):
        """Test extracting scene name from code"""
        code = '''from manim import *

class MyTestScene(Scene):
    def construct(self):
        pass
'''
        result = extract_scene_name(code)
        
        assert result == "MyTestScene"

    def test_returns_none_for_no_scene(self):
        """Test return None when no Scene class"""
        code = '''def some_function():
    pass
'''
        result = extract_scene_name(code)
        
        assert result is None

    def test_handles_different_formatting(self):
        """Test extraction with different formatting"""
        code = "class Scene123 ( Scene ) :"
        result = extract_scene_name(code)
        
        assert result == "Scene123"


class TestRemoveMarkdownBlocks:
    """Test suite for remove_markdown_blocks function"""

    def test_removes_opening_fence(self):
        """Test removing opening markdown fence"""
        code = '''```python
print("hello")
```'''
        result = remove_markdown_blocks(code)
        
        assert not result.strip().startswith("```")
        assert "print" in result

    def test_removes_closing_fence(self):
        """Test removing closing markdown fence"""
        code = '''```
code here
```'''
        result = remove_markdown_blocks(code)
        
        assert not result.strip().endswith("```")
        assert "code here" in result

    def test_code_without_fences_unchanged(self):
        """Test that code without fences is unchanged"""
        code = "print('hello')"
        result = remove_markdown_blocks(code)
        
        assert result == code


class TestEnsureManimStructure:
    """Test suite for ensure_manim_structure function"""

    def test_valid_manim_code(self):
        """Test detection of valid Manim code"""
        code = '''from manim import *

class TestScene(Scene):
    def construct(self):
        pass
'''
        result = ensure_manim_structure(code)
        
        assert result is True

    def test_missing_import(self):
        """Test detection of missing import"""
        code = '''class TestScene(Scene):
    def construct(self):
        pass
'''
        result = ensure_manim_structure(code)
        
        assert result is False

    def test_missing_class(self):
        """Test detection of missing class"""
        code = '''from manim import *

def construct():
    pass
'''
        result = ensure_manim_structure(code)
        
        assert result is False

    def test_missing_construct(self):
        """Test detection of missing construct"""
        code = '''from manim import *

class TestScene(Scene):
    def some_method(self):
        pass
'''
        result = ensure_manim_structure(code)
        
        assert result is False
