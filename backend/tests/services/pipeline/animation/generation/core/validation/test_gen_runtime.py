
import pytest
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path
from app.services.pipeline.animation.generation.core.validation.runtime import RuntimeValidator
from app.services.pipeline.animation.generation.core.validation.models import IssueCategory

@pytest.fixture
def validator():
    return RuntimeValidator()

@pytest.mark.asyncio
async def test_validate_success(validator):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stderr = ""
        
        result = await validator.validate("print('hello')")
        assert result.valid is True
        assert len(result.issues) == 0

@pytest.mark.asyncio
async def test_validate_with_spatial_issues(validator):
    # Simulate stderr with spatial JSON
    stderr = """
    Random log
    SPATIAL_ISSUES_JSON:[{"severity": "critical", "confidence": "high", "category": "text_overlap", "message": "Overlap"}]
    """
    with patch("subprocess.run") as mock_run, \
         patch("app.services.pipeline.animation.generation.core.validation.spatial.SpatialCheckInjector") as MockInjector:
        
        mock_run.return_value.returncode = 1 # Exit 1 is common when sys.exit called
        mock_run.return_value.stderr = stderr
        
        MockInjector.return_value.inject.return_value = "injected_code"
        
        result = await validator.validate("code", enable_spatial_checks=True)
        
        assert result.valid is False
        assert len(result.issues) == 1
        assert result.issues[0].category == IssueCategory.TEXT_OVERLAP

@pytest.mark.asyncio
async def test_validate_runtime_error(validator):
    stderr = """
    Traceback (most recent call last):
      File "scene.py", line 5, in construct
        x = 1 / 0
    ZeroDivisionError: division by zero
    """
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1
        mock_run.return_value.stderr = stderr
        
        result = await validator.validate("code")
        
        assert result.valid is False
        assert len(result.issues) == 1
        issue = result.issues[0]
        assert issue.category == IssueCategory.RUNTIME
        assert "ZeroDivisionError" in issue.message or "division by zero" in issue.message
        assert issue.line == 5

def test_parse_spatial_json(validator):
    stderr = 'SPATIAL_ISSUES_JSON:[{"severity":"info","confidence":"low","category":"visibility","message":"Hidden"}]'
    issues = validator._parse_spatial_json(stderr)
    assert len(issues) == 1
    assert issues[0].category == IssueCategory.VISIBILITY

def test_parse_spatial_warnings(validator):
    stderr = "SPATIAL_WARNING: Text overlap detected"
    issues = validator._parse_spatial_warnings(stderr)
    assert len(issues) == 1
    assert issues[0].category == IssueCategory.TEXT_OVERLAP


def test_prepare_media_dir_creates_tex_folder(validator):
    media_dir = Path("manim_dry_run_sample")
    with patch.object(Path, "mkdir") as mock_mkdir:
        validator._prepare_media_dir(media_dir)
        assert mock_mkdir.call_count == 2
