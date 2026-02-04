"""
Test Animation Generation for Production Content: The Adjoint Trick

This script tests the full animation pipeline (generation + rendering) with 
real production script to verify it can handle complex, educational content.
"""

import asyncio
import sys
import json
from pathlib import Path
import tempfile
import shutil

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Load environment variables from .env
import app.config  # This triggers load_dotenv()

from app.services.pipeline.animation.generation import ManimGenerator


async def main():
    print("=" * 60)
    print("🎬 Production Animation Test: The Adjoint Trick")
    print("=" * 60)
    
    # The first section from the production script
    section = {
        "id": "intro_the_problem",
        "index": 0,
        "title": "The Efficiency Problem",
        "narration": "Imagine you are training a massive neural network with billions of parameters. To improve it, you need the gradient—the direction that minimizes error. If you use the standard finite difference method, you would have to run your model billions of times just to get one update. That is practically impossible! This is where the Adjoint Trick comes in. It is a mathematical superpower used in machine learning, physics, and engineering to calculate gradients with incredible efficiency. Whether you call it backpropagation or reverse-mode automatic differentiation, the core idea is the same: finding how every single input affects the output, all in one go. It is the reason modern AI is even possible.",
        "narration_segments": [
            {
                "text": "Imagine you are training a massive neural network with billions of parameters.",
                "estimated_duration": 6.24,
                "start_time": 0,
                "duration": 6.24,
                "segment_index": 0
            },
            {
                "text": "To improve it, you need the gradient, the direction that minimizes error.",
                "estimated_duration": 5.84,
                "start_time": 6.24,
                "duration": 5.84,
                "segment_index": 1
            },
            {
                "text": "If you use the standard finite difference method, you would have to run your model billions of times just to get one update.",
                "estimated_duration": 9.92,
                "start_time": 12.08,
                "duration": 9.92,
                "segment_index": 2
            },
            {
                "text": "That is practically impossible! This is where the Adjoint Trick comes in.",
                "estimated_duration": 5.84,
                "start_time": 22.0,
                "duration": 5.84,
                "segment_index": 3
            },
            {
                "text": "It is a mathematical superpower used in machine learning, physics, and engineering to calculate gradients with incredible efficiency.",
                "estimated_duration": 10.64,
                "start_time": 27.84,
                "duration": 10.64,
                "segment_index": 4
            },
            {
                "text": "Whether you call it backpropagation or reverse-mode automatic differentiation, the core idea is the same: finding how every single input affects the output, all in one go.",
                "estimated_duration": 13.68,
                "start_time": 38.48,
                "duration": 13.68,
                "segment_index": 5
            },
            {
                "text": "It is the reason modern AI is even possible.",
                "estimated_duration": 3.52,
                "start_time": 52.16,
                "duration": 3.52,
                "segment_index": 6
            }
        ],
        "duration_seconds": 56,
        "visual_type": "animated"
    }
    
    print(f"\n📝 Section: {section['title']}")
    print(f"   Duration: {section['duration_seconds']}s")
    print(f"   Segments: {len(section['narration_segments'])}")
    print(f"\n⏳ Running full animation pipeline (code + rendering)...")
    print(f"   This may take 2-3 minutes...\n")
    
    # Create temporary output directory
    output_dir = Path(tempfile.mkdtemp(prefix="adjoint_test_"))
    print(f"📁 Output directory: {output_dir}\n")
    
    # Initialize ManimGenerator (full pipeline)
    generator = ManimGenerator(pipeline_name="adjoint_test")
    
    try:
        # Generate animation (code + render)
        result = await generator.generate_animation(
            section=section,
            output_dir=str(output_dir),
            section_index=0,
            audio_duration=section['duration_seconds'],
            style="3b1b"
        )
        
        print("\n" + "=" * 60)
        print("✅ Animation generated and rendered successfully!")
        print("=" * 60)
        
        video_path = Path(result['video_path'])
        code_path = Path(result['manim_code_path'])
        
        print(f"\n🎥 Video: {video_path}")
        print(f"   Size: {video_path.stat().st_size / 1024:.1f} KB")
        print(f"   Exists: {video_path.exists()}")
        
        print(f"\n📄 Code: {code_path}")
        print(f"   Lines: {len(result['manim_code'].splitlines())}")
        print(f"   Size: {len(result['manim_code'])} chars")
        
        print(f"\n📊 Validation: {result['validation_results']['valid']}")
        
        # Show first 40 lines of code
        print("\n" + "=" * 60)
        print("📄 Generated Code (first 40 lines):")
        print("=" * 60)
        lines = result['manim_code'].split('\n')
        for i, line in enumerate(lines[:40], 1):
            print(f"{i:3}: {line}")
        
        if len(lines) > 40:
            print(f"\n... ({len(lines) - 40} more lines)")
        
        # Keep output directory and show path
        print("\n" + "=" * 60)
        print("� Output saved to:")
        print("=" * 60)
        print(f"   {output_dir}")
        print(f"\n   Video: {video_path.name}")
        print(f"   Code:  {code_path.name}")
        
    except Exception as e:
        print(f"\n❌ FAILED: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        print("\n💰 Cost Summary:\n")
        generator.print_cost_summary()
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
