
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


def test_normalize_choreography_plan_adapts_legacy_null_strings():
    legacy = {
        "scene_type": "2D",
        "objects": [
            {
                "id": "title",
                "type": "Text",
                "text": "Hello",
                "appears_at": 0,
                "removed_at": 2,
                "relative_to": "null",
                "relation": "null",
            }
        ],
        "segments": [],
    }
    normalized = CodeFormatter.normalize_choreography_plan(legacy, language_name="English")
    obj = normalized["objects"][0]
    assert normalized["version"] == "2.0"
    assert obj["placement"]["type"] == "absolute"
    assert obj["placement"]["relative"] is None


def test_normalize_choreography_plan_quantizes_v2_times():
    v2 = {
        "version": "2.0",
        "scene": {
            "mode": "2D",
            "camera": None,
            "safe_bounds": {"x_min": -5.5, "x_max": 5.5, "y_min": -3, "y_max": 3},
        },
        "objects": [
            {
                "id": "title",
                "kind": "Text",
                "content": {"text": "A", "latex": None, "asset_path": None},
                "placement": {"type": "absolute", "absolute": {"x": 0, "y": 0}, "relative": None},
                "lifecycle": {"appear_at": 0.0004, "remove_at": 1.9996},
            }
        ],
        "timeline": [
            {
                "segment_index": 0,
                "start_at": 0.0004,
                "end_at": 1.9996,
                "actions": [
                    {"at": 0.12345, "op": "Write", "target": "title", "source": None, "run_time": 1.23456}
                ],
            }
        ],
        "constraints": {"language": "English", "max_visible_objects": 10, "forbidden_constants": ["TOP", "BOTTOM"]},
        "notes": [],
    }
    normalized = CodeFormatter.normalize_choreography_plan(v2, language_name="English")
    assert normalized["timeline"][0]["actions"][0]["at"] == 0.123
    assert normalized["timeline"][0]["actions"][0]["run_time"] == 1.235
