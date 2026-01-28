"""
Tests for Manim tool helpers and schemas.

These tests validate deterministic helper logic without calling any LLMs.
"""

from app.services.pipeline.animation.generation.tools import (
    GenerationToolHandler,
    WRITE_CODE_SCHEMA,
    FIX_CODE_SCHEMA,
    VISUAL_SCRIPT_SCHEMA,
    build_context,
    get_language_instructions,
    extract_code_from_response,
    apply_fixes,
)


class TestExtractCodeFromResponse:
    """Test code extraction behavior for tool-based generation."""

    def test_extract_python_markdown(self):
        """Extract code from ```python``` blocks."""
        response = """Here is the code:

```python
from manim import *

class MyScene(Scene):
    def construct(self):
        text = Text("Hello")
```

That's it!"""

        code = extract_code_from_response(response)

        assert "from manim import *" in code
        assert "class MyScene(Scene)" in code
        assert "Here is the code" not in code

    def test_extract_code_like_plain_text(self):
        """Return full response when it already looks like Manim code."""
        response = """from manim import *

class MyScene(Scene):
    def construct(self):
        self.play(Write(Text("Hello")))
        self.wait(1)"""

        code = extract_code_from_response(response)

        assert code == response

    def test_non_code_returns_none(self):
        """Return None for non-code responses."""
        response = "Here is a summary of the animation."
        assert extract_code_from_response(response) is None


class TestApplyFixes:
    """Test search/replace fix application logic."""

    def test_successful_replace(self):
        code = """from manim import *

class MyScene(Scene):
    def construct(self):
        text = Text("Old Text")
        self.play(Write(text))"""

        fixes = [{
            "search": 'Text("Old Text")',
            "replace": 'Text("New Text")',
            "reason": "Update text"
        }]

        new_code, applied, details = apply_fixes(code, fixes)

        assert applied == 1
        assert 'Text("New Text")' in new_code
        assert 'Text("Old Text")' not in new_code
        assert any("OK" in entry for entry in details)

    def test_pattern_not_found(self):
        code = """from manim import *

class MyScene(Scene):
    def construct(self):
        pass"""

        fixes = [{
            "search": 'Text("Missing")',
            "replace": 'Text("New")',
            "reason": "Fix"
        }]

        new_code, applied, details = apply_fixes(code, fixes)

        assert applied == 0
        assert new_code == code
        assert any("FAIL" in entry for entry in details)

    def test_multiple_occurrences(self):
        code = """from manim import *

class MyScene(Scene):
    def construct(self):
        text1 = Text("Hello")
        text2 = Text("Hello")"""

        fixes = [{
            "search": 'Text("Hello")',
            "replace": 'Text("World")',
            "reason": "Disambiguate"
        }]

        new_code, applied, details = apply_fixes(code, fixes)

        assert applied == 0
        assert new_code == code
        assert any("appears 2 times" in entry for entry in details)

    def test_empty_search(self):
        code = "some code"
        fixes = [{"search": "", "replace": "replacement", "reason": "Invalid"}]

        new_code, applied, details = apply_fixes(code, fixes)

        assert applied == 0
        assert new_code == code
        assert any("empty search text" in entry for entry in details)


class TestSchemas:
    """Validate schema structure for tool contracts."""

    def test_write_code_schema(self):
        assert WRITE_CODE_SCHEMA["type"] == "object"
        assert "code" in WRITE_CODE_SCHEMA["required"]

    def test_fix_code_schema(self):
        assert FIX_CODE_SCHEMA["type"] == "object"
        assert "fixes" in FIX_CODE_SCHEMA["required"]

    def test_visual_script_schema(self):
        assert VISUAL_SCRIPT_SCHEMA["type"] == "object"
        assert "segments" in VISUAL_SCRIPT_SCHEMA["required"]


class TestContextHelpers:
    """Smoke tests for context helpers."""

    def test_build_context_includes_duration_and_language(self):
        context = build_context(
            style="clean",
            animation_type="graph",
            target_duration=12.5,
            language="es"
        )
        prompt = context.to_system_prompt()
        assert "TARGET DURATION: 12.5 seconds" in prompt
        assert "LANGUAGE: es" in prompt
        assert "GRAPH ANIMATION" in prompt

    def test_language_instructions_rtl(self):
        instructions = get_language_instructions("ar")
        assert "Noto Sans Arabic" in instructions
        assert "right-to-left" in instructions
