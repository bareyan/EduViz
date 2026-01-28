#!/usr/bin/env python3
"""
Test script for Gemini API cost tracking
"""

import asyncio

from app.services.pipeline.animation.generation import ManimGenerator


async def test_cost_tracking():
    """Test cost tracking for a simple code generation"""
    print("=" * 60)
    print("GEMINI API COST TRACKING TEST")
    print("=" * 60)

    try:
        generator = ManimGenerator()

        # Simple test section
        test_section = {
            "title": "Test Section",
            "narration": "This is a test narration for cost tracking.",
            "visual_description": "Display a simple title",
            "target_duration": 5
        }

        print("\nGenerating test Manim code...")
        code = await generator._generate_manim_code(test_section, 5.0)

        print(f"✓ Generated {len(code)} characters of code")

        # Print cost summary
        generator.print_cost_summary()

        # Get detailed breakdown
        summary = generator.get_cost_summary()
        print("\nDetailed breakdown:")
        print(f"  Total tokens: {summary['total_tokens']:,}")
        print(f"  Total cost: ${summary['total_cost_usd']:.4f}")

        if summary['by_model']:
            for model, data in summary['by_model'].items():
                print(f"\n  {model}:")
                print(f"    Input tokens:  {data['input_tokens']:,}")
                print(f"    Output tokens: {data['output_tokens']:,}")
                print(f"    Cost: ${data['cost_usd']:.4f}")

        print("\n" + "=" * 60)
        print("TEST COMPLETE")
        print("=" * 60)

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_cost_tracking())
