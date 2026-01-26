"""
Test Step 3c: Audio Generation (TTS)

Tests generating audio narration from text.
Requires Google Cloud TTS credentials.
"""

import asyncio
import json
from pathlib import Path

from app.services.tts_engine import TTSEngine


async def test_audio_generation():
    """Test TTS audio generation"""
    
    print("🔊 Step 3c: Generating Audio (TTS)...")
    print("-" * 60)
    
    # Check if we have a script from Step 2
    script_path = Path("test_outputs/step2_script.json")
    
    if script_path.exists():
        print("📂 Loading script from Step 2 test...")
        with open(script_path, "r", encoding="utf-8") as f:
            script = json.load(f)
        sections = script.get("sections", [])
    else:
        print("⚠️  No script found. Using sample text...")
        sections = [{
            "section_id": "test_section_1",
            "title": "Test Section",
            "narration": "The Pythagorean theorem states that in a right triangle, the square of the hypotenuse equals the sum of squares of the other two sides. This is one of the most fundamental theorems in mathematics."
        }]
    
    if not sections:
        print("❌ No sections found to process!")
        return
    
    # Test first section
    section = sections[0]
    narration = section.get("narration", "")
    
    print(f"\n📝 Section: {section.get('title', 'N/A')}")
    print(f"📏 Narration length: {len(narration)} chars")
    print(f"📄 Preview: {narration[:100]}...")
    
    # Initialize TTS engine
    engine = TTSEngine()
    
    # Create output directory
    output_dir = Path("test_outputs/audio")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = output_dir / "step3c_narration.mp3"
    
    try:
        # Test different voices if you want
        voice_options = [
            "en-US-Neural2-J",  # Male
            "en-US-Neural2-F",  # Female
            "en-US-Neural2-A",  # Another option
        ]
        
        voice = voice_options[0]  # Default
        print(f"\n🎤 Using voice: {voice}")
        print("⏳ Generating audio...")
        
        # Generate audio
        result = await engine.synthesize(
            text=narration,
            output_path=str(output_path),
            voice=voice,
            language="en"
        )
        
        print("\n✅ Audio Generation Complete!")
        print(f"🔊 Audio saved to: {output_path}")
        
        # Check file size
        if output_path.exists():
            size_kb = output_path.stat().st_size / 1024
            print(f"📦 File size: {size_kb:.2f} KB")
        
        # Save generation info
        info_path = output_dir / "step3c_info.json"
        info = {
            "narration_length": len(narration),
            "voice": voice,
            "output_path": str(output_path),
            "duration": result.get("duration", "unknown")
        }
        with open(info_path, "w") as f:
            json.dump(info, f, indent=2)
        
        print(f"\n💡 You can play the audio with:")
        print(f"   ffplay {output_path}")
        print(f"   or open it in your audio player")
        
        print(f"\n🎵 Audio Info:")
        if result.get("duration"):
            print(f"  - Duration: {result['duration']:.2f} seconds")
        
        return result
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Check for common issues
        if "credentials" in str(e).lower() or "authentication" in str(e).lower():
            print("\n💡 TTS requires Google Cloud credentials.")
            print("   Make sure service-account-key.json is configured correctly.")
        
        return None


if __name__ == "__main__":
    print("=" * 60)
    print("STEP 3c: AUDIO GENERATION TEST")
    print("=" * 60)
    asyncio.run(test_audio_generation())
