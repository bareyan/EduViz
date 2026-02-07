import pytest
from types import SimpleNamespace
from unittest.mock import Mock, AsyncMock

from app.services.pipeline.animation.generation.stages.choreographer import (
    Choreographer,
    ChoreographyError,
)


@pytest.fixture
def choreographer():
    engine = Mock()
    return Choreographer(engine)


def _minimal_v2_plan() -> dict:
    return {
        "version": "2.0",
        "scene": {
            "mode": "2D",
            "camera": None,
            "safe_bounds": {
                "x_min": -5.5,
                "x_max": 5.5,
                "y_min": -3.0,
                "y_max": 3.0,
            },
        },
        "objects": [],
        "timeline": [],
        "constraints": {
            "language": "English",
            "max_visible_objects": 10,
            "forbidden_constants": ["TOP", "BOTTOM"],
        },
        "notes": [],
    }


@pytest.mark.asyncio
async def test_choreographer_plan_success(choreographer):
    section = {"title": "Test Section", "narration": "Hello world"}
    choreographer.engine.generate = AsyncMock(
        return_value={
            "success": True,
            "parsed_json": _minimal_v2_plan(),
        }
    )

    plan = await choreographer.plan(section, 5.0)
    assert plan["version"] == "2.0"
    assert plan["scene"]["mode"] == "2D"

    called_config = choreographer.engine.generate.call_args.kwargs["config"]
    assert called_config.response_format == "json"
    assert called_config.require_json_valid is True


@pytest.mark.asyncio
async def test_choreographer_schema_fallback(choreographer):
    section = {"title": "Test Section", "narration": "Hello world"}
    choreographer.engine.generate = AsyncMock(
        side_effect=[
            {
                "success": False,
                "error": "INVALID_ARGUMENT: response_schema not supported",
            },
            {
                "success": True,
                "parsed_json": _minimal_v2_plan(),
            },
        ]
    )

    plan = await choreographer.plan(section, 5.0)
    assert plan["version"] == "2.0"
    assert choreographer.engine.generate.call_count == 2


@pytest.mark.asyncio
async def test_choreographer_schema_fallback_on_pydantic_schema_error(choreographer):
    section = {"title": "Test Section", "narration": "Hello world"}
    choreographer.engine.generate = AsyncMock(
        side_effect=[
            {
                "success": False,
                "error": "7 validation errors for Schema",
            },
            {
                "success": True,
                "parsed_json": _minimal_v2_plan(),
            },
        ]
    )

    plan = await choreographer.plan(section, 5.0)
    assert plan["version"] == "2.0"
    assert choreographer.engine.generate.call_count == 2


@pytest.mark.asyncio
async def test_choreographer_skips_schema_for_preview_models(choreographer):
    section = {"title": "Test Section", "narration": "Hello world"}
    choreographer.engine._get_config = Mock(
        return_value=SimpleNamespace(model_name="gemini-3-flash-preview")
    )
    choreographer.engine.generate = AsyncMock(
        return_value={
            "success": True,
            "parsed_json": _minimal_v2_plan(),
        }
    )

    plan = await choreographer.plan(section, 5.0)
    assert plan["version"] == "2.0"

    called_config = choreographer.engine.generate.call_args.kwargs["config"]
    assert called_config.response_schema is None


@pytest.mark.asyncio
async def test_choreographer_disables_schema_after_incompatibility(choreographer):
    section = {"title": "Test Section", "narration": "Hello world"}
    choreographer.engine._get_config = Mock(
        return_value=SimpleNamespace(model_name="gemini-2.5-flash")
    )
    choreographer.engine.generate = AsyncMock(
        side_effect=[
            {
                "success": False,
                "error": "400 INVALID_ARGUMENT: Unknown name \"additional_properties\" at generation_config.response_schema",
            },
            {
                "success": True,
                "parsed_json": _minimal_v2_plan(),
            },
            {
                "success": True,
                "parsed_json": _minimal_v2_plan(),
            },
        ]
    )

    first_plan = await choreographer.plan(section, 5.0)
    second_plan = await choreographer.plan(section, 5.0)

    assert first_plan["version"] == "2.0"
    assert second_plan["version"] == "2.0"
    assert choreographer.engine.generate.call_count == 3

    first_config = choreographer.engine.generate.call_args_list[0].kwargs["config"]
    fallback_config = choreographer.engine.generate.call_args_list[1].kwargs["config"]
    second_config = choreographer.engine.generate.call_args_list[2].kwargs["config"]
    assert first_config.response_schema is not None
    assert fallback_config.response_schema is None
    assert second_config.response_schema is None


@pytest.mark.asyncio
async def test_choreographer_plan_failure(choreographer):
    section = {"title": "Test Section"}
    choreographer.engine.generate = AsyncMock(
        return_value={
            "success": False,
            "error": "Model Error",
        }
    )

    with pytest.raises(ChoreographyError) as exc:
        await choreographer.plan(section, 5.0)

    assert "Planning failed: Model Error" in str(exc.value)
