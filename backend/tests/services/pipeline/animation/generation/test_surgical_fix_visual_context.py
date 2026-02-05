"""
Tests for surgical fix multimodal contents.
"""

import tempfile
from types import SimpleNamespace

import pytest

from app.services.pipeline.animation.generation.core import ManimEditor
from app.services.pipeline.animation.generation.processors import Animator
from app.services.pipeline.animation.generation.validation.spatial.models import (
    FrameCapture,
    SpatialIssue,
    SpatialValidationResult,
)


class DummyPart:
    @classmethod
    def from_data(cls, data, mime_type):
        return {"data": data, "mime_type": mime_type}

    @classmethod
    def from_bytes(cls, data, mime_type):
        return {"data": data, "mime_type": mime_type, "from": "bytes"}


class DummyTypes:
    Part = DummyPart


class DummyEngine:
    def __init__(self):
        self.types = DummyTypes()
        self.last_contents = None

    async def generate(self, prompt, system_prompt=None, config=None, contents=None, **kwargs):
        self.last_contents = contents
        return {
            "success": True,
            "parsed_json": {"edits": []},
            "response": "{}",
        }


@pytest.mark.asyncio
async def test_surgical_fix_attaches_screenshots():
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
    try:
        tmp.write(b"fakepng")
        tmp.close()

        spatial = SpatialValidationResult(
            valid=False,
            warnings=[
                SpatialIssue(
                    line_number=1,
                    severity="warning",
                    message="Highlight miss",
                    code_snippet="self.play(Indicate(x))",
                    frame_id=tmp.name,
                )
            ],
            frame_captures=[FrameCapture(tmp.name, 1.0, ["e1"])],
        )
        validation = SimpleNamespace(spatial=spatial)

        animator = Animator.__new__(Animator)
        animator.engine = DummyEngine()
        animator.editor = ManimEditor()

        await animator._apply_surgical_fix(
            code="from manim import *",
            errors="Highlight miss",
            validation=validation,
            attempt=1,
        )

        assert isinstance(animator.engine.last_contents, list)
        assert len(animator.engine.last_contents) == 2
        assert "VISUAL CONTEXT" in animator.engine.last_contents[0]
    finally:
        import os
        if tmp and os.path.exists(tmp.name):
            os.remove(tmp.name)
