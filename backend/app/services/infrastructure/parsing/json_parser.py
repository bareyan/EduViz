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

def extract_largest_balanced_json(text: str, expect_array: bool = False) -> Optional[str]:
    """Extract the largest balanced JSON object/array from text.

    Scans for balanced braces/brackets while respecting string literals and escapes.

    Args:
        text: Source text potentially containing JSON.
        expect_array: If True, only return a JSON array (starts with '[').

    Returns:
        The largest balanced JSON substring, or None if not found.
    """
    if not text:
        return None

    in_string = False
    string_char = ""
    escape = False
    stack: List[str] = []
    start_idx: Optional[int] = None
    best: Optional[str] = None

    for i, ch in enumerate(text):
        if in_string:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == string_char:
                in_string = False
            continue

        if ch in ("\"", "'"):
            in_string = True
            string_char = ch
            continue

        if ch in "{[":
            if not stack:
                start_idx = i
            stack.append(ch)
            continue

        if ch in "}]":
            if not stack:
                continue
            open_ch = stack[-1]
            if (open_ch == "{" and ch == "}") or (open_ch == "[" and ch == "]"):
                stack.pop()
                if not stack and start_idx is not None:
                    candidate = text[start_idx:i + 1]
                    if expect_array and candidate.lstrip().startswith("{"):
                        start_idx = None
                        continue
                    if best is None or len(candidate) > len(best):
                        best = candidate
                    start_idx = None
            else:
                # Mismatched closing; reset state.
                stack.clear()
                start_idx = None

    if best and expect_array and not best.lstrip().startswith("["):
        return None
    return best


def is_likely_truncated_json(text: str) -> bool:
    """Heuristic check for truncated JSON payloads.

    Detects unterminated strings or unbalanced braces/brackets while
    respecting escape sequences. Useful for distinguishing partial
    responses from other invalid JSON errors.
    """
    if not text:
        return False

    in_string = False
    string_char = ""
    escape = False
    stack: List[str] = []

    for ch in text:
        if in_string:
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == string_char:
                in_string = False
            continue

        if ch in ("\"", "'"):
            in_string = True
            string_char = ch
            continue

        if ch in "{[":
            stack.append(ch)
            continue
        if ch in "}]":
            if not stack:
                continue
            open_ch = stack[-1]
            if (open_ch == "{" and ch == "}") or (open_ch == "[" and ch == "]"):
                stack.pop()
            else:
                # Mismatched closure; treat as invalid but not necessarily truncation.
                return False

    return bool(stack) or in_string

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


def repair_json_payload(text: str) -> Optional[str]:
    """Attempt to repair malformed JSON payloads from LLM responses.

    Strategy:
    - Strip markdown fences while preserving content.
    - Extract the largest balanced JSON object.
    - If parsing fails, attempt to fix escape sequences.
    - If fix-schema JSON appears to contain a code block, convert it to
      full_code_lines with empty edits.

    Returns:
        A repaired JSON string or None if repair fails.
    """
    if not text:
        return None

    normalized = text.strip()
    if normalized.startswith("```"):
        lines = normalized.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        normalized = "\n".join(lines).strip()

    candidate = extract_largest_balanced_json(normalized, expect_array=False)
    if not candidate:
        return None

    try:
        json.loads(candidate)
        return candidate
    except json.JSONDecodeError:
        pass

    try:
        fixed = fix_json_escapes(candidate)
        json.loads(fixed)
        return fixed
    except json.JSONDecodeError:
        pass

    has_fix_keys = (
        "\"edits\"" in candidate
        or "\"full_code\"" in candidate
        or "\"full_code_lines\"" in candidate
    )
    code_block = re.search(r"```(?:python|py)?\n([\s\S]*?)```", text)
    if has_fix_keys and code_block:
        code_lines = [line.rstrip("\n") for line in code_block.group(1).splitlines()]
        payload = {"edits": [], "full_code_lines": code_lines}
        return json.dumps(payload)

    return None


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

    # Try balanced JSON extraction (brace matching)
    try:
        candidate = extract_largest_balanced_json(text, expect_array=False)
        if candidate:
            return json.loads(candidate)
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

    # Try balanced JSON extraction (brace matching)
    try:
        candidate = extract_largest_balanced_json(text, expect_array=True)
        if candidate:
            result = json.loads(candidate)
            if isinstance(result, list):
                return result
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

# Forward compatible imports - deprecated, import from code_parser instead
from .code_parser import (
    extract_markdown_code_blocks, 
    remove_markdown_wrappers as _remove_markdown_wrappers_impl, 
    validate_python_syntax
)

def remove_markdown_wrappers(text: str) -> str:
    """Delegate to code_parser implementation."""
    return _remove_markdown_wrappers_impl(text)



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
