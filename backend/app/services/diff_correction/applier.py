"""
SEARCH/REPLACE Block Applier

Applies SEARCH/REPLACE blocks to code with fuzzy matching.
Handles common LLM issues like whitespace differences.

Based on Aider's proven implementation (github.com/Aider-AI/aider)
"""

import math
from difflib import SequenceMatcher
from typing import Optional, List, Tuple
from dataclasses import dataclass

from .parser import SearchReplaceBlock


@dataclass
class ApplyResult:
    """Result of applying a SEARCH/REPLACE block"""
    success: bool
    new_code: Optional[str] = None
    error: Optional[str] = None
    match_type: Optional[str] = None  # 'exact', 'whitespace', 'fuzzy'


def prep(content: str) -> Tuple[str, List[str]]:
    """Prepare content for matching - ensure trailing newline"""
    if content and not content.endswith("\n"):
        content += "\n"
    lines = content.splitlines(keepends=True)
    return content, lines


def perfect_replace(whole_lines: List[str], part_lines: List[str], replace_lines: List[str]) -> Optional[str]:
    """
    Try to find an exact match of part_lines in whole_lines and replace.
    
    Returns:
        The modified content if match found, None otherwise
    """
    part_tup = tuple(part_lines)
    part_len = len(part_lines)
    
    for i in range(len(whole_lines) - part_len + 1):
        whole_tup = tuple(whole_lines[i : i + part_len])
        if part_tup == whole_tup:
            res = whole_lines[:i] + replace_lines + whole_lines[i + part_len :]
            return "".join(res)
    
    return None


def match_but_for_leading_whitespace(whole_lines: List[str], part_lines: List[str]) -> Optional[str]:
    """
    Check if lines match except for consistent leading whitespace difference.
    
    Returns:
        The whitespace prefix to add if match found, None otherwise
    """
    if len(whole_lines) != len(part_lines):
        return None
    
    # Find the common leading whitespace difference
    add_leading = None
    for whole_line, part_line in zip(whole_lines, part_lines):
        if not part_line.strip():
            # Skip blank lines
            continue
            
        whole_stripped = whole_line.lstrip()
        part_stripped = part_line.lstrip()
        
        if whole_stripped != part_stripped:
            return None
        
        whole_leading = len(whole_line) - len(whole_stripped)
        part_leading = len(part_line) - len(part_stripped)
        
        diff = whole_leading - part_leading
        if diff < 0:
            return None
        
        leading = whole_line[:diff]
        
        if add_leading is None:
            add_leading = leading
        elif add_leading != leading:
            return None
    
    return add_leading or ""


def replace_part_with_missing_leading_whitespace(
    whole_lines: List[str], 
    part_lines: List[str], 
    replace_lines: List[str]
) -> Optional[str]:
    """
    Handle case where LLM omits leading whitespace uniformly.
    
    Returns:
        Modified content if match found with whitespace adjustment, None otherwise
    """
    # Find minimum leading whitespace in part/replace
    leading = []
    for p in part_lines:
        if p.strip():
            leading.append(len(p) - len(p.lstrip()))
    for p in replace_lines:
        if p.strip():
            leading.append(len(p) - len(p.lstrip()))
    
    if leading and min(leading) > 0:
        num_leading = min(leading)
        part_lines = [p[num_leading:] if p.strip() else p for p in part_lines]
        replace_lines = [p[num_leading:] if p.strip() else p for p in replace_lines]
    
    num_part_lines = len(part_lines)
    
    for i in range(len(whole_lines) - num_part_lines + 1):
        add_leading = match_but_for_leading_whitespace(
            whole_lines[i : i + num_part_lines], part_lines
        )
        
        if add_leading is None:
            continue
        
        # Apply whitespace adjustment to replace lines
        adjusted_replace = [
            add_leading + rline if rline.strip() else rline 
            for rline in replace_lines
        ]
        whole_lines = whole_lines[:i] + adjusted_replace + whole_lines[i + num_part_lines:]
        return "".join(whole_lines)
    
    return None


def replace_closest_edit_distance(
    whole_lines: List[str], 
    part: str, 
    part_lines: List[str], 
    replace_lines: List[str],
    similarity_thresh: float = 0.8
) -> Optional[str]:
    """
    Find the most similar chunk and replace it (fuzzy matching).
    
    Returns:
        Modified content if similar match found above threshold, None otherwise
    """
    max_similarity = 0
    most_similar_chunk_start = -1
    most_similar_chunk_end = -1
    
    scale = 0.1
    min_len = math.floor(len(part_lines) * (1 - scale))
    max_len = math.ceil(len(part_lines) * (1 + scale))
    
    for length in range(min_len, max_len + 1):
        for i in range(len(whole_lines) - length + 1):
            chunk = whole_lines[i : i + length]
            chunk_str = "".join(chunk)
            
            similarity = SequenceMatcher(None, chunk_str, part).ratio()
            
            if similarity > max_similarity:
                max_similarity = similarity
                most_similar_chunk_start = i
                most_similar_chunk_end = i + length
    
    if max_similarity < similarity_thresh:
        return None
    
    modified_whole = (
        whole_lines[:most_similar_chunk_start]
        + replace_lines
        + whole_lines[most_similar_chunk_end:]
    )
    return "".join(modified_whole)


