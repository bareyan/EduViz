import json
from pathlib import Path
from unittest.mock import mock_open, patch

from app.routes.jobs import _load_visual_script


def test_load_visual_script_prefers_section_visual_description():
    section = {"visual_description": "Use a number line animation."}
    section_dir = Path("outputs/job/sections/0")

    value = _load_visual_script(section, section_dir)

    assert value == "Use a number line animation."


def test_load_visual_script_falls_back_to_choreography_plan_file():
    section = {"visual_description": ""}
    section_dir = Path("outputs/job/sections/0")
    mock_plan = {"scene_type": "2D", "steps": [{"action": "Write", "target": "formula"}]}

    with patch("app.routes.jobs.validate_path_within_directory", return_value=True), \
         patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.is_file", return_value=True), \
         patch("builtins.open", mock_open(read_data=json.dumps(mock_plan))):
        value = _load_visual_script(section, section_dir)

    assert "scene_type" in value
    assert "steps" in value
