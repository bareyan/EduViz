"""
Tests for helper utilities.
Matches backend/app/services/pipeline/animation/generation/validation/spatial/utils.py
"""

import pytest
from unittest.mock import MagicMock
from app.services.pipeline.animation.generation.validation.spatial.utils import get_atomic_mobjects

def test_atomic_mobjects_unfolding():
    """Test that VGroups are unfolded into atoms."""
    m1 = MagicMock()
    m2 = MagicMock()
    # Mock a group with two children
    group = MagicMock()
    group.submobjects = [m1, m2]
    # Children have no children
    m1.submobjects = []
    m2.submobjects = []
    
    # Mock classes
    manim_classes = {
        'Text': type('Text', (), {}),
        'MathTex': type('MathTex', (), {}),
        'Tex': type('Tex', (), {}),
        'Code': type('Code', (), {}),
        'ImageMobject': type('ImageMobject', (), {}),
        'NumberPlane': type('NumberPlane', (), {}),
        'Axes': type('Axes', (), {}),
        'Arrow': type('Arrow', (), {}),
        'Line': type('Line', (), {}),
        'DashedLine': type('DashedLine', (), {}),
        'Brace': type('Brace', (), {}),
        'Vector': type('Vector', (), {}),
        'ComplexPlane': type('ComplexPlane', (), {}),
        'Circle': type('Circle', (), {}),
        'Square': type('Square', (), {}),
        'Rectangle': type('Rectangle', (), {}),
        'VMobject': type('VMobject', (), {}),
    }

    # Make m1/m2 match 'Text'
    m1.__class__ = manim_classes['Text']
    m2.__class__ = manim_classes['Text']
    
    atoms = get_atomic_mobjects(group, manim_classes)
    assert len(atoms) == 2
    assert m1 in atoms
    assert m2 in atoms


