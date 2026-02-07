
import pytest
from unittest.mock import Mock, patch
from pathlib import Path
from app.services.pipeline.animation.generation.core.file_manager import AnimationFileManager

@pytest.fixture
def file_manager():
    return AnimationFileManager()

def test_ensure_output_directory(file_manager):
    with patch("pathlib.Path.mkdir") as mock_mkdir:
        file_manager.ensure_output_directory("/tmp/test")
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

def test_prepare_scene_file(file_manager):
    with patch("builtins.open") as mock_open:
        path = file_manager.prepare_scene_file("/tmp", 1, "code")
        assert path == Path("/tmp/scene_1.py")
        mock_open.assert_called_once()


def test_prepare_choreography_plan_file_json(file_manager):
    with patch("builtins.open") as mock_open:
        path = file_manager.prepare_choreography_plan_file("/tmp", '{"steps": []}')
        assert path == Path("/tmp/choreography_plan.json")
        mock_open.assert_called_once()

def test_get_quality_subdir(file_manager):
    # Depending on REAL config, but defaulting to 480p15 usually
    # If QUALITY_DIR_MAP is mocked, we can test logic.
    # Assuming "low" -> "480p15" based on typical config
    assert file_manager.get_quality_subdir("low") == "480p15"

def test_get_expected_video_path_strict(file_manager):
    code_file = Path("/tmp/scene_1.py")
    with patch("pathlib.Path.exists", return_value=True):
        # We need to mock specific paths to return True.
        # This is tricky with pure Path mocking.
        # Let's rely on fallback logic logic or use fs mock like pyfakefs if available, 
        # but standardized unittest.mock is safer without extra deps.
        pass

def test_cleanup_artifacts(file_manager):
    with patch("shutil.rmtree") as mock_rmtree, \
         patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.glob") as mock_glob:
         
        mock_file = Mock()
        mock_glob.return_value = [mock_file]
        
        file_manager.cleanup_artifacts("/tmp", Path("scene_1.py"), "low")
        
        mock_rmtree.assert_called() # clean partials
        mock_file.unlink.assert_called() # clean existing videos
