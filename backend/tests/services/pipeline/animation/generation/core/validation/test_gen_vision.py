
import pytest
from unittest.mock import Mock, AsyncMock, patch
from pathlib import Path
from app.services.pipeline.animation.generation.core.validation.vision import VisionValidator, FrameTarget
from app.services.pipeline.animation.generation.core.validation.models import ValidationIssue, IssueSeverity, IssueConfidence

@pytest.fixture
def vision_validator():
    mock_engine = Mock()
    return VisionValidator(mock_engine)

@pytest.mark.asyncio
async def test_verify_issues_empty(vision_validator):
    res = await vision_validator.verify_issues("video.mp4", [], "/tmp")
    assert res == []

@pytest.mark.asyncio
async def test_verify_issues_extract_and_analyze(vision_validator):
    issue = ValidationIssue(IssueSeverity.WARNING, IssueConfidence.LOW, "text_overlap", "Overlap", details={"time_sec": 1.5})
    
    # Mock extract_frame
    with patch.object(vision_validator, "_extract_frame", new_callable=AsyncMock) as mock_extract:
        mock_extract.return_value = True
        
        # Mock LLM response
        vision_validator.engine.generate = AsyncMock(return_value={
            "success": True,
            "parsed_json": {
                "issues": [{
                    "frame": "frame_0_t1.50.png",
                    "time_sec": 1.5,
                    "message": "Confirmed",
                    "severity": "critical",
                    "confidence": "high"
                }]
            }
        })
        
        # Mock file write/read needs (pathlib.read_bytes)
        with patch("pathlib.Path.read_bytes", return_value=b"img"):
            res = await vision_validator.verify_issues("video.mp4", [issue], "/tmp")
            
            assert len(res) == 1
            assert res[0].message == "Confirmed (t=1.50s)"
            mock_extract.assert_called()

@pytest.mark.asyncio
async def test_extract_frame_failure(vision_validator):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1
        
        res = await vision_validator._extract_frame("vid.mp4", Path("out.png"), 1.0)
        assert res is False
