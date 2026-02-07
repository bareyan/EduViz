
import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.services.pipeline.animation.generation.stages.implementer import Implementer, ImplementationError

@pytest.fixture
def implementer():
    engine = Mock()
    return Implementer(engine)

@pytest.mark.asyncio
async def test_implement_success(implementer):
    section = {"title": "Test Section", "narration": "Hello"}
    implementer.engine.generate = AsyncMock(return_value={
        "success": True,
        "response": "```python\nclass TestSection(Scene):\n    pass\n```"
    })
    
    # Mock clean_code
    with patch("app.services.pipeline.animation.generation.stages.implementer.clean_code", return_value="class TestSection(Scene):\n    pass") as mock_clean:
        code = await implementer.implement(section, "Plan", 5.0)
        assert "class TestSection" in code

@pytest.mark.asyncio
async def test_implement_failure(implementer):
    section = {"title": "Test Section"}
    implementer.engine.generate = AsyncMock(return_value={
        "success": False,
        "error": "Gen Error"
    })
    
    with pytest.raises(ImplementationError) as exc:
        await implementer.implement(section, "Plan", 5.0)
    
    assert "Code generation failed: Gen Error" in str(exc.value)


@pytest.mark.asyncio
async def test_implement_accepts_legacy_plan_dict(implementer):
    section = {"title": "Test Section", "language": "en"}
    legacy_plan = {
        "scene_type": "2D",
        "objects": [],
        "segments": [],
    }
    implementer.engine.generate = AsyncMock(return_value={
        "success": True,
        "response": "```python\nclass TestSection(Scene):\n    pass\n```"
    })

    with patch("app.services.pipeline.animation.generation.stages.implementer.clean_code", return_value="class TestSection(Scene):\n    pass"):
        await implementer.implement(section, legacy_plan, 5.0)

    prompt = implementer.engine.generate.call_args.kwargs["prompt"]
    assert '"version": "2.0"' in prompt
