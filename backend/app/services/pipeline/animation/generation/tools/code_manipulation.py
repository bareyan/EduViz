"""
Code Manipulation Utilities

Extracted from GenerationToolHandler for Single Responsibility.
Handles code extraction, fix application, and response parsing.
"""

import re
from typing import Dict, List, Optional, Tuple


def extract_code_from_response(response: str) -> Optional[str]:
    """
    Extract code from a text response.
    
    Handles:
    - Markdown code blocks (```python ... ```)
    - Raw code with Manim patterns
    
    Args:
        response: Text response that may contain code
        
    Returns:
        Extracted code string, or None if no code found
    """
    if not response:
        return None
    
    # Try to find markdown code block
    pattern = r'```python\n(.*?)\n```'
    match = re.search(pattern, response, re.DOTALL)
    if match:
        return match.group(1)
    
    # Try generic code block
    pattern = r'```\n(.*?)\n```'
    match = re.search(pattern, response, re.DOTALL)
    if match:
        return match.group(1)
    
    # If no markdown, check if response looks like code
    if "self.play" in response or "self.wait" in response:
        return response
    
    return None


def apply_patches(code: str, patches: List[Dict]) -> Tuple[str, int, List[str]]:
    """
    Apply search/replace patches to code with whitespace-insensitive matching.
    
    Each patch is a dict with:
    - search: Text to find
    - replace: Replacement text
    - reason: Why this patch is needed
    
    Args:
        code: Original code
        patches: List of patch dictionaries
        
    Returns:
        Tuple of (new_code, patches_applied_count, details_list)
    """
    new_code = code
    applied = 0
    details = []
    
    for i, patch in enumerate(patches):
        search = patch.get("search", "")
        replace = patch.get("replace", "")
        reason = patch.get("reason", "")
        
        if not search:
            details.append(f"Patch {i+1}: SKIP - empty search text")
            continue
        
        # 1. Try exact match first (preserves exact indentation)
        if search in new_code:
            count = new_code.count(search)
            if count == 1:
                new_code = new_code.replace(search, replace)
                applied += 1
                details.append(f"Patch {i+1}: OK - exact match ({reason})" if reason else f"Patch {i+1}: OK")
                continue
            else:
                details.append(f"Patch {i+1}: FAIL - search text not unique ({count} occurrences)")
                continue

        # 2. Try whitespace-normalized match
        search_norm = ' '.join(search.split())
        
        # We need to find where this normalized search matches in the normalized code
        # and then apply the change to the actual code.
        # This is complex because we want to preserve surrounding indentation if possible.
        
        lines = new_code.split('\n')
        matches = []
        for idx, line in enumerate(lines):
            line_norm = ' '.join(line.split())
            if search_norm in line_norm:
                matches.append(idx)
        
        if len(matches) == 1:
            idx = matches[0]
            # Replace the entire line if it's a sub-string match and we're sure
            # Or better: replace the normalized part.
            # For simplicity in this agentic flow, we'll replace the line that matched.
            lines[idx] = replace
            new_code = '\n'.join(lines)
            applied += 1
            details.append(f"Patch {i+1}: OK - fuzzy match ({reason})" if reason else f"Patch {i+1}: OK")
        elif len(matches) > 1:
            details.append(f"Patch {i+1}: FAIL - fuzzy match not unique ({len(matches)} occurrences)")
        else:
            similar = find_similar_text(search, new_code)
            if similar:
                details.append(f"Patch {i+1}: FAIL - not found. Did you mean: '{similar[:50]}...'?")
            else:
                details.append(f"Patch {i+1}: FAIL - search text not found")
    
    return new_code, applied, details



def find_similar_text(search: str, code: str, min_word_overlap: float = 0.5) -> Optional[str]:
    """
    Find similar text in code when exact match fails.
    
    Uses word-based overlap to find lines that are similar but not identical.
    Helps diagnose fix failures by showing what might have been intended.
    
    Args:
        search: Text to search for
        code: Code to search in
        min_word_overlap: Minimum ratio of overlapping words (0.0 to 1.0)
        
    Returns:
        The most similar line found, or None if no similar text found
    """
    if not search or not code:
        return None
        
    # Normalize whitespace and get words from search
    search_normalized = ' '.join(search.split()).lower()
    search_words = set(search_normalized.split())
    
    if not search_words:
        return None
    
    best_match = None
    best_overlap = 0.0
    
    lines = code.split('\n')
    for line in lines:
        line_normalized = ' '.join(line.split()).lower()
        line_words = set(line_normalized.split())
        
        if not line_words:
            continue
        
        # Calculate word overlap ratio
        common_words = search_words & line_words
        # Use the smaller set as denominator for more lenient matching
        overlap_ratio = len(common_words) / min(len(search_words), len(line_words))
        
        if overlap_ratio > best_overlap:
            best_overlap = overlap_ratio
            best_match = line.strip()
    
    # Return the best match if it meets the minimum overlap threshold
    if best_overlap >= min_word_overlap:
        return best_match
    
    return None


def clean_function_call_args(args: Dict) -> Dict:
    """
    Clean and validate function call arguments from LLM.
    
    Handles common issues:
    - Empty strings
    - Whitespace-only values
    - Missing required fields
    """
    cleaned = {}
    
    for key, value in args.items():
        if isinstance(value, str):
            value = value.strip()
            if value:
                cleaned[key] = value
        elif isinstance(value, list):
            # Clean list items
            cleaned[key] = [
                item.strip() if isinstance(item, str) else item
                for item in value
                if item  # Remove None/empty
            ]
        else:
            cleaned[key] = value
    
    return cleaned
