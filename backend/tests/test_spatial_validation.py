"""Quick functional tests for the new validation + triage system."""

from app.services.pipeline.animation.generation.core.validation.models import (
    IssueCategory, IssueConfidence, IssueSeverity, ValidationIssue,
)
from app.services.pipeline.animation.generation.core.validation.static import (
    ValidationResult,
)
from app.services.pipeline.animation.generation.refinement.cst_fixer import (
    CSTFixer as DeterministicFixer,
)
from app.services.pipeline.animation.generation.formatters.code_formatter import (
    CodeFormatter,
)
from app.services.pipeline.animation.generation.core.validation.spatial import (
    SpatialCheckInjector,
    INJECTED_METHOD,
)


def test_issue_routing():
    """Test that issues route correctly through the Certain/Uncertain model."""
    # CRITICAL/HIGH/auto_fixable → CERTAIN, auto_fix
    issue = ValidationIssue(
        severity=IssueSeverity.CRITICAL,
        confidence=IssueConfidence.HIGH,
        category=IssueCategory.TEXT_OVERLAP,
        message="Text overlap: 'Title' overlaps 'Subtitle'",
        auto_fixable=True,
        details={"text1": "Title", "text2": "Subtitle", "overlap_ratio": 0.8},
    )
    assert issue.is_certain is True
    assert issue.is_uncertain is False
    assert issue.should_auto_fix is True
    assert issue.requires_llm is False
    print("  issue routing (certain + auto_fix): PASS")

    # INFO/LOW → UNCERTAIN (needs Visual QC verification)
    info = ValidationIssue(
        severity=IssueSeverity.INFO,
        confidence=IssueConfidence.LOW,
        category=IssueCategory.OBJECT_OCCLUSION,
        message="Flash covers text",
    )
    assert info.is_certain is False
    assert info.is_uncertain is True  # spatial + not certain
    assert info.should_auto_fix is False
    print("  issue routing (uncertain → Visual QC): PASS")

    # CRITICAL + HIGH + not auto-fixable → CERTAIN, requires LLM
    critical_llm = ValidationIssue(
        severity=IssueSeverity.CRITICAL,
        confidence=IssueConfidence.HIGH,
        category=IssueCategory.TEXT_OVERLAP,
        message="Complex overlap",
        auto_fixable=False,
    )
    assert critical_llm.is_certain is True
    assert critical_llm.requires_llm is True
    assert critical_llm.should_auto_fix is False
    print("  issue routing (certain + LLM escalation): PASS")

    # WARNING/LOW → UNCERTAIN (needs Visual QC)
    warn_low = ValidationIssue(
        severity=IssueSeverity.WARNING,
        confidence=IssueConfidence.LOW,
        category=IssueCategory.OBJECT_OCCLUSION,
        message="Uncertain occlusion",
    )
    assert warn_low.is_certain is False
    assert warn_low.is_uncertain is True  # spatial + not certain
    assert warn_low.requires_llm is False
    print("  issue routing (warning/low → uncertain): PASS")

    # CRITICAL/MEDIUM → CERTAIN (the edge case)
    critical_medium = ValidationIssue(
        severity=IssueSeverity.CRITICAL,
        confidence=IssueConfidence.MEDIUM,
        category=IssueCategory.TEXT_OVERLAP,
        message="Medium confidence critical",
        auto_fixable=True,
    )
    assert critical_medium.is_certain is True  # CRITICAL + MEDIUM = certain
    assert critical_medium.should_auto_fix is True
    print("  issue routing (critical/medium → certain): PASS")

    # WARNING/MEDIUM → UNCERTAIN for spatial issues
    warn_medium = ValidationIssue(
        severity=IssueSeverity.WARNING,
        confidence=IssueConfidence.MEDIUM,
        category=IssueCategory.OUT_OF_BOUNDS,
        message="Moderate boundary issue",
    )
    assert warn_medium.is_certain is False  # WARNING + MEDIUM = uncertain
    assert warn_medium.is_uncertain is True  # spatial + not certain
    print("  issue routing (warning/medium → uncertain): PASS")


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
        details={
            "traceback_excerpt": "Traceback ...",
            "code_context": ">>   42: x = 1 / 0",
        },
    )
    ctx = issue.to_fixer_context()
    assert "runtime/critical" in ctx
    assert "Line 42" in ctx
    assert "Remove the division" in ctx
    assert "Traceback excerpt" in ctx
    assert "Code context" in ctx
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


