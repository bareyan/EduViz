from app.services.pipeline.animation.generation.validation import code_validator
from app.services.pipeline.animation.generation.validation.runtime_validator import RuntimeValidationResult


def test_spatial_skipped_on_runtime_error(monkeypatch):
    validator = code_validator.CodeValidator()

    monkeypatch.setattr(
        validator.runtime_validator,
        "validate",
        lambda code: RuntimeValidationResult(
            valid=False,
            errors=["TypeError: bad"],
            exception_type="TypeError",
        ),
    )

    called = {"spatial": False}

    def _spatial_validate(_code):
        called["spatial"] = True
        return code_validator.SpatialValidationResult(valid=True, errors=[], warnings=[], info=[])

    monkeypatch.setattr(validator.spatial_validator, "validate", _spatial_validate)

    result = validator.validate("from manim import *\nclass A(Scene):\n    def construct(self):\n        pass")

    assert result.runtime.valid is False
    assert called["spatial"] is False
