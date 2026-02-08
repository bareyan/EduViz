from app.services.pipeline.animation.prompts.schemas import CHOREOGRAPHY_SCHEMA


def test_choreography_schema_requires_richer_step_metadata():
    step_schema = CHOREOGRAPHY_SCHEMA["properties"]["segments"]["items"]["properties"]["steps"]["items"]
    step_props = step_schema["properties"]

    assert "visual_change" in step_props
    assert "narration_cue" in step_props
    assert "data_binding" in step_props
    assert "visual_change" in step_schema["required"]
    assert "narration_cue" in step_schema["required"]


def test_choreography_schema_includes_object_visual_description():
    object_schema = CHOREOGRAPHY_SCHEMA["properties"]["objects"]["items"]
    object_props = object_schema["properties"]
    assert "visual_description" in object_props
    assert "layout_zone" in object_props
    assert "layout_zone" in object_schema["required"]


def test_choreography_schema_restricts_step_position_values():
    step_schema = CHOREOGRAPHY_SCHEMA["properties"]["segments"]["items"]["properties"]["steps"]["items"]
    position_schema = step_schema["properties"]["position"]
    assert "enum" in position_schema
    assert "center" in position_schema["enum"]
    assert "upper_left" in position_schema["enum"]
    assert "x,y" in position_schema["enum"]


def test_choreography_schema_restricts_object_relation_values():
    object_props = CHOREOGRAPHY_SCHEMA["properties"]["objects"]["items"]["properties"]
    relation_schema = object_props["relation"]
    relation_options = relation_schema["anyOf"][0]["enum"]
    assert relation_options == ["above", "below", "left_of", "right_of"]