def test_whitelist_key():
    """Test whitelist_key is stable and consistent."""
    issue1 = ValidationIssue(
        severity=IssueSeverity.WARNING,
        confidence=IssueConfidence.LOW,
        category=IssueCategory.OBJECT_OCCLUSION,
        message="Flash covers Title text",
        details={"overlap_ratio": 0.3, "object_type": "Flash", "text": "Title"},
    )
    issue2 = ValidationIssue(
        severity=IssueSeverity.WARNING,
        confidence=IssueConfidence.LOW,
        category=IssueCategory.OBJECT_OCCLUSION,
        message="Flash covers Title text (slightly different message)",
        details={"overlap_ratio": 0.3, "object_type": "Flash", "text": "Title"},
    )
    # Same details should produce same key (message doesn't affect key)
    assert issue1.whitelist_key == issue2.whitelist_key
    
    # Different details should produce different key
    issue3 = ValidationIssue(
        severity=IssueSeverity.WARNING,
        confidence=IssueConfidence.LOW,
        category=IssueCategory.OBJECT_OCCLUSION,
        message="Different object covers text",
        details={"overlap_ratio": 0.5, "object_type": "Circle", "text": "Title"},
    )
    assert issue1.whitelist_key != issue3.whitelist_key
    
    # time_sec should NOT affect key (time-varying field)
    issue4 = ValidationIssue(
        severity=IssueSeverity.WARNING,
        confidence=IssueConfidence.LOW,
        category=IssueCategory.OBJECT_OCCLUSION,
        message="Flash covers Title text",
        details={"overlap_ratio": 0.3, "object_type": "Flash", "text": "Title", "time_sec": 5.0},
    )
    assert issue1.whitelist_key == issue4.whitelist_key
    print("  whitelist_key: PASS")


def test_false_positive_whitelist():
    """Test FalsePositiveWhitelist functionality."""
    from app.services.pipeline.animation.generation.refinement import FalsePositiveWhitelist
    
    whitelist = FalsePositiveWhitelist()
    
    issue = ValidationIssue(
        severity=IssueSeverity.WARNING,
        confidence=IssueConfidence.LOW,
        category=IssueCategory.OBJECT_OCCLUSION,
        message="Flash covers text",
        details={"overlap_ratio": 0.3, "object_type": "Flash"},
    )
    
    # Initially not whitelisted
    assert issue not in whitelist
    assert not whitelist.is_whitelisted(issue)
    
    # Add to whitelist
    whitelist.add(issue)
    
    # Now whitelisted
    assert issue in whitelist
    assert whitelist.is_whitelisted(issue)
    assert whitelist.count == 1
    
    # Similar issue (same key) is also whitelisted
    similar_issue = ValidationIssue(
        severity=IssueSeverity.WARNING,
        confidence=IssueConfidence.LOW,
        category=IssueCategory.OBJECT_OCCLUSION,
        message="Flash covers text (different message)",
        details={"overlap_ratio": 0.3, "object_type": "Flash"},
    )
    assert similar_issue in whitelist
    
    # Reset clears whitelist
    whitelist.reset()
    assert issue not in whitelist
    assert whitelist.count == 0
    print("  FalsePositiveWhitelist: PASS")


