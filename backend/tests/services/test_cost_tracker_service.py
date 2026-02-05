"""
Tests for services/infrastructure/llm/cost_tracker module

Comprehensive tests for the CostTracker class including token tracking,
cost calculation, and summarization.
"""

from unittest.mock import MagicMock

from app.services.infrastructure.llm.cost_tracker import (
    CostTracker,
    track_cost_safely,
    PRICING,
)


class TestCostTrackerInit:
    """Test suite for CostTracker initialization"""

    def test_initial_state(self):
        """Test CostTracker starts with zero values"""
        tracker = CostTracker()
        
        assert tracker.token_usage["input_tokens"] == 0
        assert tracker.token_usage["output_tokens"] == 0
        assert tracker.token_usage["total_cost"] == 0.0
        assert tracker.token_usage["by_model"] == {}


class TestCostTrackerTrackUsage:
    """Test suite for CostTracker.track_usage method"""

    def test_track_usage_with_valid_response(self):
        """Test tracking usage from a valid API response"""
        tracker = CostTracker()
        
        # Create mock response with usage metadata
        mock_response = MagicMock()
        mock_response.usage_metadata = MagicMock()
        mock_response.usage_metadata.prompt_token_count = 100
        mock_response.usage_metadata.candidates_token_count = 50
        
        tracker.track_usage(mock_response, "gemini-3-flash-preview")
        
        assert tracker.token_usage["input_tokens"] == 100
        assert tracker.token_usage["output_tokens"] == 50
        assert tracker.token_usage["total_cost"] > 0

    def test_track_usage_accumulates(self):
        """Test that multiple track_usage calls accumulate"""
        tracker = CostTracker()
        
        mock_response1 = MagicMock()
        mock_response1.usage_metadata = MagicMock()
        mock_response1.usage_metadata.prompt_token_count = 100
        mock_response1.usage_metadata.candidates_token_count = 50
        
        mock_response2 = MagicMock()
        mock_response2.usage_metadata = MagicMock()
        mock_response2.usage_metadata.prompt_token_count = 200
        mock_response2.usage_metadata.candidates_token_count = 100
        
        tracker.track_usage(mock_response1, "gemini-3-flash-preview")
        tracker.track_usage(mock_response2, "gemini-3-flash-preview")
        
        assert tracker.token_usage["input_tokens"] == 300
        assert tracker.token_usage["output_tokens"] == 150

    def test_track_usage_none_response(self):
        """Test tracking with None response doesn't crash"""
        tracker = CostTracker()
        
        # Should not raise
        tracker.track_usage(None, "gemini-3-flash-preview")
        
        assert tracker.token_usage["input_tokens"] == 0
        assert tracker.token_usage["output_tokens"] == 0

    def test_track_usage_no_usage_metadata(self):
        """Test tracking response without usage_metadata"""
        tracker = CostTracker()
        
        mock_response = MagicMock()
        mock_response.usage_metadata = None
        
        tracker.track_usage(mock_response, "gemini-3-flash-preview")
        
        assert tracker.token_usage["input_tokens"] == 0
        assert tracker.token_usage["output_tokens"] == 0

    def test_track_usage_by_model(self):
        """Test that usage is tracked per model"""
        tracker = CostTracker()
        
        mock_response1 = MagicMock()
        mock_response1.usage_metadata = MagicMock()
        mock_response1.usage_metadata.prompt_token_count = 100
        mock_response1.usage_metadata.candidates_token_count = 50
        
        mock_response2 = MagicMock()
        mock_response2.usage_metadata = MagicMock()
        mock_response2.usage_metadata.prompt_token_count = 200
        mock_response2.usage_metadata.candidates_token_count = 100
        
        tracker.track_usage(mock_response1, "gemini-3-flash-preview")
        tracker.track_usage(mock_response2, "gemini-2.5-flash")
        
        assert "gemini-3-flash-preview" in tracker.token_usage["by_model"]
        assert "gemini-2.5-flash" in tracker.token_usage["by_model"]
        
        flash_preview = tracker.token_usage["by_model"]["gemini-3-flash-preview"]
        assert flash_preview["input_tokens"] == 100
        assert flash_preview["output_tokens"] == 50

    def test_track_usage_unknown_model(self):
        """Test tracking with unknown model (no pricing)"""
        tracker = CostTracker()
        
        mock_response = MagicMock()
        mock_response.usage_metadata = MagicMock()
        mock_response.usage_metadata.prompt_token_count = 100
        mock_response.usage_metadata.candidates_token_count = 50
        
        tracker.track_usage(mock_response, "unknown-model")
        
        # Tokens should still be tracked
        assert tracker.token_usage["input_tokens"] == 100
        assert tracker.token_usage["output_tokens"] == 50
        # But cost should be zero (no pricing available)
        assert tracker.token_usage["total_cost"] == 0.0


