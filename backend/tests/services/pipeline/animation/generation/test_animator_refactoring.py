import pytest
from unittest.mock import AsyncMock, MagicMock
from app.services.pipeline.animation.generation.animator import Animator
from app.services.pipeline.animation.generation.validation.orchestrator import CodeValidator, CodeValidationResult
from app.services.pipeline.animation.generation.core.exceptions import RefinementError

@pytest.fixture
def mock_engine():
    engine = MagicMock()
    engine.generate = AsyncMock()
    engine.cost_tracker = MagicMock()
    return engine

@pytest.fixture
def mock_validator():
    validator = MagicMock(spec=CodeValidator)
    return validator

@pytest.mark.asyncio
async def test_animator_failure_tracking(mock_engine, mock_validator):
    # Setup animator
    animator = Animator(mock_engine, mock_validator)
    
    # Mock validation results
    v_invalid = MagicMock(spec=CodeValidationResult)
    v_invalid.valid = False
    v_invalid.get_error_summary.return_value = "overlapping objects"
    v_invalid.spatial = MagicMock()
    v_invalid.spatial.frame_captures = []
    v_invalid.spatial.cleanup_screenshots = MagicMock()
    
    mock_validator.validate.return_value = v_invalid
    
    # Mock engine failure
    mock_engine.generate.return_value = {"success": False, "error": "LLM crashed"}
    
    # Run refinement turn once (should log and return original code)
    code = "from manim import *"
    result_code = await animator._execute_refinement_turn(code, "overlapping", v_invalid)
    assert result_code == code
    assert animator._consecutive_agent_failures == 1
    
    # Run second time (should raise RefinementError)
    with pytest.raises(RefinementError) as exc:
        await animator._execute_refinement_turn(code, "overlapping", v_invalid)
    assert "consecutive turns" in str(exc.value)

@pytest.mark.asyncio
async def test_animator_reset_failures_on_success(mock_engine, mock_validator):
    animator = Animator(mock_engine, mock_validator)
    animator._consecutive_agent_failures = 1
    
    v_invalid = MagicMock(spec=CodeValidationResult)
    v_invalid.valid = False
    v_invalid.get_error_summary.return_value = "overlapping"
    v_invalid.spatial = MagicMock()
    v_invalid.spatial.frame_captures = []
    v_invalid.spatial.cleanup_screenshots = MagicMock()
    
    # Mock success with structured output
    mock_engine.generate.return_value = {
        "success": True, 
        "parsed_json": {"analysis": "Fixing overlap", "edits": []}
    }
    
    await animator._execute_refinement_turn("code", "err", v_invalid)
    assert animator._consecutive_agent_failures == 0

@pytest.mark.asyncio
async def test_animator_applies_edits(mock_engine, mock_validator):
    """Verify structured edits are applied correctly."""
    animator = Animator(mock_engine, mock_validator)
    
    v_invalid = MagicMock(spec=CodeValidationResult)
    v_invalid.valid = False
    v_invalid.spatial = MagicMock()
    v_invalid.spatial.frame_captures = []
    v_invalid.spatial.cleanup_screenshots = MagicMock()
    
    # Mock structured response
    mock_engine.generate.return_value = {
        "success": True,
        "parsed_json": {
            "analysis": "Fixing color",
            "edits": [
                {
                    "search_text": "color=RED",
                    "replacement_text": "color=BLUE"
                }
            ]
        }
    }
    
    original_code = "c = Circle(color=RED)"
    expected_code = "c = Circle(color=BLUE)"
    
    result = await animator._execute_refinement_turn(original_code, "err", v_invalid)
    assert result == expected_code
