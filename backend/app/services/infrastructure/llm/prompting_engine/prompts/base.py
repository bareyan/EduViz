"""
Base prompt template class and utilities.
"""

from dataclasses import dataclass


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
        try:
            # Try standard formatting first
            return self.template.format(**kwargs)
        except (KeyError, ValueError, IndexError):
            # Fallback for prompts with JSON (braces) that conflict with format()
            # If standard format fails, use simple replacement for provided keys
            result = self.template
            for k, v in kwargs.items():
                result = result.replace("{" + k + "}", str(v))
            return result
    
    def __str__(self) -> str:
        return f"PromptTemplate({self.description})"
