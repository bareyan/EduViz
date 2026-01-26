"""
Cost tracking for Gemini API usage
"""

from typing import Dict, Any

# Gemini pricing (per 1M tokens) - as of Jan 2026
# See: https://ai.google.dev/pricing
PRICING = {
    "gemini-3-pro-preview": {
        "input": 2.0,    # $2.00 per 1M input tokens (<=200K context)
        "output": 12.0   # $12.00 per 1M output tokens (<=200K context)
    },
    "gemini-3-flash-preview": {
        "input": 0.5,   # $0.5 per 1M input tokens
        "output": 3    # $3 per 1M output tokens
    },
    "gemini-flash-lite-latest": {
        "input": 0.075,  # $0.075 per 1M input tokens (similar to 2.0-flash)
        "output": 0.30,  # $0.30 per 1M output tokens
    },
    "gemini-2.0-flash-lite": {
        "input": 0.075,  # $0.075 per 1M input tokens (video converted to tokens)
        "output": 0.30,  # $0.30 per 1M output tokens
    },
    "gemini-2.5-flash": {
        "input": 0.15,
        "output": 0.60
    }
}


class CostTracker:
    """Tracks token usage and costs for Gemini API calls"""

    def __init__(self):
        self.token_usage = {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_cost": 0.0,
            "by_model": {}
        }

    def track_usage(self, response, model_name: str):
        """Track token usage and calculate cost from Gemini response
        
        Args:
            response: Gemini API response object
            model_name: Name of the model used
        """
        try:
            # Handle None response
            if not response:
                return

            # Extract usage metadata from response
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                usage = response.usage_metadata
                input_tokens = getattr(usage, 'prompt_token_count', 0) or 0
                output_tokens = getattr(usage, 'candidates_token_count', 0) or 0
            else:
                # Fallback for different response formats
                input_tokens = 0
                output_tokens = 0

            # Update totals
            self.token_usage["input_tokens"] += input_tokens
            self.token_usage["output_tokens"] += output_tokens

            # Track by model
            if model_name not in self.token_usage["by_model"]:
                self.token_usage["by_model"][model_name] = {
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost": 0.0
                }

            self.token_usage["by_model"][model_name]["input_tokens"] += input_tokens
            self.token_usage["by_model"][model_name]["output_tokens"] += output_tokens

            # Calculate cost for this call
            if model_name in PRICING:
                pricing = PRICING[model_name]
                input_cost = (input_tokens / 1_000_000) * pricing["input"]
                output_cost = (output_tokens / 1_000_000) * pricing["output"]
                call_cost = input_cost + output_cost

                self.token_usage["by_model"][model_name]["cost"] += call_cost
                self.token_usage["total_cost"] += call_cost

        except Exception as e:
            print(f"[CostTracker] Warning: Could not track token usage: {e}")

    def get_summary(self, visual_qc=None) -> Dict[str, Any]:
        """Get a summary of token usage and costs
        
        Args:
            visual_qc: Optional VisualQualityController for QC stats
        
        Returns:
            Dict with token counts, costs, and breakdown by model
        """
        summary = {
            "total_input_tokens": self.token_usage["input_tokens"],
            "total_output_tokens": self.token_usage["output_tokens"],
            "total_tokens": self.token_usage["input_tokens"] + self.token_usage["output_tokens"],
            "total_cost_usd": round(self.token_usage["total_cost"], 4),
            "by_model": {
                model: {
                    "input_tokens": data["input_tokens"],
                    "output_tokens": data["output_tokens"],
                    "total_tokens": data["input_tokens"] + data["output_tokens"],
                    "cost_usd": round(data["cost"], 4)
                }
                for model, data in self.token_usage["by_model"].items()
            }
        }

        # Add Visual QC stats if available
        if visual_qc:
            qc_stats = visual_qc.get_usage_stats()
            summary["visual_qc"] = qc_stats
            # Add QC cost to total (convert to same precision)
            summary["total_cost_usd"] = round(summary["total_cost_usd"] + qc_stats["total_cost_usd"], 4)

        return summary

    def print_summary(self, visual_qc=None):
        """Print a formatted cost summary to console"""
        summary = self.get_summary(visual_qc)

        print("\n" + "=" * 60)
        print("💰 GEMINI API COST SUMMARY")
        print("=" * 60)
        print(f"Total Input Tokens:  {summary['total_input_tokens']:,}")
        print(f"Total Output Tokens: {summary['total_output_tokens']:,}")
        print(f"Total Tokens:        {summary['total_tokens']:,}")

        if summary['by_model']:
            print("\nBreakdown by Model:")
            print("-" * 60)
            for model, data in summary['by_model'].items():
                print(f"\n{model}:")
                print(f"  Input:  {data['input_tokens']:,} tokens")
                print(f"  Output: {data['output_tokens']:,} tokens")
                print(f"  Cost:   ${data['cost_usd']:.4f}")

        # Display Visual QC stats
        if 'visual_qc' in summary:
            qc = summary['visual_qc']
            print("\nVisual QC (gemini-2.0-flash-lite - video mode):")
            print("-" * 60)
            print(f"  Input:  {qc['input_tokens']:,} tokens")
            print(f"  Output: {qc['output_tokens']:,} tokens")
            print(f"  Videos: {qc['videos_processed']} segments analyzed")
            print(f"  Cost:   ${qc['total_cost_usd']:.4f}")

        print(f"\n💵 Total Cost:        ${summary['total_cost_usd']:.4f}")
        print("=" * 60 + "\n")


def track_cost_safely(cost_tracker, response, model_name: str) -> None:
    """Safely track API usage cost without raising exceptions.
    
    This is a convenience wrapper that handles the common pattern:
        try:
            cost_tracker.track_usage(response, model)
        except Exception:
            pass
    
    Args:
        cost_tracker: CostTracker instance (or None)
        response: API response object
        model_name: Name of the model used
    """
    if cost_tracker is None:
        return
    try:
        cost_tracker.track_usage(response, model_name)
    except Exception:
        pass
