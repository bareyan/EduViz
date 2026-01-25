"""
Tests for diff_correction module

Run with: python -m pytest tests/test_diff_correction.py -v
"""

import pytest
from app.services.diff_correction.parser import find_search_replace_blocks, SearchReplaceBlock
from app.services.diff_correction.applier import apply_search_replace, apply_all_blocks, validate_syntax


class TestParser:
    """Tests for SEARCH/REPLACE block parsing"""
    
    def test_parse_single_block(self):
        content = """Here's the fix:

<<<<<<< SEARCH
text.to_edge(BOTTOM)
=======
text.to_edge(DOWN)
>>>>>>> REPLACE
"""
        blocks = find_search_replace_blocks(content)
        assert len(blocks) == 1
        assert "BOTTOM" in blocks[0].search
        assert "DOWN" in blocks[0].replace
    
    def test_parse_multiple_blocks(self):
        content = """Fix 1:

<<<<<<< SEARCH
color = blue
=======
color = BLUE
>>>>>>> REPLACE

Fix 2:

<<<<<<< SEARCH
text.to_edge(BOTTOM)
=======
text.to_edge(DOWN)
>>>>>>> REPLACE
"""
        blocks = find_search_replace_blocks(content)
        assert len(blocks) == 2
    
    def test_parse_with_indentation(self):
        content = """
<<<<<<< SEARCH
        text = Text("Hello")
        text.to_edge(BOTTOM)
=======
        text = Text("Hello")
        text.to_edge(DOWN)
>>>>>>> REPLACE
"""
        blocks = find_search_replace_blocks(content)
        assert len(blocks) == 1
        assert "        text" in blocks[0].search  # Preserve indentation
    
    def test_empty_content(self):
        blocks = find_search_replace_blocks("")
        assert len(blocks) == 0
    
    def test_malformed_block_no_replace(self):
        content = """
<<<<<<< SEARCH
some text
=======
replacement
"""
        blocks = find_search_replace_blocks(content)
        assert len(blocks) == 0  # Incomplete block


class TestApplier:
    """Tests for applying SEARCH/REPLACE blocks"""
    
    def test_exact_match(self):
        code = """def hello():
    text.to_edge(BOTTOM)
    return text
"""
        result = apply_search_replace(code, "text.to_edge(BOTTOM)", "text.to_edge(DOWN)")
        assert result.success
        assert "DOWN" in result.new_code
        assert "BOTTOM" not in result.new_code
        assert result.match_type == 'exact'
    
    def test_multiline_match(self):
        code = """def hello():
    text = Text("Hello")
    text.to_edge(BOTTOM)
    return text
"""
        search = """    text = Text("Hello")
    text.to_edge(BOTTOM)"""
        replace = """    text = Text("Hello")
    text.to_edge(DOWN)"""
        
        result = apply_search_replace(code, search, replace)
        assert result.success
        assert "DOWN" in result.new_code
    
    def test_whitespace_adjusted_match(self):
        code = """        text.to_edge(BOTTOM)
"""
        # LLM might omit some leading whitespace
        search = "    text.to_edge(BOTTOM)"
        replace = "    text.to_edge(DOWN)"
        
        result = apply_search_replace(code, search, replace)
        # Should still work with whitespace adjustment
        assert result.success
        assert "DOWN" in result.new_code
    
    def test_no_match(self):
        code = "def hello(): pass"
        result = apply_search_replace(code, "nonexistent text", "replacement")
        assert not result.success
        assert result.error is not None
    
    def test_append_operation(self):
        code = "line1\nline2\n"
        result = apply_search_replace(code, "", "line3\n")
        assert result.success
        assert "line3" in result.new_code
        assert result.match_type == 'append'


class TestApplyAll:
    """Tests for applying multiple blocks"""
    
    def test_apply_multiple_blocks(self):
        code = """color = blue
text.to_edge(BOTTOM)
"""
        blocks = [
            SearchReplaceBlock(search="color = blue", replace="color = BLUE"),
            SearchReplaceBlock(search="to_edge(BOTTOM)", replace="to_edge(DOWN)"),
        ]
        
        new_code, successes, errors = apply_all_blocks(code, blocks)
        assert len(successes) == 2
        assert len(errors) == 0
        assert "BLUE" in new_code
        assert "DOWN" in new_code


class TestSyntaxValidation:
    """Tests for syntax validation"""
    
    def test_valid_syntax(self):
        code = "def hello():\n    return 'world'"
        error = validate_syntax(code)
        assert error is None
    
    def test_invalid_syntax(self):
        code = "def hello(\n    return"  # Missing closing paren
        error = validate_syntax(code)
        assert error is not None
        assert "SyntaxError" in error


class TestRealManimErrors:
    """Tests with real Manim error patterns"""
    
    def test_fix_bottom_to_down(self):
        code = '''from manim import *

class Section1(Scene):
    def construct(self):
        text = Text("Hello")
        text.to_edge(BOTTOM)
        self.play(Write(text))
'''
        search = "text.to_edge(BOTTOM)"
        replace = "text.to_edge(DOWN)"
        
        result = apply_search_replace(code, search, replace)
        assert result.success
        assert "DOWN" in result.new_code
        assert validate_syntax(result.new_code) is None
    
    def test_fix_color_case(self):
        code = '''from manim import *

class Section1(Scene):
    def construct(self):
        text = Text("Hello", color=blue)
'''
        search = "color=blue"
        replace = "color=BLUE"
        
        result = apply_search_replace(code, search, replace)
        assert result.success
        assert "BLUE" in result.new_code


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