def apply_search_replace(code: str, search: str, replace: str) -> ApplyResult:
    """
    Apply a single SEARCH/REPLACE to code.
    
    Tries multiple matching strategies:
    1. Perfect (exact) match
    2. Whitespace-adjusted match
    3. Fuzzy match (edit distance)
    
    Args:
        code: The original code
        search: Text to search for
        replace: Text to replace with
        
    Returns:
        ApplyResult with success status and new code or error
    """
    # Handle append operation (empty search)
    if not search.strip():
        if not code.endswith("\n"):
            code += "\n"
        return ApplyResult(
            success=True,
            new_code=code + replace,
            match_type='append'
        )
    
    # Handle delete operation (empty replace)
    if not replace.strip():
        replace = ""
    
    # Prepare content
    whole, whole_lines = prep(code)
    part, part_lines = prep(search)
    repl, replace_lines = prep(replace)
    
    # Strategy 1: Perfect match
    result = perfect_replace(whole_lines, part_lines, replace_lines)
    if result:
        return ApplyResult(success=True, new_code=result, match_type='exact')
    
    # Strategy 2: Whitespace-adjusted match (leading whitespace)
    result = replace_part_with_missing_leading_whitespace(whole_lines, part_lines, replace_lines)
    if result:
        return ApplyResult(success=True, new_code=result, match_type='whitespace')
    
    # Strategy 3: Strip trailing whitespace from both code and search
    # LLMs often mishandle trailing whitespace
    def strip_trailing(lines):
        return [line.rstrip() + '\n' for line in lines]
    
    stripped_whole = strip_trailing(whole_lines)
    stripped_part = strip_trailing(part_lines)
    result = perfect_replace(stripped_whole, stripped_part, replace_lines)
    if result:
        return ApplyResult(success=True, new_code=result, match_type='trailing_stripped')
    
    # Also try with whitespace adjustment on stripped versions
    result = replace_part_with_missing_leading_whitespace(stripped_whole, stripped_part, replace_lines)
    if result:
        return ApplyResult(success=True, new_code=result, match_type='trailing_stripped_ws')
    
    # Strategy 4: Try without leading blank line (LLM sometimes adds spurious blank lines)
    if len(part_lines) > 2 and not part_lines[0].strip():
        skip_blank_part_lines = part_lines[1:]
        result = perfect_replace(whole_lines, skip_blank_part_lines, replace_lines)
        if result:
            return ApplyResult(success=True, new_code=result, match_type='exact_skip_blank')
        
        result = replace_part_with_missing_leading_whitespace(whole_lines, skip_blank_part_lines, replace_lines)
        if result:
            return ApplyResult(success=True, new_code=result, match_type='whitespace_skip_blank')
    
    # Strategy 5: Fuzzy match with high threshold (0.9 = very similar)
    # Only for longer blocks where we can be more confident
    if len(part_lines) >= 3:
        result = replace_closest_edit_distance(whole_lines, part, part_lines, replace_lines, similarity_thresh=0.90)
        if result:
            return ApplyResult(success=True, new_code=result, match_type='fuzzy_90')
    
    # No match found - provide helpful debug info
    # Find most similar line for debugging
    first_part_line = part_lines[0].strip() if part_lines else ""
    similar_lines = []
    for i, line in enumerate(whole_lines):
        if first_part_line and SequenceMatcher(None, line.strip(), first_part_line).ratio() > 0.7:
            similar_lines.append(f"L{i+1}: {line.strip()[:40]}")
    
    error_msg = f"SEARCH block not found. First line: '{first_part_line[:50]}'"
    if similar_lines:
        error_msg += f" | Similar: {similar_lines[0]}"
    
    return ApplyResult(
        success=False,
        error=error_msg
    )


def apply_all_blocks(code: str, blocks: List[SearchReplaceBlock]) -> Tuple[str, List[str], List[str]]:
    """
    Apply all SEARCH/REPLACE blocks to code.
    
    Args:
        code: The original code
        blocks: List of SearchReplaceBlock objects
        
    Returns:
        Tuple of (resulting_code, list_of_success_messages, list_of_errors)
    """
    current_code = code
    successes = []
    errors = []
    
    for i, block in enumerate(blocks):
        result = apply_search_replace(current_code, block.search, block.replace)
        
        if result.success:
            current_code = result.new_code
            successes.append(f"Block {i+1}: Applied ({result.match_type})")
        else:
            errors.append(f"Block {i+1}: {result.error}")
    
    return current_code, successes, errors


def validate_syntax(code: str) -> Optional[str]:
    """
    Validate Python syntax of code.
    
    Returns:
        None if valid, error message if invalid
    """
    try:
        compile(code, "<string>", "exec")
        return None
    except SyntaxError as e:
        return f"SyntaxError at line {e.lineno}: {e.msg}"