class TestCostTrackerTrackRequest:
    """Test suite for CostTracker.track_request method"""

    def test_track_request_basic(self):
        """Test track_request with direct token counts"""
        tracker = CostTracker()
        
        tracker.track_request("gemini-3-flash-preview", input_tokens=500, output_tokens=200)
        
        assert tracker.token_usage["input_tokens"] == 500
        assert tracker.token_usage["output_tokens"] == 200
        assert tracker.token_usage["total_cost"] > 0

    def test_track_request_accumulates(self):
        """Test that track_request accumulates correctly"""
        tracker = CostTracker()
        
        tracker.track_request("gemini-3-flash-preview", input_tokens=100, output_tokens=50)
        tracker.track_request("gemini-3-flash-preview", input_tokens=100, output_tokens=50)
        
        assert tracker.token_usage["input_tokens"] == 200
        assert tracker.token_usage["output_tokens"] == 100

    def test_track_request_cost_calculation(self):
        """Test that costs are calculated correctly"""
        tracker = CostTracker()
        
        # 1M tokens at gemini-3-flash-preview pricing
        # Input: $0.5 per 1M, Output: $3 per 1M
        tracker.track_request("gemini-3-flash-preview", input_tokens=1_000_000, output_tokens=1_000_000)
        
        expected_input_cost = 0.5  # $0.5 for 1M input tokens
        expected_output_cost = 3.0  # $3 for 1M output tokens
        expected_total = expected_input_cost + expected_output_cost
        
        assert abs(tracker.token_usage["total_cost"] - expected_total) < 0.01

    def test_track_request_zero_tokens(self):
        """Test track_request with zero tokens"""
        tracker = CostTracker()
        
        tracker.track_request("gemini-3-flash-preview", input_tokens=0, output_tokens=0)
        
        assert tracker.token_usage["input_tokens"] == 0
        assert tracker.token_usage["output_tokens"] == 0
        assert tracker.token_usage["total_cost"] == 0.0


class TestCostTrackerGetSummary:
    """Test suite for CostTracker.get_summary method"""

    def test_get_summary_empty(self):
        """Test summary with no tracked usage"""
        tracker = CostTracker()
        
        summary = tracker.get_summary()
        
        assert summary["total_input_tokens"] == 0
        assert summary["total_output_tokens"] == 0
        assert summary["total_tokens"] == 0
        assert summary["total_cost_usd"] == 0.0
        assert summary["by_model"] == {}

    def test_get_summary_with_data(self):
        """Test summary with tracked usage"""
        tracker = CostTracker()
        
        tracker.track_request("gemini-3-flash-preview", input_tokens=1000, output_tokens=500)
        
        summary = tracker.get_summary()
        
        assert summary["total_input_tokens"] == 1000
        assert summary["total_output_tokens"] == 500
        assert summary["total_tokens"] == 1500
        assert summary["total_cost_usd"] > 0
        assert "gemini-3-flash-preview" in summary["by_model"]

    def test_get_summary_multiple_models(self):
        """Test summary with multiple models"""
        tracker = CostTracker()
        
        tracker.track_request("gemini-3-flash-preview", input_tokens=1000, output_tokens=500)
        tracker.track_request("gemini-2.5-flash", input_tokens=2000, output_tokens=1000)
        
        summary = tracker.get_summary()
        
        assert summary["total_input_tokens"] == 3000
        assert summary["total_output_tokens"] == 1500
        assert len(summary["by_model"]) == 2

    def test_get_summary_cost_rounding(self):
        """Test that costs are properly rounded"""
        tracker = CostTracker()
        
        tracker.track_request("gemini-3-flash-preview", input_tokens=1, output_tokens=1)
        
        summary = tracker.get_summary()
        
        # Cost should be rounded to 4 decimal places
        cost_str = str(summary["total_cost_usd"])
        if "." in cost_str:
            decimal_places = len(cost_str.split(".")[1])
            assert decimal_places <= 4


