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



def find_similar_text(search: str, code: str) -> Optional[str]:
    """
    Find similar text in code when exact match fails.
    
    Helps diagnose fix failures by showing what might have been intended.
    """
    # Normalize whitespace for comparison
    search_normalized = ' '.join(search.split())
    
    lines = code.split('\n')
    for line in lines:
        line_normalized = ' '.join(line.split())
        if search_normalized[:30].lower() in line_normalized.lower():
            return line.strip()
    
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
