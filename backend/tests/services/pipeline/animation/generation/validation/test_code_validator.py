"""
Tests for CodeValidator aggregation logic.
Matches backend/app/services/pipeline/animation/generation/validation/code_validator.py
"""

import pytest
from unittest.mock import patch
from app.services.pipeline.animation.generation.validation.code_validator import CodeValidator

@pytest.fixture
def validator():
    return CodeValidator()

def test_aggregation_and_summary(validator):
    """Test that errors from both stages are aggregated in summary."""
    code = "class MyScene(Scene):\n    pass" # Invalid static (no construct)
    
    # Mock spatial to return a warning
    with patch.object(validator.spatial_validator, 'validate') as mock_spatial:
        from app.services.pipeline.animation.generation.validation.spatial.models import SpatialValidationResult, SpatialIssue
        mock_spatial.return_value = SpatialValidationResult(
            valid=True, 
            warnings=[SpatialIssue(2, "warning", "Low contrast", "Text()")]
        )
        
        result = validator.validate(code)
        
        assert result.valid is False # Because static failed
        summary = result.get_error_summary()
        
        assert "## STATIC ERRORS" in summary
        assert "## SPATIAL WARNINGS" in summary
        assert "missing the 'construct(self)' method" in summary
        assert "Low contrast" in summary

def test_syntax_kill_switch(validator):
    """Test that syntax errors prevent spatial validation execution."""
    code = "def broken(;" # Syntax error
    
    with patch.object(validator.spatial_validator, 'validate') as mock_spatial:
        result = validator.validate(code)
        assert result.valid is False
        assert "Syntax Error" in result.static.errors[0]
        assert not mock_spatial.called
        assert result.spatial.valid is True # Placeholder returned
