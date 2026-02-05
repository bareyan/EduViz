from app.services.pipeline.animation.generation.validation import runtime_validator


class FakeEngine:
    def __init__(self, linter_path):
        self.linter_path = linter_path
        class _Scene:
            def play(self, *args, **kwargs):
                return None

            def wait(self, *args, **kwargs):
                return None

        self.Scene = _Scene
        self.config = {}

    def initialize(self):
        return None

    def run_scenes(self, temp_filename):
        raise TypeError("Bad type")


def test_runtime_validator_catches_type_error(monkeypatch):
    monkeypatch.setattr(runtime_validator, "ManimEngine", FakeEngine)
    validator = runtime_validator.RuntimeValidator()
    result = validator.validate("from manim import *\nclass A(Scene):\n    def construct(self):\n        pass")

    assert result.valid is False
    assert result.exception_type == "TypeError"
    assert result.errors
