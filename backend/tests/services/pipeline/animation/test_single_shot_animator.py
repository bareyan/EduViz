"""
Tests for app.services.pipeline.animation.generation.processors.Animator
Testing the new single-shot + surgical fix architecture.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from app.services.pipeline.animation.generation.processors import Animator
from app.services.pipeline.animation.generation.core.exceptions import (
    ChoreographyError,
    ImplementationError,
    RefinementError
)

@pytest.fixture
def mock_engine():
    engine = MagicMock()
    engine.types = MagicMock()
    engine.generate = AsyncMock()
    return engine

@pytest.fixture
def mock_validator():
    validator = MagicMock()
    validator.validate = MagicMock()
    return validator

@pytest.fixture
def animator(mock_engine, mock_validator):
    anim = Animator(mock_engine, mock_validator, max_fix_attempts=2)
    anim.choreography_engine = mock_engine
    return anim

@pytest.mark.asyncio
async def test_animate_success_first_try(animator, mock_engine, mock_validator):
    """Test successful animation logic when first try is valid."""
    section = {
        "title": "Test Section",
        "narration": "Hello world",
        "narration_segments": [{"start_time": 0, "duration": 5, "text": "Hello"}]
    }
    
    # Mock planning phase
    mock_engine.generate.side_effect = [
        {"success": True, "response": "Visual Plan"}, # Phase 1
        {"success": True, "response": "```python\n# Manim code\n```"} # Phase 2
    ]
    
    # Mock validation success
    mock_validator.validate.return_value.valid = True
    mock_validator.validate.return_value.static = MagicMock(valid=True)
    mock_validator.validate.return_value.spatial = MagicMock(errors=[], warnings=[])
    
    code = await animator.animate(section, 5.0)
    
    assert "# Manim code" in code
    assert mock_engine.generate.call_count == 2
    assert mock_validator.validate.call_count == 1

@pytest.mark.asyncio
async def test_animate_surgical_fix_success(animator, mock_engine, mock_validator):
    """Test successful surgical fix after initial validation failure."""
    section = {"title": "Test", "narration": "...", "narration_segments": []}
    
    # 1. Plan, 2. Broken Code, 3. Surgical Fix
    mock_engine.generate.side_effect = [
        {"success": True, "response": "Plan"},
        {"success": True, "response": "Broken Code"},
        {
            "success": True, 
            "function_calls": [{"name": "apply_surgical_edit", "args": {"target": "B", "replacement": "F"}}],
            "response": "Fix info"
        }
    ]
    
    # 1. Invalid, 2. Valid
    val_invalid = MagicMock(valid=False)
    val_invalid.static = MagicMock(valid=True)
    val_invalid.spatial = MagicMock(errors=["err"], warnings=[])
    val_invalid.get_error_summary.return_value = "Syntax error at line 1"
    
    val_valid = MagicMock(valid=True)
    val_valid.static = MagicMock(valid=True)
    val_valid.spatial = MagicMock(errors=[], warnings=[])
    
    mock_validator.validate.side_effect = [val_invalid, val_valid]
    
    # Mock editor tool
    with patch.object(animator.editor, "execute", return_value="Fixed Code") as mock_exec:
        code = await animator.animate(section, 5.0)
        
        assert code == "Fixed Code"
        assert mock_exec.called
        assert mock_engine.generate.call_count == 3

@pytest.mark.asyncio
async def test_animate_planning_failure(animator, mock_engine):
    """Test failure during choreography phase."""
    # First attempt fails planning, second attempt succeeds
    mock_engine.generate.side_effect = [
        {"success": False, "error": "LLM Down"},  # plan fails
        {"success": True, "response": "Recovered plan"},  # plan retry
        {"success": True, "response": "```python\n# code\n```"}
    ]
    code = await animator.animate({"title": "Test"}, 5.0)
    assert isinstance(code, str)

@pytest.mark.asyncio
async def test_animate_refinement_failure(animator, mock_engine, mock_validator):
    """Test failure after max surgical fix attempts."""
    section = {"title": "Test", "narration": "...", "narration_segments": []}
    
    mock_engine.generate.return_value = {"success": True, "response": "Some response"}
    
    # Always invalid
    val_invalid = MagicMock(valid=False)
    val_invalid.static = MagicMock(valid=True)
    val_invalid.spatial = MagicMock(errors=["err"], warnings=[])
    val_invalid.get_error_summary.return_value = "Never fixed"
    mock_validator.validate.return_value = val_invalid
    
    code = await animator.animate(section, 5.0)
    assert isinstance(code, str)
    assert mock_validator.validate.call_count >= 1
