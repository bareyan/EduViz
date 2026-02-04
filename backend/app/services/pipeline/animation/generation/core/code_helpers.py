"""
Code utilities - cleaning, normalization, scene file creation
"""

import re
from typing import Optional

from app.services.infrastructure.parsing.code_parser import (
    extract_markdown_code_blocks,
    normalize_indentation,
    remove_markdown_wrappers
)
from ...config import (
    CONSTRUCT_INDENT_SPACES, 
    MIN_DURATION_PADDING, 
    DURATION_PADDING_PERCENTAGE,
    THEME_SETUP_CODES
)

def get_theme_setup_code(style: str = "3b1b") -> str:
    """Returns the Manim setup code for a specific visual style.
    
    Args:
        style: The name of the style (e.g., '3b1b', 'light').
        
    Returns:
        A formatted string of Python code to be injected into construct().
    """
    return THEME_SETUP_CODES.get(style, THEME_SETUP_CODES["3b1b"])


def clean_code(code_text: Optional[str]) -> str:
    """Extracts Python code from LLM response.
    
    This function extracts Python code blocks from markdown and performs
    minimal cleaning. It no longer filters structural lines or re-indents
    as we expect the LLM to provide a complete, correctly formatted file.
    """
    if code_text is None:
        return ""
        
    # 1. Extract Python code block if present
    blocks = extract_markdown_code_blocks(code_text, "python")
    if blocks:
        # Take the longest block if multiple
        extracted_code = max(blocks, key=len)
    else:
        # Fallback: remove wrappers if it's just a raw code block
        extracted_code = remove_markdown_wrappers(code_text)

    # 2. Basic cleaning (strip whitespace)
    return extracted_code.strip()


def strip_theme_code_from_content(code: str) -> str:
    """Remove any theme-related code from AI-generated content
    
    This prevents the AI from overriding the enforced theme.
    We strip background_color settings since we enforce them at the scene level.
    """
    lines = code.split('\n')
    filtered_lines = []

    for line in lines:
        # Skip lines that set background_color (we enforce this at scene level)
        if 'background_color' in line and ('camera' in line or 'self.camera' in line):
            continue
        # Skip lines that only set background without content
        if re.match(r'^\s*self\.camera\.background_color\s*=', line.strip()):
            continue
        filtered_lines.append(line)

    return '\n'.join(filtered_lines)


def create_scene_file(code: str, section_id: str, duration: float, style: str = "3b1b") -> str:
    """Ensures the generated code is a complete Manim scene file.
    
    Since the LLM now provides the full file structure, this function primarily
    ensures basic requirements are met:
    1. Theme setup is consistent
    2. Final duration padding is added if missing
    """
    # Fix any translated common issues
    code = fix_translated_code(code)
    
    # Ensure background color is set according to style if not present
    theme_setup = get_theme_setup_code(style).strip()
    if theme_setup and theme_setup not in code:
        # Find construct(self): and insert theme setup
        match = re.search(r"def construct\(self\):", code)
        if match:
            insertion_point = match.end()
            # Find the indentation of the next line to match it
            lines = code[insertion_point:].split("\n", 2)
            if len(lines) > 1:
                next_line = lines[1]
                indent = re.match(r"^\s*", next_line).group(0)
                # If next line is just a comment or empty, default to 8 spaces
                if not indent or not next_line.strip():
                    indent = " " * CONSTRUCT_INDENT_SPACES
            else:
                indent = " " * CONSTRUCT_INDENT_SPACES
                
            code = code[:insertion_point] + "\n" + indent + theme_setup.strip() + "\n" + code[insertion_point:]

    # Add final padding wait if it seems missing
    # We look for self.wait( at the end of the file
    if "self.wait(" not in code[-200:]:
        padding_wait = max(MIN_DURATION_PADDING, duration * DURATION_PADDING_PERCENTAGE)
        # Find indentation of the last line to match it
        lines = code.strip().split("\n")
        last_indent = ""
        for line in reversed(lines):
            if line.strip():
                last_indent = re.match(r"^\s*", line).group(0)
                break
        if not last_indent:
            last_indent = " " * CONSTRUCT_INDENT_SPACES
            
        code = code.strip() + f"\n\n{last_indent}# Final padding to ensure video >= audio duration\n{last_indent}self.wait({padding_wait:.1f})\n"

    return code


def fix_translated_code(code: str) -> str:
    """Fix common issues in translated Manim code"""

    lines = code.split('\n')
    fixed_lines = []

    for i, line in enumerate(lines):
        # Fix: First line is a bare comment without quotes (should be docstring or comment)
        # Pattern: starts with text like "Auto-generated..." without # or """
        if i == 0 and line.strip() and not line.strip().startswith(('#', '"', "'", 'from', 'import')):
            # Check if it looks like a docstring that lost its quotes
            if 'auto-generated' in line.lower() or 'manim scene' in line.lower() or 'section:' in line.lower():
                fixed_lines.append(f'"""{line}"""')
                continue
            # Otherwise make it a comment
            elif not line.strip().startswith('class'):
                fixed_lines.append(f'# {line}')
                continue

        # Fix: Unquoted text that should be a comment
        # (lines that are just plain text, not code)
        stripped = line.strip()
        if stripped and i < 5:  # Only check first few lines
            # If it's not a valid Python start and not empty
            if not stripped.startswith(('#', '"', "'", 'from', 'import', 'class', 'def', '@', '"""')):
                if not any(c in stripped for c in ['=', '(', ')', '[', ']', ':', '+', '-', '*', '/']):
                    # Looks like plain text, make it a comment
                    fixed_lines.append(f'# {line}')
                    continue

        fixed_lines.append(line)

    result = '\n'.join(fixed_lines)

    # Ensure the code starts with proper import if missing
    if 'from manim import' not in result and 'import manim' not in result:
        # Find where to insert import (after any docstrings/comments at top)
        insert_pos = 0
        for i, line in enumerate(fixed_lines):
            stripped = line.strip()
            if stripped and not stripped.startswith(('#', '"""', "'''")):
                if not (stripped.startswith('"""') or stripped.endswith('"""')):
                    insert_pos = i
                    break

        fixed_lines.insert(insert_pos, 'from manim import *\n')
        result = '\n'.join(fixed_lines)

    return result


def extract_scene_name(code: str) -> Optional[str]:
    """Extract the Scene class name from Manim code"""
    match = re.search(r"class\s+(\w+)\s*\(\s*Scene\s*\)", code)
    if match:
        return match.group(1)
    return None




def ensure_manim_structure(code: str) -> bool:
    """Check if code has basic Manim structure"""
    return (
        "from manim import" in code and
        "class " in code and
        "def construct" in code
    )
