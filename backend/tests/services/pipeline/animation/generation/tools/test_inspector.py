"""
Tests for FrameInspector tool and multi-turn frame requests.
"""

import json
import tempfile
import os
from unittest.mock import Mock, MagicMock

import pytest

from app.services.pipeline.animation.generation.tools.inspector import FrameInspector
from app.services.pipeline.animation.generation.validation.spatial.models import (
    SpatialValidationResult,
    SpatialIssue,
    FrameCapture
)
from app.services.infrastructure.llm.tools import ToolExecutionError


class TestFrameInspector:
    """Test the FrameInspector tool."""
    
    def test_list_frames(self):
        """Test listing available frames."""
        result = SpatialValidationResult(
            valid=False,
            errors=[
                SpatialIssue(
                    line_number=10,
                    severity="error",
                    message="Text overlap",
                    code_snippet="text = Text('test')",
                    frame_id="/tmp/frame_1.png"
                )
            ],
            frame_captures=[
                FrameCapture("/tmp/frame_1.png", 1.5, ["e1"]),
                FrameCapture("/tmp/frame_2.png", 2.3, ["e2"])
            ]
        )
        
        inspector = FrameInspector(result)
        response = inspector.execute(action="list")
        
        data = json.loads(response)
        assert data["available_frames"] == 2
        assert len(data["frames"]) == 2
        assert data["frames"][0]["timestamp"] == 1.5
        assert data["frames"][0]["issues_count"] == 1
    
    def test_request_frame_view(self):
        """Test requesting to view a specific frame."""
        result = SpatialValidationResult(
            valid=False,
            errors=[
                SpatialIssue(
                    line_number=10,
                    severity="error",
                    message="Boundary violation",
                    code_snippet="rect = Rectangle()",
                    frame_id="/tmp/frame_1.png"
                )
            ],
            frame_captures=[
                FrameCapture("/tmp/frame_1.png", 1.5, ["e1"])
            ]
        )
        
        inspector = FrameInspector(result)
        response = inspector.execute(action="view", timestamp=1.5)
        
        data = json.loads(response)
        assert data["status"] == "Frame will be included in next response"
        assert data["timestamp"] == 1.5
        assert len(data["issues_at_frame"]) == 1
        
        # Verify frame was marked as requested
        requested = inspector.get_requested_frames()
        assert "/tmp/frame_1.png" in requested
    
    def test_request_nonexistent_frame(self):
        """Test that requesting a non-existent frame raises error."""
        result = SpatialValidationResult(
            valid=True,
            frame_captures=[
                FrameCapture("/tmp/frame_1.png", 1.5, ["e1"])
            ]
        )
        
        inspector = FrameInspector(result)
        
        with pytest.raises(ToolExecutionError) as exc_info:
            inspector.execute(action="view", timestamp=99.9)
        
        assert "No frame found" in str(exc_info.value)
        assert "1.5" in str(exc_info.value)  # Shows available timestamps
    
    def test_no_validation_result(self):
        """Test that tool fails gracefully without validation result."""
        inspector = FrameInspector(None)
        
        with pytest.raises(ToolExecutionError) as exc_info:
            inspector.execute(action="list")
        
        assert "No validation result available" in str(exc_info.value)
    
    def test_invalid_action(self):
        """Test that invalid action raises error."""
        result = SpatialValidationResult(valid=True, frame_captures=[])
        inspector = FrameInspector(result)
        
        with pytest.raises(ToolExecutionError) as exc_info:
            inspector.execute(action="invalid")
        
        assert "Unknown action" in str(exc_info.value)
    
    def test_view_without_timestamp(self):
        """Test that view action requires timestamp."""
        result = SpatialValidationResult(valid=True, frame_captures=[])
        inspector = FrameInspector(result)
        
        with pytest.raises(ToolExecutionError) as exc_info:
            inspector.execute(action="view")
        
        assert "timestamp parameter is required" in str(exc_info.value)
    
    def test_clear_requested_frames(self):
        """Test clearing requested frames list."""
        result = SpatialValidationResult(
            valid=False,
            frame_captures=[
                FrameCapture("/tmp/frame_1.png", 1.5, ["e1"])
            ]
        )
        
        inspector = FrameInspector(result)
        inspector.execute(action="view", timestamp=1.5)
        
        assert len(inspector.get_requested_frames()) == 1
        
        inspector.clear_requested_frames()
        
        assert len(inspector.get_requested_frames()) == 0
    
    def test_tool_definition(self):
        """Test that tool definition is properly formatted."""
        inspector = FrameInspector(None)
        definition = inspector.tool_definition
        
        assert definition["name"] == "inspect_frames"
        assert "parameters" in definition
        assert "action" in definition["parameters"]["properties"]
        assert "timestamp" in definition["parameters"]["properties"]
        assert definition["parameters"]["properties"]["action"]["enum"] == ["list", "view"]


@pytest.mark.asyncio
class TestMultiTurnFixLoop:
    """Test multi-turn conversation with frame requests."""
    
    async def test_frame_request_triggers_next_turn(self):
        """Test that requesting a frame triggers another LLM turn with the image."""
        from app.services.pipeline.animation.generation.animator import Animator
        from app.services.infrastructure.llm import PromptingEngine
        from app.services.pipeline.animation.generation.validation import CodeValidator
        
        # Create temp screenshot
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        tmp.write(b"\\x89PNG\\r\\n\\x1a\\n" + b"\\x00" * 100)
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
                        frame_id=tmp.name
                    )
                ],
                frame_captures=[
                    FrameCapture(tmp.name, 1.0, ["e1"])
                ]
            )
            
            # Mock engine.generate
            turn_count = [0]
            
            async def mock_generate(*args, **kwargs):
                turn_count[0] += 1
                
                if turn_count[0] == 1:
                    # First turn: LLM requests to see frame
                    return {
                        "success": True,
                        "response": "Let me check the frame",
                        "function_calls": [
                            {
                                "name": "inspect_frames",
                                "args": {"action": "view", "timestamp": 1.0}
                            }
                        ]
                    }
                else:
                    # Second turn: LLM applies fix (with frame image attached)
                    # Verify that contents now includes the image
                    if "contents" in kwargs:
                        contents = kwargs["contents"]
                        assert len(contents) >= 2  # Text + at least 1 image
                    
                    return {
                        "success": True,
                        "response": "Fixed code here",
                        "function_calls": [
                            {
                                "name": "apply_surgical_edit",
                                "args": {
                                    "code": "test code",
                                    "search_text": "old",
                                    "replacement_text": "new"
                                }
                            }
                        ]
                    }
            
            engine.generate = mock_generate
            
            # Call surgical fix
            code = "old code"
            result = await animator._execute_refinement_turn(code, "test error", validation)
            
            # Verify multi-turn happened
            assert turn_count[0] == 2, "Should have made 2 turns (frame request + fix)"
            
        finally:
            if os.path.exists(tmp.name):
                os.remove(tmp.name)
