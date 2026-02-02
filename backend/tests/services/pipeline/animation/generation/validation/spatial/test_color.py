"""
Tests for color contrast calculation.
Matches backend/app/services/pipeline/animation/generation/validation/spatial/color.py
"""

import pytest
from app.services.pipeline.animation.generation.validation.spatial.color import get_contrast_ratio

def test_high_contrast():
    """Test white on black (max contrast)."""
    black = [0, 0, 0]
    white = [1, 1, 1]
    ratio = get_contrast_ratio(white, black)
    assert ratio == 21.0

def test_low_contrast():
    """Test grey on dark grey (low contrast)."""
    grey1 = [0.4, 0.4, 0.4]
    grey2 = [0.5, 0.5, 0.5]
    ratio = get_contrast_ratio(grey1, grey2)
    assert ratio < 4.5

def test_no_contrast():
    """Test same colors."""
    red = [1, 0, 0]
    ratio = get_contrast_ratio(red, red)
    assert ratio == 1.0
