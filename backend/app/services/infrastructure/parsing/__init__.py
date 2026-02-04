"""
Parsing Module

Provides utilities for parsing JSON and code from LLM responses.

Usage:
    from app.services.infrastructure.parsing import parse_json_response, extract_markdown_code_blocks
"""

from .json_parser import (
    parse_json_response,
    parse_json_array_response,
    parse_json_strict,
    JsonParseResult,
    looks_truncated_json,
    fix_json_escapes,
    extract_markdown_code_blocks,
    remove_markdown_wrappers,
    validate_python_syntax,
    normalize_whitespace,
    extract_text_between_markers,
    split_into_lines,
)

__all__ = [
    "parse_json_response",
    "parse_json_array_response",
    "parse_json_strict",
    "JsonParseResult",
    "looks_truncated_json",
    "fix_json_escapes",
    "extract_markdown_code_blocks",
    "remove_markdown_wrappers",
    "validate_python_syntax",
    "normalize_whitespace",
    "extract_text_between_markers",
    "split_into_lines",
]
