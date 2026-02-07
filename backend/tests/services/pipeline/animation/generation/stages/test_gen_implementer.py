
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
async def test_implement_overview_uses_faster_llm_config(implementer):
    section = {"title": "Test Section", "video_mode": "overview"}
    implementer.engine.generate = AsyncMock(
        return_value={"success": True, "response": "```python\nclass A(Scene):\n    pass\n```"}
    )

    with patch(
        "app.services.pipeline.animation.generation.stages.implementer.clean_code",
        return_value="class A(Scene):\n    pass",
    ):
        await implementer.implement(section, "Plan", 5.0)

    config = implementer.engine.generate.await_args.kwargs["config"]
    assert config.enable_thinking is False
    assert config.timeout <= 180.0
