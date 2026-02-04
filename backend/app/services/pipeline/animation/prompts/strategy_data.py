"""
Strategy Data Configuration

Contains the definitions for validation and fix strategies.
Separates data from logic for better maintainability.
"""

from dataclasses import dataclass
from typing import List, Dict

@dataclass
class FixStrategyConfig:
    """Configuration for a fix strategy."""
    name: str
    description: str
    hints: List[str]
    focus_areas: List[str]


STRATEGY_CONFIGS: Dict[str, FixStrategyConfig] = {
    "syntax_error": FixStrategyConfig(
        name="syntax_error",
        description="Fix Python syntax errors",
        hints=[
            "Check colons, parentheses, and brackets for proper pairing",
            "Verify indentation is consistent (4 spaces)",
            "Look for missing or extra commas in lists/dicts",
            "Ensure strings are properly quoted"
        ],
        focus_areas=["Line-level syntax", "Indentation", "Punctuation"]
    ),
    
    "name_error": FixStrategyConfig(
        name="name_error",
        description="Fix undefined names and missing imports",
        hints=[
            "Add missing import statements at file top",
            "Check for typos in variable/class names",
            "Ensure variables are defined before use",
            "Verify Manim class names are correct (case-sensitive)"
        ],
        focus_areas=["Imports section", "Variable definitions", "Class names"]
    ),
    
    "attribute_error": FixStrategyConfig(
        name="attribute_error",
        description="Fix incorrect method/attribute access",
        hints=[
            "Verify Manim v0.19.2 API method names",
            "Check object types before calling methods",
            "Use get_edge_center() instead of get_edge()",
            "Ensure mobjects are created before accessing attributes"
        ],
        focus_areas=["Method calls", "Manim API usage", "Object lifecycle"]
    ),
    
    "type_error": FixStrategyConfig(
        name="type_error",
        description="Fix type mismatches and argument errors",
        hints=[
            "Verify argument names and order for Manim methods",
            "Check for correct argument types (int, float, str, etc.)",
            "Remove unsupported parameters (e.g., 'scale' in FadeIn)",
            "Ensure animations receive mobjects, not other animations"
        ],
        focus_areas=["Function arguments", "Type conversions", "Manim signatures"]
    ),
    
    "runtime_error": FixStrategyConfig(
        name="runtime_error",
        description="Fix runtime execution errors",
        hints=[
            "Check for division by zero",
            "Verify array indices are in bounds",
            "Ensure mathematical operations are valid",
            "Check for None values before use"
        ],
        focus_areas=["Mathematical operations", "Array access", "Null checks"]
    ),
    
    "manim_api": FixStrategyConfig(
        name="manim_api",
        description="Fix Manim-specific API issues",
        hints=[
            "Flatten VGroup manually: [*group1, *group2]",
            "Use VGroup(*items) not VGroup(items)",
            "Call get_edge_center() for edge positions",
            "Animations use .animate or pass mobjects directly"
        ],
        focus_areas=["VGroup usage", "Edge methods", "Animation syntax"]
    ),
    
    "general": FixStrategyConfig(
        name="general",
        description="General error fixing approach",
        hints=[
            "Read error message carefully for line numbers",
            "Make minimal, targeted changes",
            "Test logic around error line",
            "Check recent changes if in iteration"
        ],
        focus_areas=["Error line context", "Minimal edits", "Logic verification"]
    )
}
