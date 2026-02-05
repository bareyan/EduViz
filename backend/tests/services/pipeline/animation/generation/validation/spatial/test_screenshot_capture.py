"""
Tests for screenshot capture and visual context integration.

Verifies:
1. Screenshots are captured when spatial issues are detected
2. Deduplication works (same timestamp = same screenshot)
3. frame_id links issues to screenshots
4. Screenshots are included in validation results
5. Cleanup removes temporary files
"""

import os
from unittest.mock import Mock
import numpy as np

import pytest

from app.services.pipeline.animation.generation.validation.spatial.validator import SpatialValidator
from app.services.pipeline.animation.generation.validation.spatial.models import (
    SpatialValidationResult,
    SpatialIssue,
    FrameCapture
)


@pytest.fixture
def mock_scene():
    """Create a mock Manim scene with a frame renderer."""
    scene = Mock()
    scene.renderer = Mock()
    # Create a simple 100x100 RGB frame
    scene.renderer.get_frame.return_value = np.zeros((100, 100, 3), dtype=np.uint8)
    return scene


@pytest.fixture
def validator():
    """Create a SpatialValidator instance."""
    return SpatialValidator()


class TestScreenshotCapture:
    """Test screenshot capture during validation."""
    
    def test_capture_frame_creates_file(self, validator, mock_scene):
        """Test that _capture_frame_if_needed creates a PNG file."""
        frame_id = validator._capture_frame_if_needed(mock_scene, 1.234, "event_1")
        
        assert frame_id is not None
        assert os.path.exists(frame_id)
        assert frame_id.endswith(".png")
        
        # Cleanup
        os.remove(frame_id)
    
    def test_capture_deduplication_by_timestamp(self, validator, mock_scene):
        """Test that multiple issues at same timestamp share screenshot."""
        # Capture at exact same timestamp
        frame_id_1 = validator._capture_frame_if_needed(mock_scene, 1.234, "event_1")
        frame_id_2 = validator._capture_frame_if_needed(mock_scene, 1.234, "event_2")
        
        # Should be the same file
        assert frame_id_1 == frame_id_2
        assert len(validator.frame_captures) == 1
        
        # Check event IDs are tracked
        capture = list(validator.frame_captures.values())[0]
        assert "event_1" in capture.event_ids
        assert "event_2" in capture.event_ids
        
        # Cleanup
        os.remove(frame_id_1)
    
    def test_capture_different_timestamps(self, validator, mock_scene):
        """Test that different timestamps create separate screenshots."""
        frame_id_1 = validator._capture_frame_if_needed(mock_scene, 1.0, "event_1")
        frame_id_2 = validator._capture_frame_if_needed(mock_scene, 2.0, "event_2")
        
        assert frame_id_1 != frame_id_2
        assert len(validator.frame_captures) == 2
        assert os.path.exists(frame_id_1)
        assert os.path.exists(frame_id_2)
        
        # Cleanup
        os.remove(frame_id_1)
        os.remove(frame_id_2)
    
    def test_frame_capture_data_structure(self, validator, mock_scene):
        """Test FrameCapture dataclass stores correct data."""
        frame_id = validator._capture_frame_if_needed(mock_scene, 1.5, "test_event")
        
        capture = validator.frame_captures[1.5]
        assert isinstance(capture, FrameCapture)
        assert capture.screenshot_path == frame_id
        assert capture.timestamp == 1.5
        assert capture.event_ids == ["test_event"]
        
        # Cleanup
        os.remove(frame_id)


class TestValidationResultScreenshots:
    """Test screenshot integration in validation results."""
    
    def test_validation_result_includes_frame_captures(self):
        """Test that SpatialValidationResult includes frame_captures list."""
        result = SpatialValidationResult(
            valid=True,
            frame_captures=[
                FrameCapture("/tmp/frame_1.png", 1.0, ["event_1"]),
                FrameCapture("/tmp/frame_2.png", 2.0, ["event_2"])
            ]
        )
        
        assert len(result.frame_captures) == 2
        assert result.frame_captures[0].timestamp == 1.0
        assert result.frame_captures[1].timestamp == 2.0
    
    def test_spatial_issue_has_frame_id(self):
        """Test that SpatialIssue can link to a frame."""
        issue = SpatialIssue(
            line_number=10,
            severity="error",
            message="Text overlap detected",
            code_snippet="text.move_to(ORIGIN)",
            suggested_fix="Adjust positioning",
            frame_id="/tmp/frame_1.png"
        )
        
        assert issue.frame_id == "/tmp/frame_1.png"
    
    def test_cleanup_screenshots_removes_files(self):
        """Test that cleanup_screenshots removes temporary files."""
        # Create temporary files
        temp_files = []
        for i in range(3):
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            temp_files.append(tmp.name)
            tmp.close()
        
        result = SpatialValidationResult(
            valid=True,
            frame_captures=[
                FrameCapture(temp_files[0], 1.0, ["e1"]),
                FrameCapture(temp_files[1], 2.0, ["e2"]),
                FrameCapture(temp_files[2], 3.0, ["e3"])
            ]
        )
        
        # Verify files exist
        assert all(os.path.exists(f) for f in temp_files)
        
        # Cleanup
        result.cleanup_screenshots()
        
        # Verify files are removed
        assert not any(os.path.exists(f) for f in temp_files)
    
    def test_cleanup_screenshots_handles_missing_files(self):
        """Test that cleanup doesn't fail if files already removed."""
        result = SpatialValidationResult(
            valid=True,
            frame_captures=[
                FrameCapture("/nonexistent/file.png", 1.0, ["e1"])
            ]
        )
        
        # Should not raise exception
        result.cleanup_screenshots()
    
    def test_get_frame_helper(self):
        """Test get_frame helper method retrieves correct capture."""
        result = SpatialValidationResult(
            valid=True,
            frame_captures=[
                FrameCapture("/tmp/frame_1.png", 1.0, ["e1"]),
                FrameCapture("/tmp/frame_2.png", 2.0, ["e2"])
            ]
        )
        
        frame = result.get_frame("/tmp/frame_1.png")
        assert frame is not None
        assert frame.timestamp == 1.0
        
        # Non-existent frame
        assert result.get_frame("/tmp/nonexistent.png") is None

