import pytest

from app.services.pipeline.script_generation.base import BaseScriptGenerator


class _StubPart:
    @staticmethod
    def from_text(text):
        return {"type": "text", "text": text}


class _StubContent:
    def __init__(self, role, parts):
        self.role = role
        self.parts = parts


class _StubTypes:
    Part = _StubPart
    Content = _StubContent


@pytest.fixture
def base_generator():
    base = BaseScriptGenerator()
    base.engine.types = _StubTypes
    return base


def test_build_prompt_contents_returns_content_list(base_generator):
    attachment = {"type": "pdf", "data": b"x"}
    contents = base_generator.build_prompt_contents("hello", attachment)
    assert isinstance(contents, list)
    assert len(contents) == 1
    assert hasattr(contents[0], "parts")
    assert contents[0].parts[0]["type"] == "text"
    assert contents[0].parts[1]["type"] == "pdf"


def test_build_prompt_contents_fallback_when_no_attachment(base_generator):
    contents = base_generator.build_prompt_contents("hello", None)
    assert contents is None


@pytest.mark.asyncio
async def test_generate_with_engine_returns_response_on_failure(base_generator, monkeypatch):
    async def _fake_generate(*args, **kwargs):
        return {
            "success": False,
            "error": "JSON parse failed",
            "error_reason": "json_parse_failed",
            "response": '{"title":"Test","sections":[]}',
        }

    monkeypatch.setattr(base_generator.engine, "generate", _fake_generate)
    response = await base_generator.generate_with_engine("prompt")
    assert response == '{"title":"Test","sections":[]}'
