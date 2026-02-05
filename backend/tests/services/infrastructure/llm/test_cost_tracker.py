"""
Tests for app.services.infrastructure.llm.cost_tracker

Tests token usage tracking and cost calculation.
"""

import pytest
from unittest.mock import MagicMock
from app.services.infrastructure.llm.cost_tracker import CostTracker, track_cost_safely


class TestCostTracker:
    """Test token usage and cost tracking."""

    @pytest.fixture
    def tracker(self):
        """Create a fresh CostTracker instance."""
        return CostTracker()

    def test_track_usage_gemini_response(self, tracker):
        """Test tracking usage from a Gemini-like response object."""
        model = "gemini-2.5-flash"
        # Mocking the Gemini response structure
        response = MagicMock()
        response.usage_metadata.prompt_token_count = 1000
        response.usage_metadata.candidates_token_count = 500
        
        tracker.track_usage(response, model)
        
        summary = tracker.get_summary()
        assert summary["total_input_tokens"] == 1000
        assert summary["total_output_tokens"] == 500
        assert summary["total_tokens"] == 1500
        
        # Calculation: (1000/1M * 0.15) + (500/1M * 0.60)
        # = 0.00015 + 0.00030 = 0.00045
        assert summary["total_cost_usd"] == 0.0004 # 0.00045 rounds to 0.0004 (half-to-even)

    def test_track_request_direct(self, tracker):
        """Test tracking usage directly with token counts."""
        model = "gemini-3-pro-preview"
        tracker.track_request(model, input_tokens=1000000, output_tokens=1000000)
        
        summary = tracker.get_summary()
        # Pricing: input 2.0, output 12.0
        assert summary["total_cost_usd"] == 14.0
        assert summary["by_model"][model]["cost_usd"] == 14.0

    def test_track_usage_unknown_model(self, tracker):
        """Test behavior when using a model not in PRICING."""
        tracker.track_request("mysterious-model", input_tokens=1000, output_tokens=1000)
        
        summary = tracker.get_summary()
        assert summary["total_tokens"] == 2000
        assert summary["total_cost_usd"] == 0.0 # Cost unknown

    def test_track_usage_none_response(self, tracker):
        """Verify None response is handled safely."""
        tracker.track_usage(None, "gemini-2.5-flash")
        assert tracker.token_usage["total_cost"] == 0.0

    def test_track_usage_missing_metadata(self, tracker):
        """Verify response without metadata is handled safely."""
        response = MagicMock(spec=[]) # No usage_metadata
        tracker.track_usage(response, "gemini-2.5-flash")
        assert tracker.token_usage["total_cost"] == 0.0

    def test_get_summary_rounding(self, tracker):
        """Test rounding of costs in summary."""
        model = "gemini-flash-lite-latest"
        tracker.track_request(model, input_tokens=1, output_tokens=1)
        # Cost is extremely small: (1/1M * 0.075) + (1/1M * 0.3) = 0.000000375
        summary = tracker.get_summary()
        assert summary["total_cost_usd"] == 0.0 # rounded to 4 places

    def test_track_cost_safely_wrapper(self, tracker):
        """Test the safety wrapper function."""
        # Test valid tracking
        response = MagicMock()
        response.usage_metadata.prompt_token_count = 100
        response.usage_metadata.candidates_token_count = 100
        track_cost_safely(tracker, response, "gemini-2.5-flash")
        assert tracker.token_usage["input_tokens"] == 100
        
        # Test None tracker
        track_cost_safely(None, response, "model") # Should not raise
        
        # Test tracker that Raises
        tracker.track_usage = MagicMock(side_effect=Exception("Boom"))
        track_cost_safely(tracker, response, "model") # Should not raise

    def test_visual_qc_summary_bug_documentation(self, tracker, capsys):
        """
        Documenting the behavior of visual_qc in print_summary.
        Currently 'visual_qc' is not in get_summary output, so it's skipped.
        """
        tracker.track_request("gemini-2.0-flash-lite", 1000, 1000)
        tracker.print_summary()
        captured = capsys.readouterr()
        # It should NOT print the "Visual QC" header because it's not in the summary dict
        assert "Visual QC" not in captured.out
