
import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.services.pipeline.animation.generation.stages.refiner import Refiner
from app.services.pipeline.animation.generation.core.validation.models import ValidationIssue, IssueSeverity, IssueConfidence, IssueCategory
from app.services.pipeline.animation.generation.core.validation.static import ValidationResult
from app.services.pipeline.animation.generation.refinement.issue_verifier import VerificationResult

@pytest.fixture
def refiner():
    mock_fixer = Mock()
    mock_fixer.reset = Mock()
    return Refiner(mock_fixer, max_attempts=2)

@pytest.mark.asyncio
async def test_refine_static_validation_failure(refiner):
    code = "bad code"
    
    # 1. Static validation fails
    refiner.static_validator.validate = AsyncMock(return_value=ValidationResult(
        valid=False, 
        issues=[ValidationIssue(IssueSeverity.CRITICAL, IssueConfidence.HIGH, IssueCategory.SYNTAX, "Syntax Error")]
    ))
    
    # 2. Fixer applies fix
    refiner.fixer.run_turn = AsyncMock(return_value=("fixed code", {}))
    # We must patch _apply_llm_fix if we want to mock it directly, or rely on run_turn being called inside it.
    
    # Run
    # Mocking subsequent passes to success to avoid loops
    refiner.static_validator.validate.side_effect = [
        ValidationResult(False, [ValidationIssue(IssueSeverity.CRITICAL, IssueConfidence.HIGH, IssueCategory.SYNTAX, "Syntax Error")]),
        ValidationResult(True, [])
    ]
    refiner.deterministic_fixer.fix_known_patterns = Mock(side_effect=lambda c: (c, 0))
    refiner.runtime_validator.validate = AsyncMock(return_value=ValidationResult(True, []))
    
    final_code, stable = await refiner.refine(code, "Title")
    
    assert final_code == "fixed code"
    assert stable is True
    assert refiner.fixer.run_turn.called

@pytest.mark.asyncio
async def test_refine_runtime_triage(refiner):
    code = "code"
    
    # 1. Static passes
    refiner.static_validator.validate = AsyncMock(return_value=ValidationResult(True, []))
    
    # 2. Deterministic fix
    refiner.deterministic_fixer.fix_known_patterns = Mock(side_effect=lambda c: (c, 0))
    
    # 3. Runtime fails with certain issue
    issue = ValidationIssue(IssueSeverity.CRITICAL, IssueConfidence.HIGH, IssueCategory.RUNTIME, "Runtime Error", auto_fixable=False)
    refiner.runtime_validator.validate = AsyncMock()
    refiner.runtime_validator.validate.side_effect = [
        ValidationResult(False, [issue]), # First time
        ValidationResult(True, [])      # Second time
    ]
    
    # 4. Triage -> LLM fix
    refiner.fixer.run_turn = AsyncMock(return_value=("fixed code", {}))
    
    final_code, stable = await refiner.refine(code, "Title")
    assert final_code == "fixed code"
    assert stable is True

@pytest.mark.asyncio
async def test_refine_exhausted(refiner):
    code = "broken"
    # Always fail runtime
    refiner.static_validator.validate = AsyncMock(return_value=ValidationResult(True, []))
    refiner.deterministic_fixer.fix_known_patterns = Mock(side_effect=lambda c: (c, 0))
    refiner.runtime_validator.validate = AsyncMock(return_value=ValidationResult(False, [ValidationIssue(IssueSeverity.CRITICAL, IssueConfidence.HIGH, IssueCategory.RUNTIME, "Err")]))
    
    # Fixer tries but maybe doesn't change anything or just keeps failing
    refiner.fixer.run_turn = AsyncMock(return_value=("broken", {}))
    
    final_code, stable = await refiner.refine(code, "Title")
    
    assert final_code == "broken"
    assert stable is False


@pytest.mark.asyncio
async def test_refine_revalidates_after_deterministic_fix(refiner):
    code = "orig_code"

    refiner.static_validator.validate = AsyncMock(side_effect=[
        ValidationResult(True, []),
        ValidationResult(True, []),
    ])
    refiner.deterministic_fixer.fix_known_patterns = Mock(side_effect=lambda c: (c, 0))

    issue = ValidationIssue(
        IssueSeverity.CRITICAL,
        IssueConfidence.HIGH,
        IssueCategory.TEXT_OVERLAP,
        "Text overlap",
        auto_fixable=True,
    )
    refiner.runtime_validator.validate = AsyncMock(side_effect=[
        ValidationResult(False, [issue]),
        ValidationResult(True, []),
    ])
    refiner.deterministic_fixer.fix = Mock(return_value=("fixed_code", [], 1))
    refiner.fixer.run_turn = AsyncMock(return_value=("llm_code_should_not_be_used", {}))

    final_code, stable = await refiner.refine(code, "Title")

    assert stable is True
    assert final_code == "fixed_code"
    assert refiner.runtime_validator.validate.call_count == 2
    refiner.fixer.run_turn.assert_not_called()


