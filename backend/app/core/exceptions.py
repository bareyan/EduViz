"""
Core Exceptions
Standardized base exceptions for the application.
"""

class EduVizError(Exception):
    """Base exception for all application errors."""
    pass

class PipelineError(EduVizError):
    """Base exception for processing pipeline errors."""
    pass

class InfrastructureError(EduVizError):
    """Base exception for infrastructure errors (LLM, Storage, etc)."""
    pass