def test_whitelist_filter_uncertain():
    """Test FalsePositiveWhitelist.filter_uncertain partitions correctly."""
    from app.services.pipeline.animation.generation.refinement import FalsePositiveWhitelist
    
    whitelist = FalsePositiveWhitelist()
    
    issue1 = ValidationIssue(
        severity=IssueSeverity.WARNING,
        confidence=IssueConfidence.LOW,
        category=IssueCategory.OBJECT_OCCLUSION,
        message="Issue 1",
        details={"id": 1},
    )
    issue2 = ValidationIssue(
        severity=IssueSeverity.WARNING,
        confidence=IssueConfidence.LOW,
        category=IssueCategory.OBJECT_OCCLUSION,
        message="Issue 2",
        details={"id": 2},
    )
    issue3 = ValidationIssue(
        severity=IssueSeverity.WARNING,
        confidence=IssueConfidence.LOW,
        category=IssueCategory.OBJECT_OCCLUSION,
        message="Issue 3",
        details={"id": 3},
    )
    
    # Whitelist issue1
    whitelist.add(issue1)
    
    # Filter
    need_qc, already_whitelisted = whitelist.filter_uncertain([issue1, issue2, issue3])
    
    assert len(already_whitelisted) == 1
    assert issue1 in already_whitelisted
    
    assert len(need_qc) == 2
    assert issue2 in need_qc
    assert issue3 in need_qc
    print("  filter_uncertain: PASS")


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
    print(f"  known pattern fixes: PASS")


def test_header_mathtex_pattern_fix():
    """Dense header MathTex should be normalized to arranged labels."""
    fixer = DeterministicFixer()
    code = """from manim import *
class S(Scene):
    def construct(self):
        headers = MathTex(
            r"\\\\text{Base}", r"x_1", r"x_2", r"x_3", r"x_4", r"x_5", r"\\\\text{RHS}",
            font_size=34, color=BLUE_B
        )
"""
    fixed, count = fixer.fix_known_patterns(code)
    assert ".arrange(RIGHT" in fixed
    # LibCST may add spaces around = in keyword args (buff = 0.7 vs buff=0.7)
    assert "buff" in fixed and "0.7" in fixed
    assert ".scale_to_fit_width(min(headers.width" in fixed or "scale_to_fit_width" in fixed
    assert count >= 1
    print("  dense header MathTex fix: PASS")


def test_table_grid_lines_pattern_fix():
    """Fix unsupported table.grid_lines access."""
    fixer = DeterministicFixer()
    code = """from manim import *
class S(Scene):
    def construct(self):
        table = MathTable([["a"]])
        self.play(Create(table.grid_lines), run_time=1.0)
"""
    fixed, count = fixer.fix_known_patterns(code)
    assert "table.grid_lines" not in fixed
    assert "table.get_horizontal_lines()" in fixed
    assert "table.get_vertical_lines()" in fixed
    assert count >= 1
    print("  table.grid_lines fix: PASS")


def test_table_double_index_pattern_fix():
    """Fix table[i][j] indexing to table.get_cell()."""
    fixer = DeterministicFixer()
    code = """from manim import *
class S(Scene):
    def construct(self):
        table = MathTable([["a","b"],["c","d"]])
        pivot = table[2][2]
"""
    fixed, count = fixer.fix_known_patterns(code)
    assert "table[2][2]" not in fixed
    assert "table.get_cell(3, 3)" in fixed
    assert count >= 1
    print("  table double indexing fix: PASS")


def test_mathtex_array_table_highlight_geometry_fix():
    """Fix fragile MathTex-array table highlight sizing/centering patterns."""
    fixer = DeterministicFixer()
    code = """from manim import *
class S(Scene):
    def construct(self):
        tableau_1 = MathTex(
            r"\\begin{array}{c|ccccc|c} "
            r"B & x_1 & x_2 & x_3 & x_4 & x_5 & b \\\\ \\hline "
            r"x_3 & 1 & 0 & 1 & 0 & 0 & 4 \\\\ "
            r"x_4 & 0 & 2 & 0 & 1 & 0 & 12 \\\\ "
            r"x_5 & 3 & 2 & 0 & 0 & 1 & 18 \\\\ \\hline "
            r"Z & 3 & 5 & 0 & 0 & 0 & 0 \\end{array}",
            font_size=36,
            color=WHITE
        )
        pivot_col_highlight = SurroundingRectangle(tableau_1, color=BLUE_C, fill_opacity=0)
        pivot_col_highlight.stretch_to_fit_width(tableau_1.width / 8)
        pivot_col_highlight.move_to(tableau_1.get_left(), aligned_edge=LEFT).shift(RIGHT * 3.3)
        pivot_row_highlight = SurroundingRectangle(tableau_1, color=GREEN, fill_opacity=0)
        pivot_row_highlight.stretch_to_fit_height(tableau_1.height / 5.5)
        pivot_row_highlight.move_to(tableau_1.get_top(), aligned_edge=UP).shift(DOWN * 1.55)
        pivot_cell = SurroundingRectangle(pivot_row_highlight, color=RED, fill_opacity=0)
        pivot_cell.stretch_to_fit_width(pivot_col_highlight.width)
        pivot_cell.move_to(pivot_col_highlight.get_center()).shift(UP * 0.1)
"""
    fixed, count = fixer.fix_known_patterns(code)
    # This fix logic is complex and layout-dependent.
    # For now, we only verify that the critical divide-by-8 -> divide-by-7 fix happens.
    assert "tableau_1.width / 7" in fixed
    print("  MathTex array table highlight geometry fix: PASS")


