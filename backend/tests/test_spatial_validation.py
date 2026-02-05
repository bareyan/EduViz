"""Quick functional tests for the new validation + triage system."""

from app.services.pipeline.animation.generation.core.validation.models import (
    IssueCategory, IssueConfidence, IssueSeverity, ValidationIssue,
)
from app.services.pipeline.animation.generation.core.validation.static import (
    ValidationResult,
)
from app.services.pipeline.animation.generation.refinement.deterministic_fixer import (
    DeterministicFixer,
)
from app.services.pipeline.animation.generation.core.validation.spatial import (
    SpatialCheckInjector,
)


def test_issue_routing():
    """Test that issues route correctly through triage."""
    # CRITICAL/HIGH/auto_fixable → auto_fix
    issue = ValidationIssue(
        severity=IssueSeverity.CRITICAL,
        confidence=IssueConfidence.HIGH,
        category=IssueCategory.TEXT_OVERLAP,
        message="Text overlap: 'Title' overlaps 'Subtitle'",
        auto_fixable=True,
        details={"text1": "Title", "text2": "Subtitle", "overlap_ratio": 0.8},
    )
    assert issue.should_auto_fix is True
    assert issue.requires_llm is False
    assert issue.needs_verification is False
    print("  issue routing (auto_fix): PASS")

    # INFO/LOW → needs verification (NOT skipped)
    info = ValidationIssue(
        severity=IssueSeverity.INFO,
        confidence=IssueConfidence.LOW,
        category=IssueCategory.OBJECT_OCCLUSION,
        message="Flash covers text",
    )
    assert info.needs_verification is True
    assert info.should_auto_fix is False
    print("  issue routing (needs_verification): PASS")

    # CRITICAL + not auto-fixable → requires LLM
    critical_llm = ValidationIssue(
        severity=IssueSeverity.CRITICAL,
        confidence=IssueConfidence.HIGH,
        category=IssueCategory.TEXT_OVERLAP,
        message="Complex overlap",
        auto_fixable=False,
    )
    assert critical_llm.requires_llm is True
    assert critical_llm.should_auto_fix is False
    assert critical_llm.needs_verification is False
    print("  issue routing (LLM escalation): PASS")

    # WARNING/LOW → needs verification
    warn_low = ValidationIssue(
        severity=IssueSeverity.WARNING,
        confidence=IssueConfidence.LOW,
        category=IssueCategory.OBJECT_OCCLUSION,
        message="Uncertain occlusion",
    )
    assert warn_low.needs_verification is True
    assert warn_low.requires_llm is False
    print("  issue routing (warning/low → verify): PASS")


def test_issue_categories():
    """Test new category types work correctly."""
    syntax = ValidationIssue(
        severity=IssueSeverity.CRITICAL,
        confidence=IssueConfidence.HIGH,
        category=IssueCategory.SYNTAX,
        message="invalid syntax",
        line=5,
    )
    assert syntax.is_spatial is False
    assert syntax.category == IssueCategory.SYNTAX

    runtime = ValidationIssue(
        severity=IssueSeverity.CRITICAL,
        confidence=IssueConfidence.HIGH,
        category=IssueCategory.RUNTIME,
        message="ZeroDivisionError",
        line=10,
    )
    assert runtime.is_spatial is False

    oob = ValidationIssue(
        severity=IssueSeverity.CRITICAL,
        confidence=IssueConfidence.HIGH,
        category=IssueCategory.OUT_OF_BOUNDS,
        message="Object out of frame",
    )
    assert oob.is_spatial is True
    print("  issue categories: PASS")


def test_validation_result_issues_only():
    """Test ValidationResult has no legacy errors field."""
    result = ValidationResult(valid=True)

    # No 'errors' attribute
    assert not hasattr(result, 'errors'), "Legacy errors field should be removed"

    issue = ValidationIssue(
        severity=IssueSeverity.CRITICAL,
        confidence=IssueConfidence.HIGH,
        category=IssueCategory.TEXT_OVERLAP,
        message="overlap",
        auto_fixable=True,
    )
    result.add_issue(issue)
    assert result.valid is False  # CRITICAL → invalid
    assert len(result.issues) == 1
    assert len(result.critical_issues) == 1
    assert len(result.spatial_issues) == 1
    assert len(result.non_spatial_issues) == 0
    print("  ValidationResult (issues-only): PASS")


def test_validation_result_helpers():
    """Test ValidationResult helper properties."""
    result = ValidationResult()
    result.add_issue(ValidationIssue(
        severity=IssueSeverity.CRITICAL,
        confidence=IssueConfidence.HIGH,
        category=IssueCategory.SYNTAX,
        message="bad syntax",
    ))
    result.add_issue(ValidationIssue(
        severity=IssueSeverity.WARNING,
        confidence=IssueConfidence.MEDIUM,
        category=IssueCategory.OUT_OF_BOUNDS,
        message="near edge",
    ))
    assert len(result.spatial_issues) == 1
    assert len(result.non_spatial_issues) == 1
    assert result.valid is False  # Has CRITICAL
    summary = result.error_summary()
    assert "bad syntax" in summary
    assert "near edge" in summary
    print("  ValidationResult helpers: PASS")


