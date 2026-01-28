"""
Tests for app.services.infrastructure.parsing.json_parser

This module tests the JSON and code parsing utilities.
Note: These tests document current behavior, including potential limitations.
"""

import json
import pytest
from app.services.infrastructure.parsing.json_parser import (
    fix_json_escapes,
    parse_json_response,
    parse_json_array_response,
    extract_markdown_code_blocks,
    remove_markdown_wrappers,
    validate_python_syntax,
    normalize_whitespace,
    extract_text_between_markers,
    split_into_lines,
)


class TestJsonEscapes:
    """Test fixing common JSON escape sequence issues."""

    def test_fix_json_escapes_basic(self):
        """Test with valid and invalid escapes."""
        # \n is valid, \  (lone backslash) is invalid in JSON
        text = r'{"key": "value\nwith\invalid\escape"}'
        fixed = fix_json_escapes(text)
        # \n should be preserved, \i should be escaped as \\i
        assert r'\n' in fixed
        assert r'\\i' in fixed
        
    def test_fix_json_escapes_lone_backslash(self):
        """Test escaping a lone backslash."""
        text = r"C:\Users\Name"
        fixed = fix_json_escapes(text)
        assert fixed == r"C:\\Users\\Name"

    def test_fix_json_escapes_unicode(self):
        """Test unicode escape preservation."""
        text = r'{"char": "\u1234"}'
        fixed = fix_json_escapes(text)
        assert r"\u1234" in fixed

    def test_fix_json_escapes_complex(self):
        """Test a mix of valid and invalid escapes."""
        text = r'{"a": "valid\n", "b": "invalid\p", "c": "backslash\\"}'
        fixed = fix_json_escapes(text)
        assert r'\n' in fixed
        assert r'\\p' in fixed
        assert r'\\"' in fixed or r'\"' in fixed # \" is valid


class TestParseJsonResponse:
    """Test parsing JSON from LLM response with recovery."""

    def test_parse_json_response_direct(self):
        """Test parsing valid JSON object."""
        data = {"count": 42, "status": "ok"}
        text = json.dumps(data)
        assert parse_json_response(text) == data

    def test_parse_json_response_markdown(self):
        """Test parsing JSON from markdown code block."""
        data = {"key": "val"}
        text = f"```json\n{json.dumps(data)}\n```"
        assert parse_json_response(text) == data

    def test_parse_json_response_surrounding_text(self):
        """Test extracting JSON from surrounding text."""
        data = {"key": "val"}
        text = f"The response is: {json.dumps(data)} hope this helps!"
        assert parse_json_response(text) == data

    def test_parse_json_response_invalid_escapes(self):
        """Test parsing JSON with invalid escapes (e.g. windows paths without reserved escapes)."""
        # \p and \u (if not followed by 4 hex) are not valid JSON escapes
        # Note: \t, \n, \f, \r, \b are valid escapes and will be preserved by fix_json_escapes
        text = r'{"path": "C:\path\u_not_unicode\work"}'
        result = parse_json_response(text)
        assert result["path"] == r"C:\path\u_not_unicode\work"

    def test_parse_json_response_preserves_valid_escapes(self):
        """Test that it preserves valid escapes like \n."""
        text = '{"msg": "line1\\nline2"}'
        result = parse_json_response(text)
        assert result["msg"] == "line1\nline2"

    def test_parse_json_response_malformed_fallback(self):
        """Test fallback when JSON is slightly malformed (e.g. trailing text)."""
        text = '{"a": 1} some extra chars'
        assert parse_json_response(text) == {"a": 1}

    def test_parse_json_response_failure_returns_default(self):
        """Test that failure returns the provided default."""
        default = {"fallback": True}
        assert parse_json_response("not json", default=default) == default


class TestParseJsonArrayResponse:
    """Test parsing JSON array from LLM response."""

    def test_parse_json_array_basic(self):
        """Test parsing valid JSON array."""
        data = [{"id": 1}, {"id": 2}]
        text = json.dumps(data)
        assert parse_json_array_response(text) == data

    def test_parse_json_array_markdown(self):
        """Test parsing array from markdown."""
        data = [{"id": 1}]
        text = f"```json\n{json.dumps(data)}```"
        assert parse_json_array_response(text) == data

    def test_parse_json_array_failure_returns_default(self):
        """Test failure returns list default."""
        assert parse_json_array_response("not an array", default=[{"err": 1}]) == [{"err": 1}]

    def test_parse_json_array_not_a_list(self):
        """Test that if result is a dict, it returns default."""
        text = '{"not": "a list"}'
        assert parse_json_array_response(text, default=[]) == []


class TestMarkdownExtraction:
    """Test extracting and cleaning markdown code blocks."""

    def test_extract_markdown_code_blocks_basic(self):
        """Test extracting python block."""
        text = "```python\nprint(123)\n```"
        blocks = extract_markdown_code_blocks(text, "python")
        assert len(blocks) == 1
        assert "print(123)" in blocks[0]

    def test_extract_markdown_code_blocks_strictness(self):
        """
        Documenting behavior: current implementation is strict about \n.
        If there's a space after 'python', it might fail (depending on regex).
        """
        # Note: current regex is rf'```{language}\n(.*)```'
        text_with_space = "```python \nprint(1)\n```"
        blocks = extract_markdown_code_blocks(text_with_space, "python")
        # This will fail with current implementation because of the space
        assert len(blocks) == 0

    def test_remove_markdown_wrappers(self):
        """Test removing wrappers."""
        text = "```\ncontent\n```"
        assert remove_markdown_wrappers(text) == "content"


class TestPythonValidation:
    """Test Python syntax validation."""

    def test_validate_python_syntax_valid(self):
        """Test valid code."""
        assert validate_python_syntax("x = 1\ny = 2") is None

    def test_validate_python_syntax_invalid(self):
        """Test invalid code."""
        error = validate_python_syntax("if True\n  pass")
        assert error is not None
        assert "SyntaxError" in error

    def test_validate_python_syntax_exception(self):
        """Test something that might raise a non-SyntaxError (though compile usually raises SyntaxError)."""
        # Actually compile(code, ...) mostly raises SyntaxError for syntax.
        # But maybe NUL bytes?
        error = validate_python_syntax("\0")
        assert error is not None


class TestTextProcessing:
    """Test text processing utilities."""

    def test_normalize_whitespace(self):
        """Test whitespace normalization."""
        text = "  hello\tworld   spaced  "
        normalized = normalize_whitespace(text)
        # Tab -> 4 spaces, multiple spaces -> 1 space, strip
        # "hello    world spaced"
        assert normalized == "hello world spaced"

    def test_extract_text_between_markers(self):
        """Test extracting content."""
        text = "prefix START desired content END suffix"
        result = extract_text_between_markers(text, "START", "END")
        assert result == "desired content"

    def test_extract_text_between_markers_missing(self):
        """Test missing markers."""
        assert extract_text_between_markers("no markers", "A", "B") is None

    def test_split_into_lines_basic(self):
        """Test splitting."""
        text = "line1\n\nline2\n "
        lines = split_into_lines(text, skip_empty=True)
        assert len(lines) == 2
        assert lines == ["line1", "line2"]

    def test_split_into_lines_keep_empty(self):
        """Test keeping empty lines."""
        text = "line1\n\nline2"
        lines = split_into_lines(text, skip_empty=False)
        assert len(lines) == 3
        assert lines[1] == ""