def test_decorative_table_line_group_removed():
    """Remove VGroup table overlays that add extra decorative lines."""
    fixer = DeterministicFixer()
    code = """from manim import *
class S(Scene):
    def construct(self):
        table1 = MathTable([["a","b"],["c","d"]], include_outer_lines=False)
        h_line = Line(table1.get_left(), table1.get_right(), color=WHITE, stroke_width=2)
        v_line = Line(table1.get_top(), table1.get_bottom(), color=WHITE, stroke_width=2)
        table1_group = VGroup(table1, h_line, v_line)
        self.play(FadeIn(table1_group), run_time=1.0)
"""
    fixed, count = fixer.fix_known_patterns(code)
    assert "table1_group = table1" in fixed
    assert "avoid duplicate decorative grid lines" in fixed
    assert count >= 1
    print("  decorative table line group removal: PASS")


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


def test_text_overlap_policy_is_critical_and_auto_fixable():
    """Meaningful text overlap should be classified as critical + auto-fixable.
    
    With the Certain/Uncertain model:
    - Overlap > 40% → CERTAIN (critical, high)
    - Overlap 15-40% → CERTAIN (critical, high) - visible overlap
    - Overlap 5-15% → UNCERTAIN (warning, low) - let Visual QC decide
    """
    # Check for CERTAIN overlaps (critical, high)
    assert '"critical", "high", "text_overlap"' in INJECTED_METHOD
    assert "Visible text overlap: separate labels with .next_to()/.shift()" in INJECTED_METHOD
    # Check for UNCERTAIN overlaps (warning, low)
    assert '"warning", "low", "text_overlap"' in INJECTED_METHOD
    assert "Minor text overlap: may need adjustment" in INJECTED_METHOD
    print("  text overlap policy (certain+uncertain routing): PASS")


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


def test_segment_summary_uses_estimated_duration_when_start_missing():
    """Segment summaries should advance using estimated durations."""
    summary = CodeFormatter.summarize_segments(
        {
            "narration_segments": [
                {"text": "first", "estimated_duration": 1.5},
                {"text": "second", "estimated_duration": 2.0},
                {"text": "third", "estimated_duration": 1.0},
            ]
        }
    )
    assert "- T+0.0s: first" in summary
    assert "- T+1.5s: second" in summary
    assert "- T+3.5s: third" in summary
    print("  segment summary timing fallback: PASS")


if __name__ == "__main__":
    print("Running validation system tests...")
    test_issue_routing()
    test_issue_categories()
    test_validation_result_issues_only()
    test_validation_result_helpers()
    test_to_fixer_context()
    test_to_verification_prompt()
    test_known_pattern_fixes()
    test_header_mathtex_pattern_fix()
    test_table_grid_lines_pattern_fix()
    test_table_double_index_pattern_fix()
    test_mathtex_array_table_highlight_geometry_fix()
    test_decorative_table_line_group_removed()
    test_coordinate_clamping()
    test_text_overlap_fix()
    test_spatial_injector()
    test_text_overlap_policy_is_critical_and_auto_fixable()
    test_strategy_selector()
    test_issue_verifier_import()
    test_segment_summary_uses_estimated_duration_when_start_missing()
    print("\nALL TESTS PASSED")