@pytest.mark.asyncio
async def test_triage_routes_verified_real_auto_fixable_to_deterministic(refiner):
    uncertain = ValidationIssue(
        IssueSeverity.WARNING,
        IssueConfidence.LOW,
        IssueCategory.TEXT_OVERLAP,
        "minor overlap",
        auto_fixable=True,
    )
    verified_auto = ValidationIssue(
        IssueSeverity.WARNING,
        IssueConfidence.MEDIUM,
        IssueCategory.TEXT_OVERLAP,
        "minor overlap [verified]",
        auto_fixable=True,
    )

    refiner.issue_verifier = Mock()
    refiner.issue_verifier.verify = AsyncMock(
        return_value=VerificationResult(real=[verified_auto], false_positives=[])
    )
    refiner.deterministic_fixer.fix = Mock(return_value=("det_fixed", [], 1))
    refiner._apply_llm_fix = AsyncMock(return_value="llm_fixed")

    new_code, stats = await refiner._triage_issues(
        "orig", [uncertain], 1, "Title", context=None
    )

    assert new_code == "det_fixed"
    assert stats["deterministic"] == 1
    assert stats["llm"] == 0
    assert stats["unresolved"] == 0
    refiner.deterministic_fixer.fix.assert_called_once()
    refiner._apply_llm_fix.assert_not_called()


@pytest.mark.asyncio
async def test_triage_mixed_routes_verified_uncertain_to_both_paths(refiner):
    certain_auto = ValidationIssue(
        IssueSeverity.CRITICAL,
        IssueConfidence.HIGH,
        IssueCategory.TEXT_OVERLAP,
        "certain auto",
        auto_fixable=True,
    )
    certain_llm = ValidationIssue(
        IssueSeverity.CRITICAL,
        IssueConfidence.HIGH,
        IssueCategory.RUNTIME,
        "certain llm",
        auto_fixable=False,
    )
    uncertain_auto = ValidationIssue(
        IssueSeverity.WARNING,
        IssueConfidence.LOW,
        IssueCategory.TEXT_OVERLAP,
        "uncertain auto",
        auto_fixable=True,
    )
    uncertain_non_auto = ValidationIssue(
        IssueSeverity.WARNING,
        IssueConfidence.LOW,
        IssueCategory.OBJECT_OCCLUSION,
        "uncertain non-auto",
        auto_fixable=False,
    )

    verified_auto = ValidationIssue(
        IssueSeverity.WARNING,
        IssueConfidence.MEDIUM,
        IssueCategory.TEXT_OVERLAP,
        "uncertain auto [verified]",
        auto_fixable=True,
    )
    verified_non_auto = ValidationIssue(
        IssueSeverity.WARNING,
        IssueConfidence.MEDIUM,
        IssueCategory.OBJECT_OCCLUSION,
        "uncertain non-auto [verified]",
        auto_fixable=False,
    )

    refiner.issue_verifier = Mock()
    refiner.issue_verifier.verify = AsyncMock(
        return_value=VerificationResult(
            real=[verified_auto, verified_non_auto],
            false_positives=[],
        )
    )
    # Simulate deterministic failing to fix one auto-fixable issue.
    refiner.deterministic_fixer.fix = Mock(
        return_value=("after_det", [verified_auto], 1)
    )
    refiner._apply_llm_fix = AsyncMock(return_value="after_llm")

    new_code, stats = await refiner._triage_issues(
        "orig",
        [certain_auto, certain_llm, uncertain_auto, uncertain_non_auto],
        1,
        "Title",
        context=None,
    )

    assert new_code == "after_llm"
    assert stats["deterministic"] == 1
    # LLM batch = certain_llm + deterministic remaining + verified_non_auto
    assert stats["llm"] == 3
    assert stats["unresolved"] == 3
    refiner.issue_verifier.verify.assert_called_once()
    refiner._apply_llm_fix.assert_called_once()


def test_issue_snapshot_includes_subject_center_and_reason(refiner):
    issue = ValidationIssue(
        IssueSeverity.WARNING,
        IssueConfidence.MEDIUM,
        IssueCategory.OUT_OF_BOUNDS,
        "Object partially clipped",
        auto_fixable=True,
        details={
            "object_subject": "Revenue",
            "center_x": -7.25,
            "center_y": 0.5,
            "reason": "text_edge_clipping",
        },
    )

    snapshot = refiner._issue_snapshot(issue)

    assert snapshot["subject"] == "Revenue"
    assert snapshot["center"] == {"x": -7.25, "y": 0.5}
    assert snapshot["reason"] == "text_edge_clipping"


def test_format_issue_log_line_appends_subject_and_context(refiner):
    issue = ValidationIssue(
        IssueSeverity.CRITICAL,
        IssueConfidence.HIGH,
        IssueCategory.OUT_OF_BOUNDS,
        "Text partially clipped at edge",
        auto_fixable=True,
        details={
            "text": "Objective Function",
            "center_x": 6.8,
            "center_y": 0.0,
            "reason": "text_edge_clipping",
        },
    )

    formatted = refiner._format_issue_log_line(issue)

    assert "subject=Objective Function" in formatted
    assert "at=(6.80,0.00)" in formatted
    assert "reason=text_edge_clipping" in formatted
