from app.services.pipeline.animation.generation import processors


def test_plan_schema_includes_scene_type_and_camera():
    schema = processors.PLAN_RESPONSE_SCHEMA
    assert "scene_type" in schema["properties"]
    assert schema["properties"]["scene_type"]["enum"] == ["2D", "3D"]
    assert "camera" in schema["properties"]


def test_plan_schema_action_and_type_enums():
    schema = processors.PLAN_RESPONSE_SCHEMA
    step_props = (
        schema["properties"]["segments"]["items"]["properties"]["steps"]["items"]["properties"]
    )
    assert "ReplacementTransform" in step_props["action"]["enum"]
    obj_props = schema["properties"]["objects"]["items"]["properties"]
    assert "ThreeDAxes" in obj_props["type"]["enum"]


def test_fix_schema_allows_full_code_lines():
    schema = processors.FIX_RESPONSE_SCHEMA
    assert "full_code_lines" in schema["properties"]
    assert "required" not in schema