class TestCostTrackerPrintSummary:
    """Test suite for CostTracker.print_summary method"""

    def test_print_summary_contains_totals(self, capsys):
        """Test that print_summary outputs total information"""
        tracker = CostTracker()
        
        tracker.track_request("gemini-3-flash-preview", input_tokens=1000, output_tokens=500)
        tracker.print_summary()
        
        captured = capsys.readouterr()
        
        assert "GEMINI API COST SUMMARY" in captured.out
        assert "Input Tokens" in captured.out
        assert "Output Tokens" in captured.out
        assert "Total Cost" in captured.out

    def test_print_summary_empty(self, capsys):
        """Test print_summary with no tracked usage"""
        tracker = CostTracker()
        
        tracker.print_summary()
        
        captured = capsys.readouterr()
        
        assert "Total Tokens" in captured.out or "0" in captured.out


class TestTrackCostSafely:
    """Test suite for track_cost_safely helper function"""

    def test_track_cost_safely_with_valid_tracker(self):
        """Test track_cost_safely with valid inputs"""
        tracker = CostTracker()
        
        mock_response = MagicMock()
        mock_response.usage_metadata = MagicMock()
        mock_response.usage_metadata.prompt_token_count = 100
        mock_response.usage_metadata.candidates_token_count = 50
        
        # Should not raise
        track_cost_safely(tracker, mock_response, "gemini-3-flash-preview")
        
        assert tracker.token_usage["input_tokens"] == 100

    def test_track_cost_safely_with_none_tracker(self):
        """Test track_cost_safely with None tracker doesn't crash"""
        mock_response = MagicMock()
        
        # Should not raise
        track_cost_safely(None, mock_response, "gemini-3-flash-preview")

    def test_track_cost_safely_with_exception(self):
        """Test track_cost_safely swallows exceptions"""
        tracker = CostTracker()
        
        # Create a response that will cause an exception
        mock_response = MagicMock()
        mock_response.usage_metadata = MagicMock()
        mock_response.usage_metadata.prompt_token_count = "not a number"  # Will cause issue
        
        # Should not raise even with bad data
        track_cost_safely(tracker, mock_response, "gemini-3-flash-preview")


class TestPricing:
    """Test suite for PRICING constants"""

    def test_pricing_is_dict(self):
        """Test PRICING is a dictionary"""
        assert isinstance(PRICING, dict)

    def test_pricing_has_models(self):
        """Test PRICING has expected models"""
        expected_models = ["gemini-3-flash-preview", "gemini-2.5-flash"]
        
        for model in expected_models:
            assert model in PRICING, f"Missing pricing for {model}"

    def test_pricing_has_input_output(self):
        """Test each pricing entry has input and output"""
        for model, pricing in PRICING.items():
            assert "input" in pricing, f"Missing input pricing for {model}"
            assert "output" in pricing, f"Missing output pricing for {model}"

    def test_pricing_values_are_positive(self):
        """Test all pricing values are positive numbers"""
        for model, pricing in PRICING.items():
            assert pricing["input"] > 0, f"Input pricing for {model} should be positive"
            assert pricing["output"] > 0, f"Output pricing for {model} should be positive"

    def test_output_more_expensive_than_input(self):
        """Test that output tokens are more expensive (typical for LLMs)"""
        for model, pricing in PRICING.items():
            assert pricing["output"] >= pricing["input"], \
                f"Output should be >= input for {model}"
