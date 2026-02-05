import json

from app.services.infrastructure.parsing.json_parser import (
    extract_largest_balanced_json,
    parse_json_response,
    parse_json_array_response,
    repair_json_payload,
)


def test_extract_largest_balanced_json_ignores_trailing_text():
    text = 'prefix {"a": 1, "b": "ok"} trailing junk'
    extracted = extract_largest_balanced_json(text)
    assert extracted == '{"a": 1, "b": "ok"}'
    assert parse_json_response(text)["a"] == 1


def test_extract_largest_balanced_json_handles_braces_in_string():
    text = 'prefix {"a": "brace } in string", "b": 2} tail'
    extracted = extract_largest_balanced_json(text)
    assert json.loads(extracted)["b"] == 2


def test_extract_largest_balanced_json_array():
    text = 'noise [1, 2, {"a": "b"}] trailing'
    extracted = extract_largest_balanced_json(text, expect_array=True)
    assert json.loads(extracted)[2]["a"] == "b"
    assert parse_json_array_response(text)[0] == 1


def test_repair_json_payload_recovers_full_code_lines():
    text = """{"edits": [], "full_code": "```python
print('hi')
```"}"""
    repaired = repair_json_payload(text)
    assert repaired is not None
    parsed = json.loads(repaired)
    assert parsed["edits"] == []
    assert parsed["full_code_lines"] == ["print('hi')"]
