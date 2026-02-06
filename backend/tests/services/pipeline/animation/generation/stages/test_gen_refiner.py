
import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.services.pipeline.animation.generation.stages.refiner import Refiner
from app.services.pipeline.animation.generation.core.validation.models import ValidationIssue, IssueSeverity, IssueConfidence, IssueCategory
from app.services.pipeline.animation.generation.core.validation.static import ValidationResult

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
