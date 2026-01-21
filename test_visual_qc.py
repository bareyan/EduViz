#!/usr/bin/env python3
"""
Test script for Visual Quality Control system
Tests the basic functionality without requiring full pipeline
"""

import asyncio
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend" / "app"))

try:
    from services.visual_qc import VisualQualityController, check_section_video
except ImportError as e:
    print(f"Error importing visual_qc: {e}")
    print("Make sure google-genai and Pillow are installed:")
    print("  pip install google-genai Pillow")
    sys.exit(1)

# Default model for testing
TEST_MODEL = "gemini-2.0-flash-lite"


async def test_model_availability():
    """Test if Gemini API is accessible"""
    print("=" * 60)
    print("TEST 1: API Availability Check")
    print("=" * 60)
    
    if not os.getenv("GEMINI_API_KEY"):
        print("✗ GEMINI_API_KEY environment variable not set")
        return
    
    print(f"\nTesting Gemini API with model: {TEST_MODEL}...")
    try:
        qc = VisualQualityController(model=TEST_MODEL)
        is_available = await qc.check_model_available()
        
        if is_available:
            print(f"✓ Gemini API is accessible")
        else:
            print(f"✗ Gemini API not available")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    print()


async def test_frame_extraction():
    """Test frame extraction from a video"""
    print("=" * 60)
    print("TEST 2: Frame Extraction")
    print("=" * 60)
    
    # Find any existing video in outputs
    outputs_dir = Path(__file__).parent / "backend" / "outputs"
    
    video_files = list(outputs_dir.glob("*/sections/*/section_*.mp4"))
    
    if not video_files:
        print("✗ No test videos found in outputs directory")
        print("  Generate a video first, then run this test")
        return
    
    test_video = str(video_files[0])
    print(f"\nUsing test video: {test_video}")
    
    try:
        qc = VisualQualityController(model=TEST_MODEL)
        
        # Extract frames
        frame_paths, timestamps = qc.extract_keyframes(test_video, num_frames=3)
        
        if frame_paths:
            print(f"✓ Extracted {len(frame_paths)} frames")
            for i, (frame, ts) in enumerate(zip(frame_paths, timestamps)):
                print(f"  Frame {i} at {ts}s: {frame}")
            
            # Cleanup
            qc.cleanup_frames(frame_paths)
            print("✓ Cleaned up frames")
        else:
            print("✗ Failed to extract frames")
    
    except Exception as e:
        print(f"✗ Error: {e}")
    
    print()


async def test_full_qc():
    """Test full QC workflow on a video"""
    print("=" * 60)
    print("TEST 3: Full Quality Check")
    print("=" * 60)
    
    # Find a test video
    outputs_dir = Path(__file__).parent / "backend" / "outputs"
    video_files = list(outputs_dir.glob("*/sections/*/section_*.mp4"))
    
    if not video_files:
        print("✗ No test videos found")
        return
    
    test_video = str(video_files[0])
    print(f"\nAnalyzing video: {test_video}")
    
    section_info = {
        "title": "Test Section",
        "narration": "This is a test narration for quality control",
        "visual_description": "Shows mathematical equations and text"
    }
    
    try:
        # Check if API is available first
        qc = VisualQualityController(model=TEST_MODEL)
        
        if not await qc.check_model_available():
            print(f"✗ Gemini API not available")
            return
        
        print("\nRunning quality check...")
        result = await check_section_video(
            test_video,
            section_info,
            model=TEST_MODEL
        )
        
        print(f"\n✓ Analysis complete")
        print(f"  Status: {result['status']}")
        
        if result.get('error_report'):
            print(f"  Errors found:")
            print(f"  {result['error_report']}")
        else:
            print("  No issues found!")
    
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
    
    print()


async def test_fix_generation():
    """Test fix generation for a simple issue"""
    print("=" * 60)
    print("TEST 4: Fix Generation")
    print("=" * 60)
    
    # Sample problematic code with text overlap
    bad_code = '''from manim import *

class TestSection(Scene):
    def construct(self):
        title = Text("My Title", font_size=72)
        subtitle = Text("Subtitle", font_size=60)
        
        # PROBLEM: Both at the same position - will overlap
        self.play(Write(title))
        self.play(Write(subtitle))
        self.wait(2)
'''
    
    # Simulated error report
    error_report = """At 1.5s: Title text overlaps with subtitle text
At 3.0s: Both texts at same position causing readability issues"""
    
    try:
        qc = VisualQualityController(model=TEST_MODEL)
        
        if not await qc.check_model_available():
            print(f"✗ Gemini API not available")
            return
        
        print("\nGenerating fix for overlapping text...")
        fixed_code = await qc.generate_fix(bad_code, error_report)
        
        if fixed_code:
            print("✓ Fix generated successfully")
            print("\nFixed code snippet:")
            print("-" * 40)
            lines = fixed_code.split('\n')
            # Show relevant part
            for i, line in enumerate(lines[:20], 1):
                print(f"{i:2}: {line}")
            if len(lines) > 20:
                print(f"... ({len(lines) - 20} more lines)")
        else:
            print("✗ Failed to generate fix")
    
    except Exception as e:
        print(f"✗ Error: {e}")
    
    print()


async def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("VISUAL QUALITY CONTROL - TEST SUITE")
    print("=" * 60 + "\n")
    
    # Test 1: Check if models are available
    await test_model_availability()
    
    # Test 2: Frame extraction
    await test_frame_extraction()
    
    # Test 3: Full QC workflow
    await test_full_qc()
    
    # Test 4: Fix generation
    await test_fix_generation()
    
    print("=" * 60)
    print("TEST SUITE COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"\nTest failed with error: {e}")
        import traceback
        traceback.print_exc()
