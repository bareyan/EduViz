"""
Tests for Manim code generation tools

Ensures tool execution and integration works correctly.
"""

import pytest
from app.services.manim_generator.tools import (
    extract_code_from_response,
    apply_search_replace,
    ToolExecutor,
    MANIM_TOOLS
)


class TestExtractCodeFromResponse:
    """Test code extraction from various formats"""
    
    def test_extract_python_markdown(self):
        """Test extraction from ```python``` blocks"""
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
    
    def test_extract_generic_markdown(self):
        """Test extraction from generic ``` blocks"""
        response = """```
def hello():
    print("World")
```"""
        
        code = extract_code_from_response(response)
        
        assert "def hello():" in code
        assert "```" not in code
    
    def test_plain_code(self):
        """Test when response is just code without markers"""
        response = """from manim import *

class MyScene(Scene):
    def construct(self):
        pass"""
        
        code = extract_code_from_response(response)
        
        assert code == response.strip()


class TestApplySearchReplace:
    """Test search/replace operations"""
    
    def test_successful_replace(self):
        """Test successful single replacement"""
        code = """from manim import *

class MyScene(Scene):
    def construct(self):
        text = Text("Old Text")
        self.play(Write(text))"""
        
        success, new_code, error = apply_search_replace(
            code,
            'Text("Old Text")',
            'Text("New Text")'
        )
        
        assert success is True
        assert 'Text("New Text")' in new_code
        assert 'Text("Old Text")' not in new_code
        assert error == ""
    
    def test_pattern_not_found(self):
        """Test when search pattern doesn't exist"""
        code = """from manim import *

class MyScene(Scene):
    def construct(self):
        pass"""
        
        success, new_code, error = apply_search_replace(
            code,
            'Text("Missing")',
            'Text("New")'
        )
        
        assert success is False
        assert new_code == code  # Unchanged
        assert "not found" in error.lower()
    
    def test_multiple_occurrences(self):
        """Test when search pattern appears multiple times"""
        code = """from manim import *

class MyScene(Scene):
    def construct(self):
        text1 = Text("Hello")
        text2 = Text("Hello")"""
        
        success, new_code, error = apply_search_replace(
            code,
            'Text("Hello")',
            'Text("World")'
        )
        
        assert success is False
        assert "2 times" in error or "multiple" in error.lower()
    
    def test_empty_search(self):
        """Test with empty search pattern"""
        code = "some code"
        
        success, new_code, error = apply_search_replace(
            code,
            '',
            'replacement'
        )
        
        assert success is False
        assert "empty" in error.lower()


class TestToolExecutor:
    """Test tool executor"""
    
    def setup_method(self):
        """Set up test fixtures"""
        self.executor = ToolExecutor()
    
    def test_validate_code_tool_valid(self):
        """Test validate_code with valid code"""
        result = self.executor.execute("validate_code", {
            "code": """
from manim import *

class MyScene(Scene):
    def construct(self):
        text = Text("Hello")
        self.play(Write(text))
        self.wait()
"""
        })
        
        assert isinstance(result, dict)
        assert result["valid"] is True
        assert "syntax" in result
        assert "structure" in result
        assert "imports" in result
    
    def test_validate_code_tool_invalid(self):
        """Test validate_code with invalid code"""
        result = self.executor.execute("validate_code", {
            "code": """
from manim import Scene

class MyScene(Scene)
    def construct(self):
        text = Text("Hello")
"""
        })
        
        assert isinstance(result, dict)
        assert result["valid"] is False
        assert result["syntax"]["valid"] is False
    
    def test_apply_fix_tool_success(self):
        """Test apply_fix with valid fix"""
        code = """from manim import *

class MyScene(Scene):
    def construct(self):
        text = Text("Old")"""
        
        result = self.executor.execute("apply_fix", {
            "code": code,
            "search": 'Text("Old")',
            "replace": 'Text("New")',
            "reason": "Updating text"
        })
        
        assert result["success"] is True
        assert 'Text("New")' in result["new_code"]
        assert result["reason"] == "Updating text"
    
    def test_apply_fix_tool_failure(self):
        """Test apply_fix with pattern not found"""
        code = """from manim import *

class MyScene(Scene):
    def construct(self):
        pass"""
        
        result = self.executor.execute("apply_fix", {
            "code": code,
            "search": 'Text("Missing")',
            "replace": 'Text("New")',
            "reason": "Fix"
        })
        
        assert result["success"] is False
        assert len(result["error"]) > 0
    
    def test_finalize_code_tool_valid(self):
        """Test finalize_code with valid code"""
        code = """from manim import *

class MyScene(Scene):
    def construct(self):
        text = Text("Hello")
        self.wait()"""
        
        result = self.executor.execute("finalize_code", {
            "code": code
        })
        
        assert result["accepted"] is True
        assert result["code"] == code
        assert "validation" in result
    
    def test_finalize_code_tool_invalid(self):
        """Test finalize_code with invalid code"""
        code = """def broken()
    pass"""
        
        result = self.executor.execute("finalize_code", {
            "code": code
        })
        
        assert result["accepted"] is False
        assert result["validation"]["valid"] is False
    
    def test_unknown_tool(self):
        """Test execution of unknown tool"""
        result = self.executor.execute("unknown_tool", {})
        
        assert "error" in result
        assert "unknown" in result["error"].lower()


class TestToolDefinitions:
    """Test tool definition structure"""
    
    def test_all_tools_have_required_fields(self):
        """Test that all tools have proper structure"""
        for tool in MANIM_TOOLS:
            assert "name" in tool
            assert "description" in tool
            assert "parameters" in tool
            assert isinstance(tool["name"], str)
            assert isinstance(tool["description"], str)
            assert isinstance(tool["parameters"], dict)
    
    def test_tool_parameters_schema(self):
        """Test that tool parameters follow JSON schema"""
        for tool in MANIM_TOOLS:
            params = tool["parameters"]
            assert "type" in params
            assert params["type"] == "object"
            assert "properties" in params
            assert "required" in params
            assert isinstance(params["properties"], dict)
            assert isinstance(params["required"], list)
