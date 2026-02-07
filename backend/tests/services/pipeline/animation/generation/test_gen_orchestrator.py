
import pytest
from unittest.mock import AsyncMock, Mock, patch

from app.services.pipeline.animation.generation.orchestrator import AnimationOrchestrator
from app.services.pipeline.animation.generation.core import ChoreographyError, ImplementationError
from app.utils.section_status import SectionState
from app.services.infrastructure.llm import PromptingEngine

@pytest.fixture
def mock_engine():
    engine = Mock(spec=PromptingEngine)
    engine.cost_tracker = Mock()
    return engine

@pytest.fixture
def mock_stages():
    with patch("app.services.pipeline.animation.generation.orchestrator.Choreographer") as MockChoreographer, \
         patch("app.services.pipeline.animation.generation.orchestrator.Implementer") as MockImplementer, \
         patch("app.services.pipeline.animation.generation.orchestrator.Refiner") as MockRefiner, \
         patch("app.services.pipeline.animation.generation.orchestrator.AdaptiveFixerAgent") as MockFixer:
        
        choreographer = MockChoreographer.return_value
        implementer = MockImplementer.return_value
        refiner = MockRefiner.return_value
        fixer = MockFixer.return_value
        
        yield {
            "choreographer": choreographer,
            "implementer": implementer,
            "refiner": refiner,
            "fixer": fixer
        }

@pytest.fixture
def orchestrator(mock_engine, mock_stages):
    return AnimationOrchestrator(mock_engine)

@pytest.mark.asyncio
async def test_generate_success(orchestrator, mock_stages):
    # Setup mocks
    mock_stages["choreographer"].plan = AsyncMock(return_value={"version": "2.0"})
    mock_stages["implementer"].implement = AsyncMock(return_value="code")
    mock_stages["refiner"].refine = AsyncMock(return_value=("final_code", True))
    
    section = {"title": "Test Section"}
    result = await orchestrator.generate(section, 60.0)
    
    # Assertions
    assert result == "final_code"
    mock_stages["choreographer"].plan.assert_called_once()
    mock_stages["implementer"].implement.assert_called_once()
    mock_stages["refiner"].refine.assert_called_once()


@pytest.mark.asyncio
async def test_generate_persists_choreography_callback(orchestrator, mock_stages):
    mock_stages["choreographer"].plan = AsyncMock(return_value={"version": "2.0"})
    mock_stages["implementer"].implement = AsyncMock(return_value="code")
    mock_stages["refiner"].refine = AsyncMock(return_value=("final_code", True))
    on_choreography = Mock()

    section = {"title": "Test Section"}
    result = await orchestrator.generate(section, 60.0, on_choreography=on_choreography)

    assert result == "final_code"
    on_choreography.assert_called_once_with({"version": "2.0"}, 0)

@pytest.mark.asyncio
async def test_generate_retry_logic(orchestrator, mock_stages):
    # Choreography fails on first attempt, succeeds on second
    mock_stages["choreographer"].plan = AsyncMock(side_effect=[ChoreographyError("Fail"), {"version": "2.0"}])
    mock_stages["implementer"].implement = AsyncMock(return_value="code")
    mock_stages["refiner"].refine = AsyncMock(return_value=("final_code", True))
    
    with patch("asyncio.sleep", AsyncMock()) as mock_sleep:
        section = {"title": "Test Section"}
        result = await orchestrator.generate(section, 60.0)
        
        assert result == "final_code"
        assert mock_stages["choreographer"].plan.call_count == 2
        mock_sleep.assert_called_once()

@pytest.mark.asyncio
async def test_generate_all_retries_fail(orchestrator, mock_stages):
    # Always fail
    mock_stages["choreographer"].plan = AsyncMock(side_effect=ChoreographyError("Fail"))
    
    with patch("asyncio.sleep", AsyncMock()):
        section = {"title": "Test Section"}
        result = await orchestrator.generate(section, 60.0)
        
        assert result == ""
        # Should be called MAX_CLEAN_RETRIES times (2 by default)
        assert mock_stages["choreographer"].plan.call_count >= 2

@pytest.mark.asyncio
async def test_refinement_failure(orchestrator, mock_stages):
    mock_stages["choreographer"].plan = AsyncMock(return_value={"version": "2.0"})
    mock_stages["implementer"].implement = AsyncMock(return_value="code")
    # Refinement fails to stabilize -> Raises ImplementationError -> triggers retry
    mock_stages["refiner"].refine = AsyncMock(return_value=("code", False)) 
    
    with patch("asyncio.sleep", AsyncMock()):
        section = {"title": "Test Section"}
        result = await orchestrator.generate(section, 60.0)
        
        assert result == ""
        # Should retry until exhausted
        assert mock_stages["refiner"].refine.call_count >= 2

def test_build_retry_context(orchestrator):
    base_context = {"key": "value"}
    ctx = orchestrator._build_retry_context(base_context, 1, ValueError("Oops"))
    
    assert ctx["key"] == "value"
    assert ctx["retry_attempt"] == 2
    assert "retry_temperature" in ctx
    assert ctx["previous_failure"] == "Oops"

def test_compute_retry_temperature(orchestrator):
    temp0 = orchestrator._compute_retry_temperature(0)
    temp1 = orchestrator._compute_retry_temperature(1)
    assert temp1 > temp0
