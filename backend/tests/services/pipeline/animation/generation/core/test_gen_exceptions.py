
from app.services.pipeline.animation.generation.core.exceptions import (
    AnimationError,
    ChoreographyError,
    ImplementationError,
    RefinementError,
    RenderingError
)

def test_exceptions_inheritance():
    # Verify inheritance hierarchy
    assert issubclass(ChoreographyError, AnimationError)
    assert issubclass(ImplementationError, AnimationError)
    assert issubclass(RefinementError, AnimationError)
    assert issubclass(RenderingError, AnimationError)
    
    try:
        raise ChoreographyError("test")
    except AnimationError:
        pass
    except:
        assert False, "Should have caught as AnimationError"
