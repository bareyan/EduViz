"""
SEARCH/REPLACE Block Parser

Parses Aider-style SEARCH/REPLACE blocks from LLM responses.
Based on Aider's proven implementation (github.com/Aider-AI/aider)

Format:
    <<<<<<< SEARCH
    text to find
    =======
    replacement text
    >>>>>>> REPLACE
"""

import re
from typing import List, Optional
from dataclasses import dataclass


# Regex patterns for SEARCH/REPLACE markers - more flexible matching
# Matches: <<<<<<< SEARCH, <<<<< SEARCH, <<< SEARCH, SEARCH:, etc.
HEAD = r"^<{3,9}\s*SEARCH>?\s*$"
DIVIDER = r"^={3,9}\s*$"
UPDATED = r"^>{3,9}\s*REPLACE\s*$"

head_pattern = re.compile(HEAD, re.IGNORECASE)
divider_pattern = re.compile(DIVIDER)
updated_pattern = re.compile(UPDATED, re.IGNORECASE)


@dataclass
class SearchReplaceBlock:
    """A single SEARCH/REPLACE block"""
    search: str
    replace: str
    line_number: Optional[int] = None  # Line in LLM response where block started


def find_search_replace_blocks(content: str) -> List[SearchReplaceBlock]:
    """
    Parse SEARCH/REPLACE blocks from LLM response.
    
    Args:
        content: The full LLM response text
        
    Returns:
        List of SearchReplaceBlock objects
    """
    blocks = []
    lines = content.splitlines(keepends=True)
    i = 0

    while i < len(lines):
        line = lines[i]

        # Look for SEARCH marker
        if head_pattern.match(line.strip()):
            block_start = i
            search_lines = []
            replace_lines = []

            i += 1
            # Collect SEARCH content until DIVIDER
            while i < len(lines) and not divider_pattern.match(lines[i].strip()):
                search_lines.append(lines[i])
                i += 1

            if i >= len(lines):
                # Malformed block - no divider found
                break

            i += 1  # Skip divider

            # Collect REPLACE content until REPLACE marker
            while i < len(lines) and not updated_pattern.match(lines[i].strip()):
                replace_lines.append(lines[i])
                i += 1

            if i >= len(lines):
                # Malformed block - no REPLACE marker found
                break

            # Create block
            search_text = "".join(search_lines)
            replace_text = "".join(replace_lines)

            blocks.append(SearchReplaceBlock(
                search=search_text,
                replace=replace_text,
                line_number=block_start
            ))

        i += 1

    return blocks


def extract_blocks_from_fenced(content: str) -> List[SearchReplaceBlock]:
    """
    Extract SEARCH/REPLACE blocks that may be inside markdown fences.
    
    Handles formats like:
        ```python
        <<<<<<< SEARCH
        ...
        ```
    """
    # Remove markdown code fences but preserve content
    # This handles cases where LLM wraps response in ```python ... ```
    fence_pattern = r"```(?:\w+)?\n(.*?)```"

    # First try to find blocks in the raw content
    blocks = find_search_replace_blocks(content)

    if blocks:
        return blocks

    # If no blocks found, try extracting from fenced sections
    fenced_matches = re.findall(fence_pattern, content, re.DOTALL)
    for match in fenced_matches:
        blocks.extend(find_search_replace_blocks(match))

    return blocks


def validate_block(block: SearchReplaceBlock) -> Optional[str]:
    """
    Validate a SEARCH/REPLACE block.
    
    Returns:
        None if valid, error message if invalid
    """
    if not block.search.strip() and not block.replace.strip():
        return "Both SEARCH and REPLACE sections are empty"

    # Empty SEARCH with content in REPLACE = append operation (valid)
    # Empty REPLACE with content in SEARCH = delete operation (valid)

    return None
