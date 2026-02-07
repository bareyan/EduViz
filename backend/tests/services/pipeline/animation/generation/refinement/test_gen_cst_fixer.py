
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


def test_fix_visual_quality_text_dominance():
    fixer = CSTFixer()
    code = """
class Scene(Scene):
    def construct(self):
        opt_lbl = Text("Optimal Solution", font_size=32)
        self.play(
            opt_lbl.animate.scale(1.2).set_color(YELLOW),
            run_time=1.0
        )
"""
    issue = ValidationIssue(
        severity=IssueSeverity.WARNING,
        confidence=IssueConfidence.HIGH,
        category=IssueCategory.VISUAL_QUALITY,
        message="Text dominance",
        details={"reason": "text_dominance", "text": "Optimal Solution"},
        auto_fixable=True,
    )

    fixed, remaining, count = fixer.fix(code, [issue])
    assert count == 1
    assert "opt_lbl.scale_to_fit_width" in fixed
    assert "1.2" not in fixed
    assert "1.08" in fixed


def test_fix_known_patterns_disables_outer_lines_when_grid_lines_used():
    fixer = CSTFixer()
    code = """
from manim import *
class SceneA(Scene):
    def construct(self):
        table = MathTable([["1"]], include_outer_lines=True)
        grid = table.get_grid_lines()
"""
    fixed, count = fixer.fix_known_patterns(code)
    assert count >= 1
    assert "include_outer_lines=False" in fixed


def test_fix_visual_quality_filled_shape_dominance():
    fixer = CSTFixer()
    code = """
class Scene(Scene):
    def construct(self):
        panel = Rectangle(width=12, height=6, fill_opacity=1.0)
"""
    issue = ValidationIssue(
        severity=IssueSeverity.CRITICAL,
        confidence=IssueConfidence.HIGH,
        category=IssueCategory.VISUAL_QUALITY,
        message="Filled rectangle dominates frame",
        details={"reason": "filled_shape_dominance", "object_type": "Rectangle"},
        auto_fixable=True,
    )

    fixed, remaining, count = fixer.fix(code, [issue])
    assert count == 1
    assert "panel.set_fill(opacity=0.15)" in fixed or "panel.set_fill(opacity = 0.15)" in fixed


def test_fix_out_of_bounds_text_edge_clipping_nudges_text():
    fixer = CSTFixer()
    code = """
class Scene(Scene):
    def construct(self):
        question = Text("Which edge to follow?")
"""
    issue = ValidationIssue(
        severity=IssueSeverity.CRITICAL,
        confidence=IssueConfidence.HIGH,
        category=IssueCategory.OUT_OF_BOUNDS,
        message="Text appears clipped near left edge",
        details={
            "is_text": True,
            "reason": "text_edge_clipping",
            "text": "Which edge to follow?",
            "edge": "left",
        },
        auto_fixable=True,
    )

    fixed, remaining, count = fixer.fix(code, [issue])
    assert count == 1
    assert "question.shift(RIGHT * 0.6)" in fixed


def test_fix_visual_quality_stroke_through_text_boosts_z_index():
    fixer = CSTFixer()
    code = """
class Scene(Scene):
    def construct(self):
        headers = MathTex("x_1", "x_2", "x_3")
"""
    issue = ValidationIssue(
        severity=IssueSeverity.CRITICAL,
        confidence=IssueConfidence.HIGH,
        category=IssueCategory.VISUAL_QUALITY,
        message="Stroke crosses x_2",
        details={"reason": "stroke_through_text", "text": "x_2"},
        auto_fixable=True,
    )

    fixed, remaining, count = fixer.fix(code, [issue])
    assert count == 1
    assert "headers.set_z_index(10)" in fixed
