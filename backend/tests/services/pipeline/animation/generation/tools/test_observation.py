"""
Tests for ObservationTool.
"""

import pytest

from app.services.pipeline.animation.generation.tools.observation import ObservationTool


class TestObservationTool:
    """Test the observation tool."""
    
    def test_record_observation(self):
        """Test recording a basic observation."""
        tool = ObservationTool()
        
        result = tool.execute(
            observation="I see the text overlapping the axis in frame at 1.5s",
            category="frame_analysis"
        )
        
        assert "Observation recorded" in result
        assert len(tool.get_observations()) == 1
        assert tool.get_observations()[0]["category"] == "frame_analysis"
    
    def test_multiple_observations(self):
        """Test recording multiple observations."""
        tool = ObservationTool()
        
        tool.execute("Frame shows overlap", category="frame_analysis")
        tool.execute("Issue is likely positioning", category="issue_identification")
        tool.execute("Will use .shift() to fix", category="fix_strategy")
        
        observations = tool.get_observations()
        assert len(observations) == 3
        assert observations[0]["category"] == "frame_analysis"
        assert observations[1]["category"] == "issue_identification"
        assert observations[2]["category"] == "fix_strategy"
    
    def test_clear_observations(self):
        """Test clearing observations."""
        tool = ObservationTool()
        
        tool.execute("Test observation", category="general")
        assert len(tool.get_observations()) == 1
        
        tool.clear_observations()
        assert len(tool.get_observations()) == 0
    
    def test_default_category(self):
        """Test that category defaults to general."""
        tool = ObservationTool()
        
        result = tool.execute(observation="Just thinking aloud here")
        
        assert len(tool.get_observations()) == 1
        # Category should default to general
        obs = tool.get_observations()[0]
        assert "category" in obs
    
    def test_tool_definition(self):
        """Test tool definition structure."""
        tool = ObservationTool()
        definition = tool.tool_definition
        
        assert definition["name"] == "record_observation"
        assert "observation" in definition["parameters"]["properties"]
        assert "category" in definition["parameters"]["properties"]
        
        # Check category enum
        category_enum = definition["parameters"]["properties"]["category"]["enum"]
        assert "frame_analysis" in category_enum
        assert "issue_identification" in category_enum
        assert "fix_strategy" in category_enum
        assert "general" in category_enum
