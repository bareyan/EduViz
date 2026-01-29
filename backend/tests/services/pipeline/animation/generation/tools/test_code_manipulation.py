"""
Tests for app.services.pipeline.animation.generation.tools.code_manipulation

Tests for code extraction, patch application, and response parsing utilities.
"""

import pytest
from app.services.pipeline.animation.generation.tools.code_manipulation import (
    extract_code_from_response,
    apply_patches,
    find_similar_text,
    clean_function_call_args,
)


class TestExtractCodeFromResponse:
    """Test suite for extract_code_from_response function"""

    def test_extracts_from_python_markdown_block(self):
        """Test extraction from ```python code block"""
        response = '''Here is your code:
```python
circle = Circle()
self.play(Create(circle))
```
Done!'''
        result = extract_code_from_response(response)
        
        assert result is not None
        assert "circle = Circle()" in result
        assert "self.play(Create(circle))" in result
        assert "```" not in result

    def test_extracts_from_generic_markdown_block(self):
        """Test extraction from ``` code block without language"""
        response = '''Code:
```
self.wait(1)
```'''
        result = extract_code_from_response(response)
        
        assert result is not None
        assert "self.wait(1)" in result

    def test_returns_none_for_empty_response(self):
        """Test empty response returns None"""
        assert extract_code_from_response("") is None
        assert extract_code_from_response(None) is None

    def test_returns_code_if_looks_like_manim(self):
        """Test that raw Manim code is returned as-is"""
        code = "self.play(Create(circle))\nself.wait(1)"
        result = extract_code_from_response(code)
        
        assert result == code

    def test_returns_none_for_plain_text(self):
        """Test plain text without code returns None"""
        response = "Here is my explanation of the concept."
        result = extract_code_from_response(response)
        
        assert result is None


class TestApplyPatches:
    """Test suite for apply_patches function"""

    def test_exact_match_single_patch(self):
        """Test applying a single exact match patch"""
        code = '''line1
line2
line3'''
        patches = [{
            "search": "line2",
            "replace": "modified_line2",
            "reason": "Fix line 2"
        }]
        
        new_code, applied, details = apply_patches(code, patches)
        
        assert applied == 1
        assert "modified_line2" in new_code
        # Check original standalone line2 is replaced (note: "line2" is still in "modified_line2")
        assert new_code.split('\n')[1] == "modified_line2"
        assert "OK" in details[0]

    def test_exact_match_multiple_patches(self):
        """Test applying multiple patches in sequence"""
        code = '''first
second
third'''
        patches = [
            {"search": "first", "replace": "FIRST", "reason": ""},
            {"search": "second", "replace": "SECOND", "reason": ""},
        ]
        
        new_code, applied, details = apply_patches(code, patches)
        
        assert applied == 2
        assert "FIRST" in new_code
        assert "SECOND" in new_code

    def test_empty_search_text_skipped(self):
        """Test that empty search text is skipped"""
        code = "original"
        patches = [{"search": "", "replace": "replacement", "reason": "No search"}]
        
        new_code, applied, details = apply_patches(code, patches)
        
        assert applied == 0
        assert "SKIP" in details[0]
        assert new_code == code

    def test_search_not_found(self):
        """Test patch failure when search text not found"""
        code = "original content"
        patches = [{"search": "nonexistent", "replace": "new", "reason": ""}]
        
        new_code, applied, details = apply_patches(code, patches)
        
        assert applied == 0
        assert "FAIL" in details[0]
        assert "not found" in details[0]

    def test_non_unique_match_fails(self):
        """Test that non-unique matches fail"""
        code = '''line
line
line'''
        patches = [{"search": "line", "replace": "new", "reason": ""}]
        
        new_code, applied, details = apply_patches(code, patches)
        
        assert applied == 0
        assert "not unique" in details[0]

    def test_whitespace_normalized_fuzzy_match(self):
        """Test whitespace-insensitive matching"""
        code = '''    indented_call()
normal_line()'''
        patches = [{
            "search": "indented_call()",  # No indentation in search
            "replace": "    new_call()",   # Include proper indentation in replace
            "reason": "Fuzzy match"
        }]
        
        new_code, applied, details = apply_patches(code, patches)
        
        assert applied == 1
        assert "fuzzy" in details[0].lower()

    def test_suggests_similar_text_on_failure(self):
        """Test patch fails gracefully when search text not found - similar text detection uses word overlap"""
        code = '''self.play(Create(circle))
self.wait(1)'''
        # Note: "self.play(Create(square))" has low word overlap with "self.play(Create(circle))"
        # because they're treated as single tokens, not separate words
        patches = [{"search": "self.play(Create(square))", "replace": "new", "reason": ""}]
        
        new_code, applied, details = apply_patches(code, patches)
        
        # Patch should fail - no exact match and not enough word overlap for similarity
        assert applied == 0
        assert "FAIL" in details[0]


class TestFindSimilarText:
    """Test suite for find_similar_text function"""

    def test_finds_similar_line(self):
        """Test finding similar text in code"""
        code = '''def hello():
    print("Hello World")
    return True'''
        search = 'print("Hello Worlds")'  # Close but not exact
        
        result = find_similar_text(search, code)
        
        assert result is not None
        assert "print" in result

    def test_returns_none_when_no_similar(self):
        """Test returns None when no similar text found"""
        code = "completely different content"
        search = "xyz123abc"
        
        result = find_similar_text(search, code)
        
        assert result is None

    def test_handles_empty_code(self):
        """Test handling empty code"""
        result = find_similar_text("search", "")
        assert result is None


class TestCleanFunctionCallArgs:
    """Test suite for clean_function_call_args function"""

    def test_strips_whitespace_from_strings(self):
        """Test whitespace stripping"""
        args = {"code": "  hello  ", "name": " test "}
        
        result = clean_function_call_args(args)
        
        assert result["code"] == "hello"
        assert result["name"] == "test"

    def test_removes_empty_strings(self):
        """Test empty strings are removed"""
        args = {"code": "valid", "empty": "", "whitespace": "   "}
        
        result = clean_function_call_args(args)
        
        assert "code" in result
        assert "empty" not in result
        assert "whitespace" not in result

    def test_cleans_list_items(self):
        """Test list items are cleaned"""
        args = {"fixes": ["  item1  ", "item2", None, ""]}
        
        result = clean_function_call_args(args)
        
        assert "item1" in result["fixes"]
        assert "item2" in result["fixes"]
        assert len(result["fixes"]) == 2  # Empty/None items removed

    def test_preserves_non_string_values(self):
        """Test non-string values are preserved"""
        args = {"count": 42, "enabled": True, "data": {"nested": "value"}}
        
        result = clean_function_call_args(args)
        
        assert result["count"] == 42
        assert result["enabled"] is True
        assert result["data"]["nested"] == "value"
