from app.services.pipeline.animation.prompts.schemas import CHOREOGRAPHY_SCHEMA


def _walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from _walk(value)
    elif isinstance(node, list):
        for value in node:
            yield from _walk(value)


def test_choreography_schema_avoids_union_type_lists():
    for node in _walk(CHOREOGRAPHY_SCHEMA):
        if "type" in node:
            assert not isinstance(node["type"], list)


def test_choreography_schema_keeps_nullable_fields_explicit():
    camera = CHOREOGRAPHY_SCHEMA["properties"]["scene"]["properties"]["camera"]
    source = (
        CHOREOGRAPHY_SCHEMA["properties"]["timeline"]["items"]["properties"]["actions"]["items"]["properties"]["source"]
    )
    assert camera.get("nullable") is True
    assert source.get("nullable") is True


def test_choreography_schema_omits_additional_properties_keywords():
    for node in _walk(CHOREOGRAPHY_SCHEMA):
        if not isinstance(node, dict):
            continue
        assert "additionalProperties" not in node
        assert "additional_properties" not in node


def test_choreography_schema_structural_nodes_define_type():
    for node in _walk(CHOREOGRAPHY_SCHEMA):
        if not isinstance(node, dict):
            continue
        if ("properties" in node or "items" in node) and "type" not in node:
            raise AssertionError(f"Schema node missing explicit type: {node}")
