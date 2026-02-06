
from app.services.pipeline.animation.generation.constants import (
    DEFAULT_THEME_CODE,
    DEFAULT_THEME,
    DEFAULT_VISUAL_HINTS,
    DEFAULT_SECTION_TITLE,
    DEFAULT_LANGUAGE
)

def test_default_theme_code():
    assert DEFAULT_THEME_CODE == "3b1b"

def test_default_theme():
    assert DEFAULT_THEME == "3b1b dark educational style"

def test_default_visual_hints():
    assert DEFAULT_VISUAL_HINTS == "No explicit visual hints"

def test_default_section_title():
    assert DEFAULT_SECTION_TITLE == "Untitled"

def test_default_language():
    assert DEFAULT_LANGUAGE == "en"
