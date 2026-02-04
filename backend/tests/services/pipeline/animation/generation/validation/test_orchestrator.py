"""
Tests for CodeValidator aggregation logic.
Matches backend/app/services/pipeline/animation/generation/validation/code_validator.py
"""

import pytest
from unittest.mock import patch
from app.services.pipeline.animation.generation.validation.orchestrator import CodeValidator

@pytest.fixture
def validator():
    return CodeValidator()

def test_aggregation_and_summary(validator):
    """Test that errors from both stages are aggregated in summary when static passes."""
    code = "class MyScene(Scene):\n    def construct(self):\n        pass" # Valid static
    
    # Mock spatial to return a warning and an error
    with patch.object(validator.spatial_validator, 'validate') as mock_spatial:
        from app.services.pipeline.animation.generation.validation.spatial.models import SpatialValidationResult, SpatialIssue
        mock_spatial.return_value = SpatialValidationResult(
            valid=False, 
            errors=[SpatialIssue(5, "error", "Major overlap", "Text()")],
            warnings=[SpatialIssue(2, "warning", "Low contrast", "Text()")]
        )
        
        result = validator.validate(code)
        
        assert result.valid is False # Because spatial failed
        summary = result.get_error_summary()
        
        assert "## SPATIAL ERRORS" in summary
        assert "## SPATIAL WARNINGS" in summary
        assert "Major overlap" in summary
        assert "Low contrast" in summary

def test_static_fail_kill_switch(validator):
    """Test that any static failure (not just syntax) prevents spatial validation."""
    code = "class Empty(Scene): pass" # Missing construct()
    
    with patch.object(validator.spatial_validator, 'validate') as mock_spatial:
        result = validator.validate(code)
        assert result.valid is False
        assert "construct(self)" in result.static.errors[0]
        assert not mock_spatial.called
        assert len(result.spatial.warnings) == 0

def test_syntax_kill_switch(validator):
    """Test that syntax errors prevent spatial validation execution."""
    code = "def broken(;" # Syntax error
    
    with patch.object(validator.spatial_validator, 'validate') as mock_spatial:
        result = validator.validate(code)
        assert result.valid is False
        assert "Syntax Error" in result.static.errors[0]
        assert not mock_spatial.called
        assert result.spatial.valid is True # Placeholder returned
