
import pytest
from app.services.pipeline.animation.generation.validation.timing_adjuster import TimingAdjuster

def test_timing_adjuster_with_excessive_wait():
    adjuster = TimingAdjuster()
    code = """
class MyScene(Scene):
    def construct(self):
        obj = Circle()
        self.play(Create(obj), run_time=2.0)
        self.wait(14.0)
"""
    target = 10.0
    # Current duration: 2 + 14 = 16.0
    # Expected: 2 + 8 = 10.0 (Wait reduced by 6s)
    
    fixed_code = adjuster.adjust(code, target)
    assert "self.wait(8.00)" in fixed_code
    assert "self.wait(14.0)" not in fixed_code

def test_timing_adjuster_with_insufficient_duration():
    adjuster = TimingAdjuster()
    code = """
class MyScene(Scene):
    def construct(self):
        obj = Circle()
        self.play(Create(obj), run_time=2.0)
        self.wait(2.0)
"""
    target = 10.0
    # Current duration: 2 + 2 = 4.0
    # Expected: 2 + 2 + 6.0 = 10.0 (Wait increased to 8.0)
    
    fixed_code = adjuster.adjust(code, target)
    assert "self.wait(8.00)" in fixed_code

def test_timing_adjuster_no_last_wait():
    adjuster = TimingAdjuster()
    code = """
class MyScene(Scene):
    def construct(self):
        obj = Circle()
        self.play(Create(obj), run_time=2.0)
"""
    target = 10.0
    # Current duration: 2.0
    # Expected: self.wait(8.0) appended
    
    fixed_code = adjuster.adjust(code, target)
    assert "self.wait(8.00)" in fixed_code

def test_timing_adjuster_complex_calls():
    adjuster = TimingAdjuster()
    code = """
class MyScene(Scene):
    def construct(self):
        self.play(FadeIn(txt)) # default 1.0
        self.play(Write(txt2), run_time=3.5)
        self.wait() # default 1.0
        self.play(FadeOut(txt2), run_time=0.5)
        self.wait(2.0)
"""
    # Total: 1.0 + 3.5 + 1.0 + 0.5 + 2.0 = 8.0
    target = 10.0
    # Diff = 2.0. Last wait (2.0) becomes 4.0.
    
    fixed_code = adjuster.adjust(code, target)
    assert "self.wait(4.00)" in fixed_code

def test_timing_adjuster_respects_indentation():
    adjuster = TimingAdjuster()
    code = """
class MyScene(Scene):
    def construct(self):
        if True:
            self.play(Create(Circle()))
            self.wait(2.0)
"""
    target = 5.0
    # Total: 1.0 + 2.0 = 3.0
    # Diff = 2.0. Last wait (2.0) becomes 4.0.
    
    fixed_code = adjuster.adjust(code, target)
    assert "            self.wait(4.00)" in fixed_code
