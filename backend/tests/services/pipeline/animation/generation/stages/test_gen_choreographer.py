
import pytest
from unittest.mock import Mock, AsyncMock
from app.services.pipeline.animation.config import (
    CHOREOGRAPHY_MAX_OUTPUT_TOKENS,
    OVERVIEW_CHOREOGRAPHY_MAX_OUTPUT_TOKENS,
)
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


@pytest.mark.asyncio
async def test_choreographer_plan_includes_practical_visual_strategy(choreographer):
    section = {
        "title": "Applied Regression",
        "narration": "Let's solve a concrete regression task.",
        "content_focus": "practice",
        "video_mode": "comprehensive",
        "document_context": "standalone",
    }
    choreographer.engine.generate = AsyncMock(return_value={
        "success": True,
        "response": "Detailed Plan"
    })

    await choreographer.plan(section, 30.0)

    prompt = choreographer.engine.generate.await_args.kwargs["prompt"]
    assert "PRACTICAL VISUAL PRIORITY" in prompt
    assert "graphs, tables, timelines" in prompt
    assert "Do not rely on Text/MathTex-only plans" in prompt
    assert "visual_change" in prompt
    assert "narration_cue" in prompt
    assert "layout_zone" in prompt
    assert "Co-visible objects should occupy distinct zones" in prompt
    assert "text-text >= 0.4" in prompt


@pytest.mark.asyncio
async def test_choreographer_plan_requires_reference_recreation(choreographer):
    section = {
        "title": "Cited Architecture",
        "narration": "As shown in Figure 3, the stack widens.",
        "section_data": {
            "supporting_data": [
                {
                    "type": "referenced_content",
                    "label": "Figure 3",
                    "value": {"binding_key": "figure:3", "recreate_in_video": True},
                }
            ]
        },
    }
    choreographer.engine.generate = AsyncMock(return_value={"success": True, "response": "Plan"})

    await choreographer.plan(section, 20.0)

    prompt = choreographer.engine.generate.await_args.kwargs["prompt"]
    assert "REFERENCE RECREATION" in prompt
    assert "data_binding" in prompt


@pytest.mark.asyncio
async def test_choreographer_overview_uses_faster_llm_config(choreographer):
    section = {"title": "Overview", "video_mode": "overview"}
    choreographer.engine.generate = AsyncMock(return_value={"success": True, "response": "Plan"})

    await choreographer.plan(section, 10.0)

    config = choreographer.engine.generate.await_args.kwargs["config"]
    assert config.enable_thinking is False
    assert config.timeout <= 180.0


@pytest.mark.asyncio
async def test_choreographer_scales_tokens_for_long_comprehensive_sections(choreographer):
    section = {"title": "Long Comprehensive", "video_mode": "comprehensive"}
    choreographer.engine.generate = AsyncMock(return_value={"success": True, "response": "Plan"})

    await choreographer.plan(section, 180.0)

    config = choreographer.engine.generate.await_args.kwargs["config"]
    assert config.max_output_tokens > CHOREOGRAPHY_MAX_OUTPUT_TOKENS


@pytest.mark.asyncio
async def test_choreographer_scales_tokens_for_long_overview_sections(choreographer):
    section = {"title": "Long Overview", "video_mode": "overview"}
    choreographer.engine.generate = AsyncMock(return_value={"success": True, "response": "Plan"})

    await choreographer.plan(section, 180.0)

    config = choreographer.engine.generate.await_args.kwargs["config"]
    assert config.max_output_tokens > OVERVIEW_CHOREOGRAPHY_MAX_OUTPUT_TOKENS
