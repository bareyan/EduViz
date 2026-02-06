
import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.services.pipeline.animation.generation.stages.choreographer import Choreographer, ChoreographyError

@pytest.fixture
def choreographer():
    engine = Mock()
    return Choreographer(engine)

@pytest.mark.asyncio
async def test_choreographer_plan_success(choreographer):
    section = {"title": "Test Section", "narration": "Hello world"}
    choreographer.engine.generate = AsyncMock(return_value={
        "success": True,
        "response": "Detailed Plan"
    })
    
    plan = await choreographer.plan(section, 5.0)
    assert plan == "Detailed Plan"

@pytest.mark.asyncio
async def test_choreographer_plan_failure(choreographer):
    section = {"title": "Test Section"}
    choreographer.engine.generate = AsyncMock(return_value={
        "success": False, 
        "error": "Model Error"
    })
    
    with pytest.raises(ChoreographyError) as exc:
        await choreographer.plan(section, 5.0)
    
    assert "Planning failed: Model Error" in str(exc.value)
