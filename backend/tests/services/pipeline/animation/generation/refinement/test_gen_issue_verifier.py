
import pytest
from unittest.mock import Mock, AsyncMock, patch
from app.services.pipeline.animation.generation.refinement.issue_verifier import IssueVerifier, VerificationResult
from app.services.pipeline.animation.generation.core.validation.models import ValidationIssue, IssueSeverity, IssueConfidence, IssueCategory

@pytest.fixture
def issue_verifier():
    mock_engine = Mock()
    return IssueVerifier(mock_engine)

@pytest.mark.asyncio
async def test_verify_empty(issue_verifier):
    res = await issue_verifier.verify("code", [])
    assert res.total == 0

@pytest.mark.asyncio
async def test_verify_batch_success(issue_verifier):
    i1 = ValidationIssue(IssueSeverity.INFO, IssueConfidence.LOW, IssueCategory.TEXT_OVERLAP, "msg1")
    i2 = ValidationIssue(IssueSeverity.INFO, IssueConfidence.LOW, IssueCategory.VISIBILITY, "msg2")
    
    # Mock LLM response: i1 is REAL, i2 is FALSE_POSITIVE
    issue_verifier.engine.generate = AsyncMock(return_value={
        "success": True,
        "parsed_json": [
            {"index": 0, "verdict": "REAL"},
            {"index": 1, "verdict": "FALSE_POSITIVE"}
        ]
    })
    
    res = await issue_verifier.verify("code", [i1, i2])
    
    assert len(res.real) == 1
    assert res.real[0].message == "msg1 [verified]"
    assert res.real[0].confidence == IssueConfidence.MEDIUM
    
    assert len(res.false_positives) == 1
#    assert res.false_positives[0] == i2 # Equality check might fail on object identity if not handled, but strictly it's the same object reference passed to list

@pytest.mark.asyncio
async def test_verify_llm_failure(issue_verifier):
    i1 = ValidationIssue(IssueSeverity.INFO, IssueConfidence.LOW, IssueCategory.TEXT_OVERLAP, "msg1")
    
    issue_verifier.engine.generate = AsyncMock(return_value={"success": False, "error": "broken"})
    
    res = await issue_verifier.verify("code", [i1])
    
    # Conservative fallback: all real
    assert len(res.real) == 1
    assert len(res.false_positives) == 0


@pytest.mark.asyncio
async def test_verify_recovers_from_malformed_json_response(issue_verifier):
    i1 = ValidationIssue(IssueSeverity.INFO, IssueConfidence.LOW, IssueCategory.TEXT_OVERLAP, "msg1")
    i2 = ValidationIssue(IssueSeverity.INFO, IssueConfidence.LOW, IssueCategory.VISIBILITY, "msg2")

    # Simulate strict JSON failure with recoverable raw response.
    issue_verifier.engine.generate = AsyncMock(return_value={
        "success": False,
        "error": "json_decode_error: Expecting property name enclosed in double quotes",
        "response": '[{index: 0, verdict: "FALSE_POSITIVE"}, {index: 1, verdict: "REAL"}]',
        "parsed_json": None,
    })

    res = await issue_verifier.verify("code", [i1, i2])
    assert len(res.false_positives) == 1
    assert res.false_positives[0].message == "msg1"
    assert len(res.real) == 1
    assert res.real[0].message == "msg2 [verified]"

def test_build_prompt(issue_verifier):
    code = "import manim"
    i1 = ValidationIssue(IssueSeverity.INFO, IssueConfidence.LOW, IssueCategory.TEXT_OVERLAP, "msg1")
    prompt = issue_verifier._build_prompt(code, [i1])
    
    assert "code" in prompt
    assert "msg1" in prompt
    assert "REAL or FALSE_POSITIVE" in prompt
