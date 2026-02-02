"""
Integration tests for the Animation Pipeline.
Tests the full flow: Planning -> Code Generation -> Surgical Fixes.
"""

import pytest
import json
from unittest.mock import MagicMock, AsyncMock, patch
from app.services.pipeline.animation.generation.processors import Animator

@pytest.fixture
def mock_engine():
    engine = MagicMock()
    engine.types = MagicMock()
    engine.generate = AsyncMock()
    return engine

@pytest.fixture
def mock_validator():
    validator = MagicMock()
    # default to valid
    validator.validate.return_value = MagicMock(valid=True)
    return validator

@pytest.fixture
def animator(mock_engine, mock_validator):
    return Animator(mock_engine, mock_validator, max_fix_attempts=3)

@pytest.mark.asyncio
async def test_animator_full_flow_with_surgical_fix(animator, mock_engine, mock_validator):
    """
    Simulates a full integration flow where:
    1. Planning succeeds.
    2. Initial code has a syntax error.
    3. Surgical fix is applied and corrects the error.
    4. Validation passes on the second attempt.
    """
    section = {
        "title": "Integration Test Topic",
        "narration": "This is a full flow test of the new animation pipeline.",
        "narration_segments": [
            {"start_time": 0, "duration": 3, "text": "This is a full flow test"},
            {"start_time": 3, "duration": 3, "text": "of the new animation pipeline."}
        ]
    }
    
    # --- Mock LLM Responses ---
    
    # 1. Planning Phase Response
    plan_response = {
        "success": True,
        "response": "CHOREOGRAPHY PLAN:\n1. Show text 'Integration Test'\n2. Pulse animation"
    }
    
    # 2. Initial Implementation Phase Response (Broken Code)
    broken_code = """
class Scene(Scene):
    def construct(self):
        text = Text("Broken"
        self.play(Write(text))
"""
    impl_response = {
        "success": True,
        "response": f"```python{broken_code}```"
    }
    
    # 3. Surgical Fix Phase Response (Tool Call + Hybrid Fallback)
    fixed_code = """
class Scene(Scene):
    def construct(self):
        text = Text("Fixed")
        self.play(Write(text))
"""
    fix_response = {
        "success": True,
        "function_calls": [
            {
                "name": "apply_surgical_edit",
                "args": {
                    "target": 'text = Text("Broken"',
                    "replacement": 'text = Text("Fixed")'
                }
            }
        ],
        "response": "I fixed the missing parenthesis."
    }
    
    mock_engine.generate.side_effect = [plan_response, impl_response, fix_response]
    
    # --- Mock Validator Responses ---
    
    # First validation fails
    invalid_result = MagicMock(valid=False)
    invalid_result.get_error_summary.return_value = "SyntaxError: unexpected EOF while parsing"
    
    # Second validation succeeds
    valid_result = MagicMock(valid=True)
    
    mock_validator.validate.side_effect = [invalid_result, valid_result]
    
    # --- Execute ---
    # We need to patch the editor tool's actual execution to return our "fixed" code string
    # since we're using a string-based mock here for simplicity in integration testing.
    with patch.object(animator.editor, "execute", return_value=fixed_code) as mock_edit_exec:
        final_code = await animator.animate(section, 6.0)
        
        # --- Assertions ---
        
        # 1. Verify all phases were called
        assert mock_engine.generate.call_count == 3
        
        # 2. Verify Planning call args
        plan_call = mock_engine.generate.call_args_list[0]
        assert "Integration Test Topic" in plan_call.kwargs["prompt"]
        
        # 3. Verify Implementation call args
        impl_call = mock_engine.generate.call_args_list[1]
        assert "CHOREOGRAPHY PLAN" in impl_call.kwargs["prompt"]
        
        # 4. Verify Fix call args
        fix_call = mock_engine.generate.call_args_list[2]
        assert "SyntaxError" in fix_call.kwargs["prompt"]
        assert "Broken" in fix_call.kwargs["prompt"]
        
        # 5. Verify Tool was called
        assert mock_edit_exec.called
        
        # 6. Final verification of code content
        assert "Fixed" in final_code
        assert "Broken" not in final_code
        assert "def construct(self):" in final_code

@pytest.mark.asyncio
async def test_animator_failure_max_attempts(animator, mock_engine, mock_validator):
    """Verifies that the animator fails correctly if code cannot be stabilized."""
    section = {"title": "Stub", "narration": "Stub", "narration_segments": []}
    
    # Just keep returning something valid-looking but validator always says NO
    mock_engine.generate.return_value = {"success": True, "response": "```python\npass\n```"}
    
    # Always invalid
    mock_validator.validate.return_value = MagicMock(valid=False)
    mock_validator.validate.return_value.get_error_summary.return_value = "Persistent error"
    
    from app.services.pipeline.animation.generation.core.exceptions import RefinementError
    with pytest.raises(RefinementError) as excinfo:
        await animator.animate(section, 5.0)
    
    assert "Could not stabilize" in str(excinfo.value)
    # 1 (initial) + 3 (max_fix_attempts) = 4 validation checks
    # But wait, our Animator loop: `for attempt in range(1, self.max_fix_attempts + 1):`
    # It checks validation AT THE START of the loop.
    # Total calls: 1 (after initial impl) + 1 (after fix 1) + 1 (after fix 2) + 1 (after fix 3) + 1 (final)
    # Actually, look at logic:
    # 1. validate initial code. fails. apply fix 1.
    # 2. validate fix 1. fails. apply fix 2.
    # 3. validate fix 2. fails. apply fix 3.
    # 4. loop ends. final validation. fails. raise.
    assert mock_validator.validate.call_count == 4
