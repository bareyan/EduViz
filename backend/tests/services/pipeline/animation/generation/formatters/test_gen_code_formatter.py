
from app.services.pipeline.animation.generation.formatters.code_formatter import CodeFormatter

def test_derive_class_name():
    # ID case
    assert CodeFormatter.derive_class_name({"id": "my-section"}) == "MySection"
    assert CodeFormatter.derive_class_name({"id": "my section"}) == "MySection"
    assert CodeFormatter.derive_class_name({"id": "intro_to_calculus"}) == "IntroToCalculus"
    
    # Index fallback
    assert CodeFormatter.derive_class_name({"index": 1}) == "Section1"

def test_summarize_segments():
    section = {
        "narration_segments": [
            {"start_time": 0.0, "text": "Hello"},
            {"start_time": 2.5, "text": "World"}
        ]
    }
    summary = CodeFormatter.summarize_segments(section)
    assert "- T+0.0s: Hello" in summary
    assert "- T+2.5s: World" in summary

def test_serialize_for_prompt():
    assert CodeFormatter.serialize_for_prompt(None) == "None provided"
    assert CodeFormatter.serialize_for_prompt("text") == "text"
    assert CodeFormatter.serialize_for_prompt({"a": 1}) == '{\n  "a": 1\n}' # JSON

def test_get_language_name():
    assert CodeFormatter.get_language_name("en") == "English"
    assert CodeFormatter.get_language_name("ru") == "Russian"
    assert CodeFormatter.get_language_name("unknown") == "English" # Default
