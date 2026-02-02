"""
Tests for geometric validation logic.
Matches backend/app/services/pipeline/animation/generation/validation/spatial/geometry.py
"""

import pytest
from unittest.mock import MagicMock
from app.services.pipeline.animation.generation.validation.spatial.geometry import get_overlap_metrics, get_boundary_violation

def test_no_overlap():
    """Test metrics for two separate objects."""
    m1 = MagicMock()
    m2 = MagicMock()
    m1.width = 1.0; m1.height = 1.0; m1.get_center.return_value = [0,0,0]
    m2.width = 1.0; m2.height = 1.0; m2.get_center.return_value = [5,5,0]
    
    area, center, desc = get_overlap_metrics(m1, m2)
    assert area == 0
    assert desc == "None"

def test_boundary_violation():
    """Test boundary check logic."""
    m = MagicMock()
    m.width = 1.0; m.height = 1.0
    # Mock bounds that exceed standard 14x8 frame
    m.get_center.return_value = [7.5, 0, 0] # center + 0.5 = 8.0 > (14/2 - margin)
    
    config = MagicMock()
    config.frame_width = 14.0
    config.frame_height = 8.0
    
    result = get_boundary_violation(m, config)
    assert result is not None
    dist, desc = result
    assert dist > 0
    assert "Right" in desc
