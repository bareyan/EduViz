"""
Tests for visual context formatting.
"""

from app.services.pipeline.animation.generation.validation.spatial.formatter import (
    format_visual_context_for_fix,
)
from app.services.pipeline.animation.generation.validation.spatial.models import (
    FrameCapture,
    SpatialIssue,
    SpatialValidationResult,
)


def test_format_visual_context_includes_frames():
    result = SpatialValidationResult(
        valid=False,
        errors=[
            SpatialIssue(
                line_number=5,
                severity="error",
                message="Overlap detected",
                code_snippet="text.move_to(ORIGIN)",
                frame_id="/tmp/frame_1.png",
            )
        ],
        warnings=[
            SpatialIssue(
                line_number=8,
                severity="warning",
                message="Highlight miss",
                code_snippet="self.play(Indicate(x))",
                frame_id="/tmp/frame_1.png",
            )
        ],
        frame_captures=[
            FrameCapture("/tmp/frame_1.png", 1.234, ["e1"]),
        ],
    )

    text = format_visual_context_for_fix(result)

    assert "VISUAL CONTEXT" in text
    assert "t=1.23s" in text
    assert "Overlap detected" in text
