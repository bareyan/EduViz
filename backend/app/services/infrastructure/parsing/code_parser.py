"""
Code Parsing Utilities

Provides robust utilities for extracting, cleaning, and validating code blocks
from LLM responses. Follows SRP by handling only code-string manipulation.
"""

import re
import ast
from typing import List, Optional

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
    # Case insensitive match for language
    pattern = rf'```{language}\n(.*?)```'
    matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
    
    if not matches:
        # Fallback: try finding blocks without language specifier if we asked for python
        # and didn't find specific ones, OR just return generic blocks
        pattern_generic = r'```\n(.*?)```'
        matches_generic = re.findall(pattern_generic, text, re.DOTALL)
        if matches_generic:
            return matches_generic
            
    blocks.extend(matches)
    return blocks

def remove_markdown_wrappers(text: str) -> str:
    """Remove markdown code fence wrappers from text.
    
    Args:
        text: Text potentially wrapped in ```...```
        
    Returns:
        Unwrapped text
    """
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line if it starts with ```
        if lines[0].strip().startswith("```"):
            lines.pop(0)
        # Remove last line if it starts with ```
        if lines and lines[-1].strip().startswith("```"):
            lines.pop()
        text = "\n".join(lines)

    return text.strip()

def validate_python_syntax(code: str) -> Optional[str]:
    """Validate Python syntax.
    
    Args:
        code: Python code to validate
        
    Returns:
        Error message if invalid, None if valid
    """
    try:
        ast.parse(code)
        return None
    except SyntaxError as e:
        return f"Syntax error at line {e.lineno}: {e.msg}"
    except Exception as e:
        return f"Validation error: {str(e)}"

def normalize_indentation(code: str, base_spaces: int = 0) -> str:
    """Normalize indentation of code block to a specific base level.
    
    Preserves relative indentation between lines.
    
    Args:
        code: The code string to normalize.
        base_spaces: The number of spaces to prepend to the normalized block.
        
    Returns:
        Normalized code string.
    """
    lines = code.split("\n")
    
    # Find the minimum non-zero indentation to understand the current base level
    min_indent = float('inf')
    for line in lines:
        if line.strip():
            # Replace tabs with 4 spaces for counting
            normalized_line = line.replace('\t', '    ')
            indent = len(normalized_line) - len(normalized_line.lstrip())
            # We track the minimum indentation found
            min_indent = min(min_indent, indent)

    if min_indent == float('inf'):
        min_indent = 0

    # Re-indent
    indented_lines = []
    base_indent_str = " " * base_spaces
    
    for line in lines:
        if line.strip():
            # Replace tabs with 4 spaces
            normalized_line = line.replace('\t', '    ')
            current_indent = len(normalized_line) - len(normalized_line.lstrip())
            content = normalized_line.lstrip()

            # Calculate relative indentation (how many levels above base)
            # If min_indent is 0, relative is just current
            relative_indent = current_indent - min_indent if min_indent > 0 else current_indent

            # New indent: base_spaces + relative indentation
            # Ensure we don't go negative
            new_indent_len = max(0, relative_indent)
            indented_lines.append(base_indent_str + (" " * new_indent_len) + content)
        else:
            indented_lines.append("") # Keep empty lines
            
    return "\n".join(indented_lines)
