"""
Reproduction Test for "Missed Spatial Errors"
Checking if errors that occur mid-scene are caught even if cleaned up at the end.
"""
import pytest
from app.services.pipeline.animation.generation.core.validation.runtime import RuntimeValidator

# Logic:
# 1. Add object at X=10 (Violation)
# 2. Wait (Check should happen here)
# 3. Remove object (Violation cleared)
# 4. End of construct
MID_SCENE_VIOLATION_CODE = """
from manim import *

class TestScene(Scene):
    def construct(self):
        # 1. Violation
        c = Circle().move_to(RIGHT * 10) 
        self.add(c)
        
        # 2. Key moment where validator MUST catch it
        self.wait(1)
        
        # 3. Cleanup
        self.remove(c)
        self.wait(1)
"""

@pytest.mark.asyncio
async def test_mid_scene_violation():
    validator = RuntimeValidator()
    result = await validator.validate(MID_SCENE_VIOLATION_CODE, enable_spatial_checks=True)
    
    # This assertion expects the validator to be smart enough to verify MID-SCENE.
    # Currently it fails (valid=True) because checks obey the "end-state-only" flaw.
    assert not result.valid
    assert any("out of bounds" in e for e in result.errors)
