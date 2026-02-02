"""
Code utilities - cleaning, normalization, scene file creation
"""

import re
from typing import Optional

from ..config import CONSTRUCT_INDENT_SPACES, MIN_DURATION_PADDING, DURATION_PADDING_PERCENTAGE

def get_theme_setup_code(style: str = "3b1b") -> str:
    """Returns the Manim setup code for a specific visual style.
    
    Args:
        style: The name of the style (e.g., '3b1b', 'light').
        
    Returns:
        A formatted string of Python code to be injected into construct().
    """
    if style == "light":
        return "        self.camera.background_color = \"#FFFFFF\"\n"
    # Default to 3b1b / dark theme
    return "        self.camera.background_color = \"#171717\"  # Slate dark\n"


def clean_code(code: str) -> str:
    """Clean up generated code while preserving nested indentation"""

    # Remove markdown code blocks
    if code.startswith("```"):
        lines = code.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        code = "\n".join(lines)

    # Remove any class definitions or imports that might have slipped in
    lines = code.split("\n")
    cleaned_lines = []
    skip_until_construct = False

    for line in lines:
        stripped = line.strip()
        # Skip import lines
        if stripped.startswith("from manim") or stripped.startswith("import"):
            continue
        # Skip class definition
        if stripped.startswith("class "):
            skip_until_construct = True
            continue
        if skip_until_construct:
            if "def construct" in line:
                skip_until_construct = False
            continue
        cleaned_lines.append(line)

    code = "\n".join(cleaned_lines)

    # Normalize indentation while PRESERVING relative indentation
    lines = code.split("\n")

    # Find the minimum non-zero indentation to understand the base level
    min_indent = float('inf')
    for line in lines:
        if line.strip():
            # Replace tabs with 4 spaces for counting
            normalized_line = line.replace('\t', '    ')
            indent = len(normalized_line) - len(normalized_line.lstrip())
            if indent > 0:
                min_indent = min(min_indent, indent)

    if min_indent == float('inf'):
        min_indent = 0

    # Re-indent: shift everything so base level is CONSTRUCT_INDENT_SPACES (inside construct)
    indented_lines = []
    for line in lines:
        if line.strip():
            # Replace tabs with 4 spaces
            normalized_line = line.replace('\t', '    ')
            current_indent = len(normalized_line) - len(normalized_line.lstrip())
            content = normalized_line.lstrip()

            # Calculate relative indentation (how many levels above base)
            if min_indent > 0:
                relative_indent = current_indent - min_indent
            else:
                relative_indent = current_indent

            # New indent: CONSTRUCT_INDENT_SPACES + relative indentation
            new_indent = CONSTRUCT_INDENT_SPACES + max(0, relative_indent)
            indented_lines.append(" " * new_indent + content)
        else:
            indented_lines.append("")

    return "\n".join(indented_lines)


def normalize_indentation(code: str) -> str:
    """Normalize indentation to use consistent 4-space indentation
    
    This fixes common issues:
    - Tabs converted to 4 spaces
    - Mixed tabs/spaces normalized
    - Inconsistent indentation levels fixed
    """
    lines = code.split('\n')
    normalized_lines = []

    for line in lines:
        if not line.strip():
            # Empty line
            normalized_lines.append('')
            continue

        # Count leading whitespace
        stripped = line.lstrip()
        leading = line[:len(line) - len(stripped)]

        # Replace tabs with 4 spaces
        leading = leading.replace('\t', '    ')

        # Count the indentation level (how many 4-space units)
        # Handle cases where spaces might not be exact multiples of 4
        space_count = len(leading)
        indent_level = (space_count + 2) // 4  # Round to nearest 4

        # Reconstruct with clean 4-space indentation
        normalized_lines.append('    ' * indent_level + stripped)

    return '\n'.join(normalized_lines)


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
    """Create a complete Manim scene file with minimum duration padding and enforced theme
    
    The theme is enforced at the scene level to ensure consistency across all sections.
    Any theme-related code in the AI-generated content is stripped to prevent conflicts.
    """

    # Strip any theme code from the AI-generated content
    code = strip_theme_code_from_content(code)

    # Normalize indentation to fix any tab/space issues from AI generation
    normalized_code = normalize_indentation(code)

    # Ensure the code has proper base indentation for inside construct()
    lines = normalized_code.split('\n')
    indented_lines = []
    for line in lines:
        if line.strip():
            # Ensure minimum CONSTRUCT_INDENT_SPACES indentation (inside construct method)
            current_indent = len(line) - len(line.lstrip())
            if current_indent < CONSTRUCT_INDENT_SPACES:
                # Add base indentation to reach CONSTRUCT_INDENT_SPACES for construct body
                line = ' ' * CONSTRUCT_INDENT_SPACES + line.lstrip()
        indented_lines.append(line)
    normalized_code = '\n'.join(indented_lines)

    # Sanitize section_id for class name
    class_name = "".join(word.title() for word in section_id.split("_"))

    # Calculate padding using config constants
    padding_wait = max(MIN_DURATION_PADDING, duration * DURATION_PADDING_PERCENTAGE)

    # Get theme setup code
    theme_setup = get_theme_setup_code(style)

    scene_code = f'''"""Auto-generated Manim scene for section: {section_id}"""
from manim import *

class Scene{class_name}(Scene):
    def construct(self):
        # ══════════════════════════════════════════════════════════════════
        # TARGET DURATION: {duration:.1f} seconds (must sync with audio)
        # Your animations + waits should total approximately this duration
        # A padding wait is added at the end to ensure minimum duration
        # ══════════════════════════════════════════════════════════════════
        
{theme_setup}
{normalized_code}
        
        # ══════════════════════════════════════════════════════════════════
        # DURATION PADDING: Extra wait to ensure video >= audio duration
        # This shows the final state while remaining narration plays
        # ══════════════════════════════════════════════════════════════════
        self.wait({padding_wait:.1f})
'''
    return scene_code


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


def remove_markdown_blocks(code: str) -> str:
    """Remove markdown code block delimiters from code"""
    if code.startswith("```"):
        lines = code.split("\n")
        # Remove first line if it's ```python or ```
        if lines[0].strip().startswith("```"):
            lines = lines[1:]
        # Remove last line if it's ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        code = "\n".join(lines)
    return code


def ensure_manim_structure(code: str) -> bool:
    """Check if code has basic Manim structure"""
    return (
        "from manim import" in code and
        "class " in code and
        "def construct" in code
    )
