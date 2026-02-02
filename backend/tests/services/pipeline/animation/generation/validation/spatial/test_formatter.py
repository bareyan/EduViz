"""
Tests for report formatting.
Matches backend/app/services/pipeline/animation/generation/validation/spatial/formatter.py
"""

import pytest
from app.services.pipeline.animation.generation.validation.spatial.models import SpatialValidationResult, SpatialIssue
from app.services.pipeline.animation.generation.validation.spatial.formatter import format_spatial_issues

def test_format_summary_errors():
    """Test formatting with errors."""
    res = SpatialValidationResult(
        valid=False,
        errors=[SpatialIssue(10, "error", "Overlaps everything", "obj.add()")],
        warnings=[]
    )
    summary = format_spatial_issues(res)
    assert "ERRORS:" in summary
    assert "Line 10" in summary
    assert "Overlaps everything" in summary

def test_format_summary_warnings():
    """Test formatting with warnings."""
    res = SpatialValidationResult(
        valid=True,
        errors=[],
        warnings=[SpatialIssue(5, "warning", "Low contrast", "Text()")]
    )
    summary = format_spatial_issues(res)
    assert "WARNINGS:" in summary
    assert "Low contrast" in summary

def test_format_clean():
    """Test formatting for no issues."""
    res = SpatialValidationResult(valid=True, errors=[], warnings=[])
    summary = format_spatial_issues(res)
    assert "No spatial layout issues found" in summary
