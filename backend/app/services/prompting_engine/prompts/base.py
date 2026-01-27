"""
Base prompt template class and utilities.
"""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class PromptTemplate:
    """
    A prompt template with placeholders.
    
    Usage:
        template = PromptTemplate(
            template="Hello {name}!",
            description="A greeting"
        )
        result = template.format(name="World")
    """
    template: str
    description: str = ""
    
    def format(self, **kwargs) -> str:
        """Format the template with provided values"""
        return self.template.format(**kwargs)
    
    def __str__(self) -> str:
        return f"PromptTemplate({self.description})"
