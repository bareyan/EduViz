
import pytest
from app.services.pipeline.animation.generation.refinement.strategies import StrategySelector, FixStrategy

def test_strategy_selector_found():
    selector = StrategySelector()
    
    # Syntax Error
    s1 = selector.select("SyntaxError: invalid syntax")
    assert s1.name == "syntax_error"
    
    # Name Error
    s2 = selector.select("NameError: name 'x' is not defined")
    assert s2.name == "name_error"
    
    # Spatial
    s3 = selector.select("SpatialCheck: text_overlap detected")
    assert s3.name == "spatial_error"
    
    # Manim API
    s4 = selector.select("AttributeError: 'VGroup' has no attribute 'foo'")
    assert s4.name == "manim_api"

def test_strategy_selector_default():
    selector = StrategySelector()
    s = selector.select("Some unknown error")
    assert s.name == "general"

def test_fix_strategy_guidance():
    s = FixStrategy(
        name="test",
        description="desc",
        hints=["Hint 1", "Hint 2"],
        focus_areas=["Area 1"]
    )
    guidance = s.build_guidance()
    assert "## FIX STRATEGY HINTS" in guidance
    assert "- Hint 1" in guidance
    assert "## FOCUS AREAS" in guidance
    assert "- Area 1" in guidance
