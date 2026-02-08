
import pytest
from unittest.mock import Mock
from app.services.pipeline.animation.generation.refinement.prompting import FixerPromptBuilder

def test_build_initial_prompt():
    builder = FixerPromptBuilder(max_turn_retries=2)
    
    # Mock strategy
    mock_strategy = Mock()
    mock_strategy.build_guidance.return_value = "## STRATEGY HINTS"
    
    prompt = builder.build_initial_prompt(
        code="def foo(): pass",
        errors="SyntaxError",
        strategy=mock_strategy,
        code_scope_note="Truncated"
    )
    
    assert "def foo(): pass" in prompt
    assert "SyntaxError" in prompt
    assert "## STRATEGY HINTS" in prompt
    assert "## CODE SCOPE" in prompt
    assert "Truncated" in prompt
    assert "## GUIDANCE" in prompt

def test_build_followup_prompt():
    builder = FixerPromptBuilder(max_turn_retries=2)
    
    prompt = builder.build_followup_prompt(
        code="current code",
        errors="new error",
        attempt=2
    )
    
    assert "current code" in prompt
    assert "new error" in prompt
