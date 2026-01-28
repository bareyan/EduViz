"""
Tests for app.services.pipeline.animation.prompts
"""

import pytest
from unittest.mock import MagicMock
from app.services.pipeline.animation.prompts import (
    format_visual_script_for_prompt,
    format_segment_timing_for_prompt,
    AGENTIC_GENERATION_SYSTEM,
    AGENTIC_GENERATION_USER
)

class TestAnimationPrompts:
    """Test animation prompt formatting helpers."""

    def test_format_visual_script_with_dicts(self):
        """Test formatting from dictionary input."""
        visual_script = {
            "segments": [
                {
                    "segment_id": 0,
                    "narration_text": "Narration 1",
                    "visual_description": "Desc 1",
                    "visual_elements": ["Elem 1"],
                    "audio_duration": 5.0,
                    "post_narration_pause": 1.0
                }
            ]
        }
        
        result = format_visual_script_for_prompt(visual_script)
        
        assert "### Segment 1" in result
        assert "Narration 1" in result
        assert "Desc 1" in result
        assert "Elem 1" in result
        assert "5.0s audio" in result

    def test_format_visual_script_with_objects(self):
        """Test formatting from object input."""
        seg_mock = MagicMock()
        seg_mock.segment_id = 0
        seg_mock.narration_text = "Narration 2"
        seg_mock.visual_description = "Desc 2"
        seg_mock.visual_elements = ["Elem 2"]
        seg_mock.audio_duration = 10.0
        seg_mock.post_narration_pause = 0.5
        
        script_mock = MagicMock()
        script_mock.segments = [seg_mock]
        
        result = format_visual_script_for_prompt(script_mock)
        
        assert "### Segment 1" in result
        assert "Narration 2" in result
        assert "Desc 2" in result
        assert "10.0s audio" in result

    def test_format_visual_script_none(self):
        assert "No visual script provided" in format_visual_script_for_prompt(None)

    def test_format_segment_timing_with_dicts(self):
        """Test timing table formatting from dict."""
        visual_script = {
            "segments": [
                {
                    "segment_id": 0,
                    "audio_duration": 5.0,
                    "post_narration_pause": 2.0
                },
                {
                    "segment_id": 1,
                    "audio_duration": 3.0,
                    "post_narration_pause": 0.0
                }
            ]
        }
        
        result = format_segment_timing_for_prompt(visual_script)
        
        assert "Segment | Audio Duration" in result
        assert "7.0s" in result # Total for seg 0
        assert "3.0s" in result # Total for seg 1
        assert "10.0s" in result # Cumulative

    def test_format_segment_timing_with_objects(self):
        """Test timing table formatting from objects."""
        seg1 = MagicMock()
        seg1.segment_id = 0
        seg1.audio_duration = 5.0
        seg1.post_narration_pause = 0.0
        
        script_mock = MagicMock()
        script_mock.segments = [seg1]
        
        result = format_segment_timing_for_prompt(script_mock)
        
        assert "5.0s" in result
        assert str(seg1.segment_id + 1) in result

    def test_prompt_templates_exist(self):
        """Verify key prompt templates are instantiated."""
        assert AGENTIC_GENERATION_SYSTEM is not None
        assert AGENTIC_GENERATION_USER is not None
        assert AGENTIC_GENERATION_SYSTEM.description
        assert AGENTIC_GENERATION_USER.template
