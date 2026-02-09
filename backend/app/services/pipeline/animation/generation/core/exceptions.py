"""
Animation Exceptions - Standardized error states for the animation pipeline.
Prevents silent failures and allows for granular retry logic.
"""

from app.core.exceptions import PipelineError

class AnimationError(PipelineError):
    """Base exception for animation pipeline."""
    pass

class ChoreographyError(AnimationError):
    """Raised when the planning stage fails to produce a viable storyboard."""
    pass

class ImplementationError(AnimationError):
    """Raised when the coder fails to produce valid syntax or follow the plan."""
    pass

class RefinementError(AnimationError):
    """Raised when the refinement loop fails to stabilize the code within max attempts."""
    pass

class RenderingError(AnimationError):
    """Raised when the Manim engine fails to produce an output file."""
    pass
