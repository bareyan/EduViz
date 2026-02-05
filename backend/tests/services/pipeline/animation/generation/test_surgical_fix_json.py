import pytest

from app.services.pipeline.animation.generation import processors


class DummyEditor:
    def __init__(self):
        self.calls = []

    def execute(self, code: str, search_text: str, replacement_text: str) -> str:
        self.calls.append((search_text, replacement_text))
        return code.replace(search_text, replacement_text)


class DummyEngine:
    def __init__(self, parsed_json):
        self.parsed_json = parsed_json
        self.last_kwargs = None

    async def generate(self, **kwargs):
        self.last_kwargs = kwargs
        return {"success": True, "parsed_json": self.parsed_json}


@pytest.mark.anyio
async def test_surgical_fix_applies_json_edits():
    animator = processors.Animator.__new__(processors.Animator)
    animator.editor = DummyEditor()
    animator.engine = DummyEngine(
        {
            "edits": [
                {"search_text": "Broken", "replacement_text": "Fixed"}
            ]
        }
    )

    updated = await animator._apply_surgical_fix(
        code="Broken Code",
        errors="TypeError",
        validation=None,
        attempt=1,
    )

    assert "Fixed" in updated
    assert animator.editor.calls


@pytest.mark.anyio
async def test_surgical_fix_falls_back_to_full_code():
    animator = processors.Animator.__new__(processors.Animator)
    animator.editor = DummyEditor()
    animator.engine = DummyEngine(
        {
            "edits": [],
            "full_code": "```python\n# Full replacement\n```"
        }
    )

    updated = await animator._apply_surgical_fix(
        code="Original Code",
        errors="TypeError",
        validation=None,
        attempt=1,
    )

    assert "# Full replacement" in updated
