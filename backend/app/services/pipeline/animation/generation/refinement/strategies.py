"""
Adaptive Fixer Strategies

Error type → Fix strategy mapping.

Each strategy provides specialized prompting and context for different error patterns.
"""

from typing import Dict, List, Optional
from dataclasses import dataclass

from ...prompts.strategy_data import STRATEGY_CONFIGS, FixStrategyConfig


@dataclass
class FixStrategy:
    """Represents a fix strategy for specific error patterns."""
    
    name: str
    description: str
    hints: List[str]
    focus_areas: List[str]
    
    @classmethod
    def from_config(cls, config: FixStrategyConfig) -> "FixStrategy":
        return cls(
            name=config.name,
            description=config.description,
            hints=config.hints,
            focus_areas=config.focus_areas
        )
    
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
    
    def __init__(self):
        # Initialize strategies from config
        self.strategies = {
            key: FixStrategy.from_config(cfg)
            for key, cfg in STRATEGY_CONFIGS.items()
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
            return self.strategies["syntax_error"]
        
        if "nameerror" in error_lower or "is not defined" in errors:
            return self.strategies["name_error"]
        
        if "attributeerror" in error_lower:
            # Check if it's Manim-specific
            if any(term in errors for term in ["VGroup", "get_edge", "flatten"]):
                return self.strategies["manim_api"]
            return self.strategies["attribute_error"]
        
        if "typeerror" in error_lower:
            if "argument" in error_lower:
                return self.strategies["type_error"]
            return self.strategies["manim_api"]
        
        if "runtime" in error_lower or "exception" in error_lower:
            return self.strategies["runtime_error"]
        
        # Check for Manim-specific keywords
        if any(term in errors for term in [
            "VGroup", "Mobject", "Scene", "Animation",
            "get_edge", "flatten", "FadeIn", "Transform"
        ]):
            return self.strategies["manim_api"]
        
        # Default to general strategy
        return self.strategies["general"]
