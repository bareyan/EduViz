
import pytest
import json
from app.services.pipeline.animation.generation.validation import CodeValidator

def test_detect_zombie_mobject():
    """Test that an object manually set to 0 opacity but not removed is flagged as a zombie."""
    validator = CodeValidator()
    code = """
from manim import *
class ZombieScene(Scene):
    def construct(self):
        txt = Text("I am a zombie")
        self.add(txt)
        self.wait(1.0)
        txt.set_opacity(0)  # Manually set to 0 - this creates a zombie!
        self.wait(10.0)  # Should be flagged as zombie here
"""
    result = validator.validate_code(code)
    
    # Check for zombie error
    zombie_errors = [e for e in result["details"]["spatial"]["errors"] if "Zombie" in e["message"]]
    assert len(zombie_errors) > 0
    assert "Text" in zombie_errors[0]["message"]
    assert "0 opacity" in zombie_errors[0]["message"]

def test_no_zombie_if_removed():
    """Test that self.remove() prevents zombie flagging."""
    validator = CodeValidator()
    code = """
from manim import *
class SafeScene(Scene):
    def construct(self):
        txt = Text("I am safe")
        self.play(Write(txt))
        self.play(FadeOut(txt))
        self.remove(txt) # Explicit removal
        self.wait(10.0)
"""
    result = validator.validate_code(code)
    zombie_errors = [e for e in result["details"]["spatial"]["errors"] if "Zombie" in e["message"]]
    assert len(zombie_errors) == 0

def test_persistent_overlap_is_error():
    """Test that overlaps persisting across multiple wait/play calls stay identified."""
    validator = CodeValidator()
    code = """
from manim import *
class OverlapScene(Scene):
    def construct(self):
        t1 = Text("Base Layer").move_to(ORIGIN)
        t2 = Text("Overlap Layer").move_to(ORIGIN)
        self.add(t1, t2)
        self.wait(2.0)
        self.play(t2.animate.scale(1.1))
        self.wait(2.0)
"""
    result = validator.validate_code(code)
    overlap_errors = [e for e in result["details"]["spatial"]["errors"] if "overlaps" in e["message"]]
    assert len(overlap_errors) > 0
