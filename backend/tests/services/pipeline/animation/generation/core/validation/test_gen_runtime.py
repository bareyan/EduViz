
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


def test_parse_spatial_json_visual_quality(validator):
    stderr = 'SPATIAL_ISSUES_JSON:[{"severity":"warning","confidence":"high","category":"visual_quality","message":"Dominant label"}]'
    issues = validator._parse_spatial_json(stderr)
    assert len(issues) == 1
    assert issues[0].category == IssueCategory.VISUAL_QUALITY

def test_parse_spatial_warnings(validator):
    stderr = "SPATIAL_WARNING: Text overlap detected"
    issues = validator._parse_spatial_warnings(stderr)
    assert len(issues) == 1
    assert issues[0].category == IssueCategory.TEXT_OVERLAP


def test_parse_spatial_uncertain_issue_is_low_confidence(validator):
    stderr = (
        'SPATIAL_ISSUES_JSON:[{"severity":"warning","confidence":"low",'
        '"category":"out_of_bounds","message":"Text clipped near edge"}]'
    )
    issues = validator._parse_spatial_json(stderr)
    assert len(issues) == 1
    assert issues[0].is_uncertain is True


def test_prepare_media_dir_creates_tex_folder(validator):
    media_dir = Path("manim_dry_run_sample")
    with patch.object(Path, "mkdir") as mock_mkdir:
        validator._prepare_media_dir(media_dir)
        assert mock_mkdir.call_count == 2


@pytest.mark.asyncio
async def test_validate_preflight_blocks_grid_lines_attribute(validator):
    code = """
from manim import *
class SceneA(Scene):
    def construct(self):
        t = MathTable([["1"]])
        x = t.grid_lines
"""
    with patch("subprocess.run") as mock_run:
        result = await validator.validate(code)
        assert result.valid is False
        assert any("grid_lines" in issue.message for issue in result.issues)
        assert result.issues[0].line is not None
        mock_run.assert_not_called()


@pytest.mark.asyncio
async def test_validate_preflight_flags_duplicate_math_table_grid_lines(validator):
    code = """
from manim import *
class SceneA(Scene):
    def construct(self):
        t = MathTable(
            [["1", "2"], ["3", "4"]],
            include_outer_lines=True
        )
        grid = t.get_grid_lines()
"""
    with patch("subprocess.run") as mock_run:
        result = await validator.validate(code)
        assert result.valid is False
        assert any(
            issue.category == IssueCategory.VISUAL_QUALITY
            and "get_grid_lines" in issue.message
            for issue in result.issues
        )
        visual_issue = next(
            issue for issue in result.issues
            if issue.category == IssueCategory.VISUAL_QUALITY
        )
        assert visual_issue.auto_fixable is True
        assert visual_issue.details.get("reason") == "duplicate_grid_lines"
        assert visual_issue.details.get("table_var") == "t"
        mock_run.assert_not_called()


@pytest.mark.asyncio
async def test_validate_preflight_flags_duplicate_math_table_horizontal_lines(validator):
    code = """
from manim import *
class SceneA(Scene):
    def construct(self):
        t = MathTable(
            [["1", "2"], ["3", "4"]],
            include_outer_lines=True
        )
        grid = t.get_horizontal_lines()
"""
    with patch("subprocess.run") as mock_run:
        result = await validator.validate(code)
        assert result.valid is False
        assert any(
            issue.category == IssueCategory.VISUAL_QUALITY
            and "visual artifacts" in issue.message
            for issue in result.issues
        )
        mock_run.assert_not_called()


@pytest.mark.asyncio
async def test_validate_preflight_detects_get_cell_out_of_bounds(validator):
    code = """
from manim import *
class SceneA(Scene):
    def construct(self):
        t = MathTable(
            [["1", "2"], ["3", "4"]],
            col_labels=[MathTex("x1"), MathTex("x2")],
            row_labels=[MathTex("r1"), MathTex("r2")]
        )
        bad = t.get_cell((8, 8))
"""
    with patch("subprocess.run") as mock_run:
        result = await validator.validate(code)
        assert result.valid is False
        assert any(
            issue.category == IssueCategory.RUNTIME
            and "exceeds table bounds" in issue.message
            for issue in result.issues
        )
        mock_run.assert_not_called()


@pytest.mark.asyncio
async def test_validate_preflight_detects_negative_wait(validator):
    code = """
from manim import *
class SceneA(Scene):
    def construct(self):
        self.wait(1.0 - 2.5)
"""
    with patch("subprocess.run") as mock_run:
        result = await validator.validate(code)
        assert result.valid is False
        assert any(
            issue.category == IssueCategory.RUNTIME
            and "negative duration" in issue.message
            for issue in result.issues
        )
        mock_run.assert_not_called()


@pytest.mark.asyncio
async def test_validate_preflight_detects_nested_get_columns_oob(validator):
    code = """
from manim import *
class SceneA(Scene):
    def construct(self):
        t = MathTable(
            [["1", "2"], ["3", "4"]],
            col_labels=[MathTex("x1"), MathTex("x2")],
            row_labels=[MathTex("r1"), MathTex("r2")]
        )
        bad = t.get_columns()[10][0]
"""
    with patch("subprocess.run") as mock_run:
        result = await validator.validate(code)
        assert result.valid is False
        assert any(
            issue.category == IssueCategory.RUNTIME
            and "out of range" in issue.message
            for issue in result.issues
        )
        mock_run.assert_not_called()
