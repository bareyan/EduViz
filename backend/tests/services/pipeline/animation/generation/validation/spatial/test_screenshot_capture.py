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
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
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


class TestVisualContextFormatting:
    """Test visual context formatting for LLM prompts."""
    
    def test_format_visual_context_with_screenshots(self):
        """Test formatting visual context from validation result."""
        from app.services.pipeline.animation.generation.processors import Animator
        from app.services.infrastructure.llm import PromptingEngine
        from app.services.pipeline.animation.generation.validation import CodeValidator
        
        engine = PromptingEngine(config_key='animation_generation')
        validator = CodeValidator()
        animator = Animator(engine, validator)
        
        # Create mock validation with screenshots
        validation = Mock()
        validation.spatial = SpatialValidationResult(
            valid=False,
            errors=[
                SpatialIssue(
                    line_number=10,
                    severity="error",
                    message="Text overlaps with axis",
                    code_snippet="text = Text('label')",
                    suggested_fix="Adjust position",
                    frame_id="/tmp/frame_1.png"
                )
            ],
            warnings=[
                SpatialIssue(
                    line_number=15,
                    severity="warning",
                    message="Element near boundary",
                    code_snippet="rect = Rectangle()",
                    suggested_fix="Add margin",
                    frame_id="/tmp/frame_2.png"
                )
            ],
            frame_captures=[
                FrameCapture("/tmp/frame_1.png", 1.5, ["e1"]),
                FrameCapture("/tmp/frame_2.png", 2.3, ["e2"])
            ]
        )
        
        context = animator._format_visual_context(validation)
        
        assert "VISUAL CONTEXT" in context
        assert "t=1.5s" in context
        assert "t=2.3s" in context
        assert "Text overlaps with axis" in context
        assert "Element near boundary" in context
    
    def test_format_visual_context_empty_when_no_screenshots(self):
        """Test that visual context is empty when no screenshots exist."""
        from app.services.pipeline.animation.generation.processors import Animator
        from app.services.infrastructure.llm import PromptingEngine
        from app.services.pipeline.animation.generation.validation import CodeValidator
        
        engine = PromptingEngine(config_key='animation_generation')
        validator = CodeValidator()
        animator = Animator(engine, validator)
        
        validation = Mock()
        validation.spatial = SpatialValidationResult(valid=True, frame_captures=[])
        
        context = animator._format_visual_context(validation)
        assert context == ""


@pytest.mark.asyncio
class TestMultimodalLLMIntegration:
    """Test multimodal content generation for LLM."""
    
    async def test_surgical_fix_with_screenshots(self):
        """Test that _apply_surgical_fix builds multimodal content."""
        from app.services.pipeline.animation.generation.processors import Animator
        from app.services.infrastructure.llm import PromptingEngine
        from app.services.pipeline.animation.generation.validation import CodeValidator
        
        # Create temp screenshot
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        tmp.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)  # Minimal PNG header + data
        tmp.close()
        
        try:
            engine = PromptingEngine(config_key='animation_generation')
            validator = CodeValidator()
            animator = Animator(engine, validator)
            
            # Mock validation with screenshot
            validation = Mock()
            validation.spatial = SpatialValidationResult(
                valid=False,
                errors=[
                    SpatialIssue(
                        line_number=10,
                        severity="error",
                        message="Test error",
                        code_snippet="test = Text('test')",
                        suggested_fix="Fix it",
                        frame_id=tmp.name
                    )
                ],
                frame_captures=[
                    FrameCapture(tmp.name, 1.0, ["e1"])
                ]
            )
            
            # Mock engine.generate to capture call
            generate_called_with = {}
            
            async def mock_generate(*args, **kwargs):
                generate_called_with.update(kwargs)
                return {
                    "success": True,
                    "response": "Fixed code",
                    "function_calls": []
                }
            
            engine.generate = mock_generate
            
            # Call surgical fix
            code = "test code"
            await animator._apply_surgical_fix(code, "test error", validation)
            
            # Verify multimodal content was passed
            assert "contents" in generate_called_with
            contents = generate_called_with["contents"]
            assert isinstance(contents, list)
            assert len(contents) == 2  # Text + 1 image
            assert isinstance(contents[0], str)  # First is text prompt
            
        finally:
            # Cleanup
            if os.path.exists(tmp.name):
                os.remove(tmp.name)
    
    async def test_surgical_fix_without_screenshots(self):
        """Test that _apply_surgical_fix works without screenshots (text-only)."""
        from app.services.pipeline.animation.generation.processors import Animator
        from app.services.infrastructure.llm import PromptingEngine
        from app.services.pipeline.animation.generation.validation import CodeValidator
        
        engine = PromptingEngine(config_key='animation_generation')
        validator = CodeValidator()
        animator = Animator(engine, validator)
        
        # Mock validation without screenshots
        validation = Mock()
        validation.spatial = SpatialValidationResult(valid=True, frame_captures=[])
        
        # Mock engine.generate
        generate_called_with = {}
        
        async def mock_generate(*args, **kwargs):
            generate_called_with.update(kwargs)
            return {
                "success": True,
                "response": "Fixed code",
                "function_calls": []
            }
        
        engine.generate = mock_generate
        
        # Call surgical fix
        code = "test code"
        await animator._apply_surgical_fix(code, "test error", validation)
        
        # Verify text-only prompt was used
        assert "prompt" in generate_called_with
        assert isinstance(generate_called_with["prompt"], str)
        assert len(generate_called_with["prompt"]) > 0