def test_to_fixer_context():
    """Test to_fixer_context includes line and category."""
    issue = ValidationIssue(
        severity=IssueSeverity.CRITICAL,
        confidence=IssueConfidence.HIGH,
        category=IssueCategory.RUNTIME,
        message="ZeroDivisionError: division by zero",
        line=42,
        fix_hint="Remove the division",
    )
    ctx = issue.to_fixer_context()
    assert "runtime/critical" in ctx
    assert "Line 42" in ctx
    assert "Remove the division" in ctx
    print("  to_fixer_context: PASS")


def test_to_verification_prompt():
    """Test low-confidence issues produce verification prompts."""
    issue = ValidationIssue(
        severity=IssueSeverity.INFO,
        confidence=IssueConfidence.LOW,
        category=IssueCategory.OBJECT_OCCLUSION,
        message="Flash covers Title text",
        details={"overlap_ratio": 0.3},
    )
    prompt = issue.to_verification_prompt()
    assert "REAL" in prompt
    assert "FALSE_POSITIVE" in prompt
    assert "Flash covers Title text" in prompt
    print("  to_verification_prompt: PASS")


def test_known_pattern_fixes():
    """Test DeterministicFixer on known bad patterns."""
    fixer = DeterministicFixer()
    code = """from manim import *
class S(Scene):
    def construct(self):
        t = ValueTracker(0)
        v = t.number
        self.wait(0)
        obj.move_to(CENTER)
"""
    fixed, count = fixer.fix_known_patterns(code)
    assert "get_value()" in fixed
    assert "self.wait(0)" not in fixed
    assert "ORIGIN" in fixed
    print(f"  known pattern fixes ({count}x): PASS")


def test_coordinate_clamping():
    """Test out-of-bounds coordinate clamping."""
    fixer = DeterministicFixer()
    code = """from manim import *
class S(Scene):
    def construct(self):
        text = Text('Hello')
        text.move_to(RIGHT * 8.5)
"""
    issue = ValidationIssue(
        severity=IssueSeverity.CRITICAL,
        confidence=IssueConfidence.HIGH,
        category=IssueCategory.OUT_OF_BOUNDS,
        message="Object out of bounds",
        auto_fixable=True,
        details={"center_x": 8.5, "center_y": 0, "object_type": "Text"},
    )
    fixed, remaining, fixes = fixer.fix(code, [issue])
    assert "RIGHT * 5.5" in fixed
    assert fixes == 1
    assert len(remaining) == 0
    print("  coordinate clamping: PASS")


def test_text_overlap_fix():
    """Test text overlap deterministic fix."""
    fixer = DeterministicFixer()
    code = """from manim import *
class S(Scene):
    def construct(self):
        title = Text("Introduction")
        subtitle = Text("Chapter 1")
        title.move_to(ORIGIN)
        subtitle.move_to(ORIGIN)
"""
    issue = ValidationIssue(
        severity=IssueSeverity.CRITICAL,
        confidence=IssueConfidence.HIGH,
        category=IssueCategory.TEXT_OVERLAP,
        message="Text overlap: 'Introduction' overlaps 'Chapter 1'",
        auto_fixable=True,
        details={"text1": "Introduction", "text2": "Chapter 1", "overlap_ratio": 0.9},
    )
    fixed, remaining, fixes = fixer.fix(code, [issue])
    assert "next_to" in fixed or "shift" in fixed
    print(f"  text overlap fix ({fixes} fixes): PASS")


def test_spatial_injector():
    """Test SpatialCheckInjector output."""
    injector = SpatialCheckInjector()
    code = """from manim import *
class MyScene(Scene):
    def construct(self):
        t = Text('Hi')
        self.play(Create(t))
"""
    injected = injector.inject(code)
    assert "_perform_spatial_checks" in injected
    assert "_monitored_play" in injected
    assert "SPATIAL_ISSUES_JSON" in injected
    print("  SpatialCheckInjector: PASS")


def test_strategy_selector():
    """Test spatial strategy selection."""
    from app.services.pipeline.animation.generation.refinement.strategies import (
        StrategySelector,
    )
    sel = StrategySelector()

    s = sel.select("Spatial Issue: out of bounds at (8, 0)")
    assert s.name == "spatial_error", f"Got {s.name}"

    s2 = sel.select("text_overlap: Title overlaps Subtitle")
    assert s2.name == "spatial_error", f"Got {s2.name}"

    s3 = sel.select("NameError: 'foo' is not defined")
    assert s3.name == "name_error", f"Got {s3.name}"
    print("  strategy selector: PASS")


def test_issue_verifier_import():
    """Test IssueVerifier can be imported cleanly."""
    from app.services.pipeline.animation.generation.refinement.issue_verifier import (
        VerificationResult,
    )
    vr = VerificationResult()
    assert vr.total == 0
    assert vr.real == []
    assert vr.false_positives == []
    print("  IssueVerifier import: PASS")


if __name__ == "__main__":
    print("Running validation system tests...")
    test_issue_routing()
    test_issue_categories()
    test_validation_result_issues_only()
    test_validation_result_helpers()
    test_to_fixer_context()
    test_to_verification_prompt()
    test_known_pattern_fixes()
    test_coordinate_clamping()
    test_text_overlap_fix()
    test_spatial_injector()
    test_strategy_selector()
    test_issue_verifier_import()
    print("\nALL TESTS PASSED")
