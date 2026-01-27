"""
Shared JSON and code parsing utilities to eliminate duplication.

This module provides common utilities for:
- JSON response parsing from LLM with error recovery
- Code cleaning and validation
- Text extraction and normalization
"""

import json
import re
from typing import Dict, Any, List, Optional


# ============================================================================
# JSON Parsing Utilities
# ============================================================================

def fix_json_escapes(text: str) -> str:
    """Fix common JSON escape sequence issues from LLM responses.
    
    Handles invalid escape sequences by escaping lone backslashes while
    preserving valid JSON escapes.
    
    Args:
        text: Text potentially containing invalid escape sequences
        
    Returns:
        Fixed text with valid JSON escape sequences
    """
    # Valid JSON escapes: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX

    # First, temporarily replace valid escapes
    valid_escapes = {
        '\\"': '<<QUOTE>>',
        '\\\\': '<<BACKSLASH>>',
        '\\/': '<<SLASH>>',
        '\\b': '<<BACKSPACE>>',
        '\\f': '<<FORMFEED>>',
        '\\n': '<<NEWLINE>>',
        '\\r': '<<RETURN>>',
        '\\t': '<<TAB>>',
    }

    for old, new in valid_escapes.items():
        text = text.replace(old, new)

    # Handle unicode escapes \uXXXX
    text = re.sub(r'\\u([0-9a-fA-F]{4})', r'<<UNICODE_\1>>', text)

    # Now escape any remaining backslashes (invalid escapes)
    text = text.replace('\\', '\\\\')

    # Restore valid escapes
    for old, new in valid_escapes.items():
        text = text.replace(new, old)

    # Restore unicode escapes
    text = re.sub(r'<<UNICODE_([0-9a-fA-F]{4})>>', r'\\u\1', text)

    return text


def parse_json_response(text: str, default: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Parse JSON from LLM response with comprehensive error recovery.
    
    Handles:
    - Markdown code block wrapping (```json ... ```)
    - Invalid escape sequences
    - Malformed JSON with fallback extraction via regex
    
    Args:
        text: Text potentially containing JSON
        default: Default value to return on parse failure
        
    Returns:
        Parsed JSON dict or default if parsing fails
    """
    if default is None:
        default = {}

    text = text.strip()

    # Remove markdown code blocks if present
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove lines that are code fence markers
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try fixing escape sequences
    try:
        fixed_text = fix_json_escapes(text)
        return json.loads(fixed_text)
    except json.JSONDecodeError:
        pass

    # Last resort: try to extract JSON using regex
    try:
        # Match either {...} or [...]
        match = re.search(r'[\{\[][\s\S]*[\}\]]', text)
        if match:
            json_str = match.group(0)
            return json.loads(json_str)
    except json.JSONDecodeError:
        pass

    return default


def parse_json_array_response(text: str, default: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
    """Parse JSON array from LLM response.
    
    Handles markdown wrapping and escape issues like parse_json_response
    but expects an array instead of object.
    
    Args:
        text: Text potentially containing JSON array
        default: Default value to return on parse failure
        
    Returns:
        Parsed JSON array or default if parsing fails
    """
    if default is None:
        default = []

    text = text.strip()

    # Remove markdown code blocks
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    # Try direct parse
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
        return default
    except json.JSONDecodeError:
        pass

    # Try fixing escape sequences
    try:
        fixed_text = fix_json_escapes(text)
        result = json.loads(fixed_text)
        if isinstance(result, list):
            return result
        return default
    except json.JSONDecodeError:
        pass

    # Last resort: extract array
    try:
        match = re.search(r'\[[\s\S]*\]', text)
        if match:
            result = json.loads(match.group(0))
            if isinstance(result, list):
                return result
    except json.JSONDecodeError:
        pass

    return default


# ============================================================================
# Code Parsing and Validation Utilities
# ============================================================================

def extract_markdown_code_blocks(text: str, language: str = "python") -> List[str]:
    """Extract code blocks from markdown text.
    
    Args:
        text: Text containing markdown code blocks
        language: Programming language to extract (e.g., "python", "json")
        
    Returns:
        List of code block contents
    """
    blocks = []

    # Pattern for fenced code blocks with optional language
    pattern = rf'```{language}\n(.*)```'
    matches = re.findall(pattern, text, re.DOTALL)
    blocks.extend(matches)

    return blocks


def remove_markdown_wrappers(text: str) -> str:
    """Remove markdown code fence wrappers from text.
    
    Args:
        text: Text potentially wrapped in ```...```
        
    Returns:
        Unwrapped text
    """
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    return text.strip()


def validate_python_syntax(code: str) -> Optional[str]:
    """Validate Python code syntax.
    
    Args:
        code: Python code to validate
        
    Returns:
        Error message if invalid, None if valid
    """
    try:
        compile(code, '<string>', 'exec')
        return None
    except SyntaxError as e:
        return f"SyntaxError at line {e.lineno}: {e.msg}"
    except Exception as e:
        return f"{type(e).__name__}: {str(e)}"


# ============================================================================
# Text Processing Utilities
# ============================================================================

def normalize_whitespace(text: str) -> str:
    """Normalize whitespace in text.
    
    - Converts tabs to spaces
    - Collapses multiple spaces
    - Removes leading/trailing whitespace
    
    Args:
        text: Text to normalize
        
    Returns:
        Normalized text
    """
    text = text.replace('\t', '    ')  # Convert tabs to 4 spaces
    text = re.sub(r' +', ' ', text)     # Collapse multiple spaces
    return text.strip()


def extract_text_between_markers(text: str, start_marker: str, end_marker: str) -> Optional[str]:
    """Extract text between two markers.
    
    Args:
        text: Text to search
        start_marker: Starting marker
        end_marker: Ending marker
        
    Returns:
        Extracted text or None if markers not found
    """
    try:
        start_idx = text.index(start_marker)
        end_idx = text.index(end_marker, start_idx + len(start_marker))
        return text[start_idx + len(start_marker):end_idx].strip()
    except ValueError:
        return None


def split_into_lines(text: str, skip_empty: bool = True) -> List[str]:
    """Split text into lines.
    
    Args:
        text: Text to split
        skip_empty: Skip empty lines
        
    Returns:
        List of lines
    """
    lines = text.split('\n')
    if skip_empty:
        lines = [l for l in lines if l.strip()]
    return lines
