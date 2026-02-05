from app.services.pipeline.animation.generation.validation import code_validator
from app.services.pipeline.animation.generation.validation.runtime_validator import RuntimeValidationResult
from app.services.pipeline.animation.generation.validation.static_validator import StaticValidationResult


def test_code_validator_emits_timing_logs(caplog, monkeypatch):
    validator = code_validator.CodeValidator()

    monkeypatch.setattr(
        validator.static_validator,
        "validate",
        lambda code: StaticValidationResult(valid=True, errors=[], warnings=[]),
    )
    monkeypatch.setattr(
        validator.runtime_validator,
        "validate",
        lambda code: RuntimeValidationResult(valid=True, errors=[]),
    )
    monkeypatch.setattr(
        validator.spatial_validator,
        "validate",
        lambda code: code_validator.SpatialValidationResult(valid=True, errors=[], warnings=[], info=[]),
    )

    with caplog.at_level("INFO"):
        validator.validate("from manim import *\nclass A(Scene):\n    def construct(self):\n        pass")

    timing_logs = [r for r in caplog.records if "Validation timings" in r.getMessage()]
    assert timing_logs

    record = timing_logs[-1]
    assert hasattr(record, "static_duration_ms")
    assert hasattr(record, "runtime_duration_ms")
    assert hasattr(record, "spatial_duration_ms")
    assert hasattr(record, "total_duration_ms")
