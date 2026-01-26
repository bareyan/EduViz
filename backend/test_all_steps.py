"""
Run All Pipeline Steps in Sequence

This script runs all pipeline steps one after another,
allowing you to test the complete flow with breaks between steps.
"""

import asyncio
import sys
from pathlib import Path

# Import test functions
sys.path.insert(0, str(Path(__file__).parent))

from test_step2_script_generation import test_script_generation
from test_step3a_manim_generation import test_manim_generation
from test_step3b_manim_rendering import test_manim_rendering
from test_step3c_audio_generation import test_audio_generation
from test_step5_video_combination import test_video_combination


async def run_all_steps():
    """Run all pipeline steps sequentially"""
    
    print("\n" + "=" * 60)
    print("COMPLETE PIPELINE TEST")
    print("=" * 60)
    
    results = {}
    
    # Step 2: Script Generation
    print("\n\n")
    input("Press Enter to start Step 2 (Script Generation)...")
    results['step2'] = await test_script_generation()
    
    if not results['step2']:
        print("\n❌ Step 2 failed. Cannot continue.")
        return
    
    # Step 3a: Manim Code Generation
    print("\n\n")
    input("Press Enter to start Step 3a (Manim Code Generation)...")
    results['step3a'] = await test_manim_generation()
    
    if not results['step3a']:
        print("\n❌ Step 3a failed. Cannot continue.")
        return
    
    # Step 3b: Manim Rendering
    print("\n\n")
    input("Press Enter to start Step 3b (Manim Rendering)...")
    results['step3b'] = await test_manim_rendering()
    
    if not results['step3b']:
        print("\n⚠️  Step 3b failed. Continuing anyway...")
    
    # Step 3c: Audio Generation
    print("\n\n")
    input("Press Enter to start Step 3c (Audio Generation)...")
    results['step3c'] = await test_audio_generation()
    
    if not results['step3c']:
        print("\n⚠️  Step 3c failed. Continuing anyway...")
    
    # Step 5: Video Combination
    print("\n\n")
    input("Press Enter to start Step 5 (Video Combination)...")
    results['step5'] = await test_video_combination()
    
    # Summary
    print("\n\n" + "=" * 60)
    print("PIPELINE TEST SUMMARY")
    print("=" * 60)
    
    print(f"\nStep 2 (Script Generation):     {'✅ Success' if results['step2'] else '❌ Failed'}")
    print(f"Step 3a (Manim Code):            {'✅ Success' if results['step3a'] else '❌ Failed'}")
    print(f"Step 3b (Manim Rendering):       {'✅ Success' if results['step3b'] else '❌ Failed'}")
    print(f"Step 3c (Audio Generation):      {'✅ Success' if results['step3c'] else '❌ Failed'}")
    print(f"Step 5 (Video Combination):      {'✅ Success' if results['step5'] else '❌ Failed'}")
    
    print("\n📁 Check test_outputs/ directory for all generated files")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_all_steps())
