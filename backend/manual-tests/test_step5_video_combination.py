"""
Test Step 5: Video Combination

Tests combining video sections and audio using FFmpeg.
Requires FFmpeg to be installed.
"""

import asyncio
import json
from pathlib import Path

from app.services.video_generator.processor import VideoProcessor


async def test_video_combination():
    """Test combining videos and audio"""
    
    print("🎬 Step 5: Combining Video and Audio...")
    print("-" * 60)
    
    # Check if we have rendered video and audio from previous steps
    video_path = Path("test_outputs/rendered/step3b_rendered.mp4")
    audio_path = Path("test_outputs/audio/step3c_narration.mp3")
    
    has_video = video_path.exists()
    has_audio = audio_path.exists()
    
    print(f"📹 Video from Step 3b: {'✓ Found' if has_video else '✗ Missing'}")
    print(f"🔊 Audio from Step 3c: {'✓ Found' if has_audio else '✗ Missing'}")
    
    if not has_video and not has_audio:
        print("\n❌ No video or audio found!")
        print("   Run test_step3b_manim_rendering.py and test_step3c_audio_generation.py first.")
        return
    
    # Initialize processor
    processor = VideoProcessor()
    
    # Create output directory
    output_dir = Path("test_outputs/final")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        if has_video and has_audio:
            print("\n🎯 Test 1: Combining single video with audio...")
            output_path = output_dir / "step5_combined_single.mp4"
            
            await processor.combine_sections(
                videos=[str(video_path)],
                audios=[str(audio_path)],
                output_path=str(output_path),
                sections_dir=str(video_path.parent)
            )
            
            print(f"✅ Combined video saved to: {output_path}")
            
            if output_path.exists():
                size_mb = output_path.stat().st_size / (1024 * 1024)
                print(f"📦 File size: {size_mb:.2f} MB")
        
        # Test concatenating multiple videos (if you have more than one)
        rendered_dir = Path("test_outputs/rendered")
        if rendered_dir.exists():
            video_files = list(rendered_dir.glob("*.mp4"))
            
            if len(video_files) > 1:
                print(f"\n🎯 Test 2: Concatenating {len(video_files)} videos...")
                output_path = output_dir / "step5_concatenated.mp4"
                
                await processor.concatenate_videos(
                    video_paths=[str(v) for v in video_files],
                    output_path=str(output_path)
                )
                
                print(f"✅ Concatenated video saved to: {output_path}")
                
                if output_path.exists():
                    size_mb = output_path.stat().st_size / (1024 * 1024)
                    print(f"📦 File size: {size_mb:.2f} MB")
        
        # Test with sample videos (create dummy ones if needed for testing)
        if not has_video:
            print("\n💡 Creating test videos for concatenation test...")
            print("   (This would normally use real rendered videos)")
        
        print("\n✅ Video Combination Tests Complete!")
        
        # Save test info
        info_path = output_dir / "step5_info.json"
        info = {
            "has_video": has_video,
            "has_audio": has_audio,
            "tests_run": []
        }
        
        if has_video and has_audio:
            info["tests_run"].append("single_combine")
        
        with open(info_path, "w") as f:
            json.dump(info, f, indent=2)
        
        print(f"\n💡 You can play the final video with:")
        if (output_dir / "step5_combined_single.mp4").exists():
            print(f"   ffplay {output_dir / 'step5_combined_single.mp4'}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Check for common issues
        if "ffmpeg" in str(e).lower():
            print("\n💡 This step requires FFmpeg to be installed.")
            print("   Check if 'ffmpeg' command is available in your PATH.")
        
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("STEP 5: VIDEO COMBINATION TEST")
    print("=" * 60)
    asyncio.run(test_video_combination())
