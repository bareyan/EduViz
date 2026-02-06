
import pytest
from app.services.pipeline.animation.generation.refinement.cst_fixer import CSTFixer
from app.services.pipeline.animation.generation.core.validation.models import ValidationIssue, IssueCategory, IssueSeverity, IssueConfidence

def test_fix_known_patterns_wait_zero():
    fixer = CSTFixer()
    code = """
class Scene(Scene):
    def construct(self):
        self.wait(0)
        self.play(Write(t))
"""
    fixed, count = fixer.fix_known_patterns(code)
    assert count == 1
    assert "self.wait(0)" not in fixed
    assert "self.play(Write(t))" in fixed

def test_fix_out_of_bounds_clamping():
    fixer = CSTFixer()
    code = "obj.shift(expected_arg)" # Not matching structure for simple text replacement, 
    # but let's try matching the transformer logic:
    # CoordinateClampingTransformer looks for RIGHT * val
    
    code_in = "obj.shift(RIGHT * 20.0)"
    
    # We need to simulate an issue
    issue = ValidationIssue(
        severity=IssueSeverity.WARNING, 
        confidence=IssueConfidence.HIGH, 
        category=IssueCategory.OUT_OF_BOUNDS, 
        message="OOB", 
        details={"is_group_overflow": False},
        auto_fixable=True
    )
    
    # The transformer logic is in _fix_out_of_bounds
    fixed, remaining, count = fixer.fix(code_in, [issue])
    
    # Depending on SAFE_X_LIMIT (usually 7-8), 20.0 should be clamped
    assert count == 1
    assert "20.0" not in fixed
    assert "5.5" in fixed # checking typical limit (SAFE_X_LIMIT=5.5)

def test_fix_text_overlap():
    fixer = CSTFixer()
    code = """
t1 = Text("Hello")
t2 = Text("World")
"""
    issue = ValidationIssue(
        severity=IssueSeverity.WARNING, 
        confidence=IssueConfidence.HIGH, 
        category=IssueCategory.TEXT_OVERLAP, 
        message="Overlap",
        details={"text1": "Hello", "text2": "World"},
        auto_fixable=True
    )
    
    fixed, remaining, count = fixer.fix(code, [issue])
    assert count == 1
    # Check if a shift or next_to is added for t2
    # LibCST might format as buff=0.4 or buff = 0.4
    assert "t2.next_to(t1, DOWN" in fixed
    assert "buff" in fixed
    assert "0.4" in fixed

def test_fix_object_occlusion():
    fixer = CSTFixer()
    code = """
rect = Rectangle()
"""
    issue = ValidationIssue(
        severity=IssueSeverity.WARNING, 
        confidence=IssueConfidence.HIGH, 
        category=IssueCategory.OBJECT_OCCLUSION, 
        message="Occlusion", 
        details={"object_type": "Rectangle"},
        auto_fixable=True
    )
    
    fixed, remaining, count = fixer.fix(code, [issue])
    assert count == 1
    # Handle whitespace like set_fill(opacity=0) or set_fill(opacity = 0)
    assert "rect.set_fill" in fixed
    assert "opacity" in fixed
    assert "0" in fixed
