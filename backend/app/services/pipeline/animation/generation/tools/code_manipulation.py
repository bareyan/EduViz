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


def apply_fixes(code: str, fixes: List[Dict]) -> Tuple[str, int, List[str]]:
    """
    Apply search/replace fixes to code.
    
    Each fix is a dict with:
    - search: Exact text to find (must be unique)
    - replace: Replacement text
    - reason: Why this fix is needed
    
    Args:
        code: Original code
        fixes: List of fix dictionaries
        
    Returns:
        Tuple of (new_code, fixes_applied_count, details_list)
    """
    new_code = code
    applied = 0
    details = []
    
    for i, fix in enumerate(fixes):
        search = fix.get("search", "")
        replace = fix.get("replace", "")
        reason = fix.get("reason", "")
        
        if not search:
            details.append(f"Fix {i+1}: SKIP - empty search text")
            continue
        
        if search in new_code:
            # Check uniqueness
            count = new_code.count(search)
            if count == 1:
                new_code = new_code.replace(search, replace)
                applied += 1
                details.append(f"Fix {i+1}: OK - {reason}" if reason else f"Fix {i+1}: OK")
            else:
                details.append(f"Fix {i+1}: SKIP - search text appears {count} times (must be unique)")
        else:
            # Try to find similar matches for better error messages
            similar = find_similar_text(search, new_code)
            if similar:
                details.append(f"Fix {i+1}: FAIL - search text not found. Similar: '{similar[:50]}...'")
            else:
                details.append(f"Fix {i+1}: FAIL - search text not found in code")
    
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
