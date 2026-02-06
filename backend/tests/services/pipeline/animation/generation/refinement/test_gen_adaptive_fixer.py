
import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.services.pipeline.animation.generation.refinement.adaptive_fixer import AdaptiveFixerAgent

@pytest.fixture
def adaptive_fixer():
    mock_engine = Mock()
    mock_engine.types.Content = Mock()
    mock_engine.types.Part = Mock()
    return AdaptiveFixerAgent(mock_engine)

@pytest.mark.asyncio
async def test_run_turn_success(adaptive_fixer):
    code = "broken"
    errors = "error"
    
    # Mock mocks
    adaptive_fixer.strategy_selector.select = Mock(return_value=Mock(name="strat"))
    adaptive_fixer.context_manager.select_context = Mock(return_value=("ctx", "note"))
    adaptive_fixer.prompt_builder.build_initial_prompt = Mock(return_value="prompt")
    
    # Mock LLM success
    adaptive_fixer.engine.generate = AsyncMock(return_value={
        "success": True,
        "parsed_json": {
            "edits": [{"search_text": "broken", "replacement_text": "fixed"}]
        }
    })
    
    new_code, meta = await adaptive_fixer.run_turn(code, errors)
    
    assert new_code == "fixed"
    assert meta["status"] == "applied"
    assert meta["edits"] == 1

@pytest.mark.asyncio
async def test_run_turn_llm_failure_retry(adaptive_fixer):
    # First attempt fails (no success), second succeeds
    adaptive_fixer.prompt_builder.build_initial_prompt = Mock(return_value="p1")
    adaptive_fixer.prompt_builder.build_followup_prompt = Mock(return_value="p2")

    adaptive_fixer.engine.generate = AsyncMock(side_effect=[
        {"success": False, "error": "oops"},
        {
            "success": True, 
            "parsed_json": {"edits": [{"search_text": "code", "replacement_text": "fixed"}]}
        }
    ])
    
    code = "code"
    # We need apply_edits to work
    new_code, meta = await adaptive_fixer.run_turn(code, "err")
    
    assert new_code == "fixed"
    assert meta["attempts"] == 2

@pytest.mark.asyncio
async def test_run_turn_exhausted(adaptive_fixer):
    adaptive_fixer.engine.generate = AsyncMock(return_value={"success": False, "error": "nope"})
    
    new_code, meta = await adaptive_fixer.run_turn("code", "err")
    
    assert new_code == "code" # Unchanged
    assert meta["status"] == "failed"
    assert adaptive_fixer._consecutive_failures == 1
