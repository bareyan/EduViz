"""
Adaptive Fixer Strategies

Error type → Fix strategy mapping.

Each strategy provides specialized prompting and context for different error patterns.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class FixStrategy:
    """Represents a fix strategy for specific error patterns."""
    
    name: str
    description: str
    hints: List[str]
    focus_areas: List[str]
    
    def build_guidance(self) -> str:
        """Build strategy-specific guidance for the prompt.
        
        Returns:
            Formatted strategy guidance
        """
        sections = []
        
        if self.hints:
            sections.append("## FIX STRATEGY HINTS\n" + "\n".join(
                f"- {hint}" for hint in self.hints
            ))
        
        if self.focus_areas:
            sections.append("## FOCUS AREAS\n" + "\n".join(
                f"- {area}" for area in self.focus_areas
            ))
        
        return "\n\n".join(sections) if sections else ""


class StrategySelector:
    """Selects appropriate fix strategy based on error patterns."""
    
    # Define available strategies
    STRATEGIES = {
        "syntax_error": FixStrategy(
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
        
        "name_error": FixStrategy(
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
        
        "attribute_error": FixStrategy(
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
        
        "type_error": FixStrategy(
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
        
        "runtime_error": FixStrategy(
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
        
        "manim_api": FixStrategy(
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
        
        "general": FixStrategy(
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
    
    def select(
        self,
        errors: str,
        failure_history: Optional[List[Dict]] = None
    ) -> FixStrategy:
        """Select best strategy based on errors and history.
        
        Args:
            errors: Error messages string
            failure_history: List of recent failures with strategies used
            
        Returns:
            Selected FixStrategy
        """
        # Analyze error patterns
        error_lower = errors.lower()
        
        # Priority matching (most specific first)
        if "syntaxerror" in error_lower or "e999" in errors:
            return self.STRATEGIES["syntax_error"]
        
        if "nameerror" in error_lower or "is not defined" in errors:
            return self.STRATEGIES["name_error"]
        
        if "attributeerror" in error_lower:
            # Check if it's Manim-specific
            if any(term in errors for term in ["VGroup", "get_edge", "flatten"]):
                return self.STRATEGIES["manim_api"]
            return self.STRATEGIES["attribute_error"]
        
        if "typeerror" in error_lower:
            if "argument" in error_lower:
                return self.STRATEGIES["type_error"]
            return self.STRATEGIES["manim_api"]
        
        if "runtime" in error_lower or "exception" in error_lower:
            return self.STRATEGIES["runtime_error"]
        
        # Check for Manim-specific keywords
        if any(term in errors for term in [
            "VGroup", "Mobject", "Scene", "Animation",
            "get_edge", "flatten", "FadeIn", "Transform"
        ]):
            return self.STRATEGIES["manim_api"]
        
        # Default to general strategy
        return self.STRATEGIES["general"]
