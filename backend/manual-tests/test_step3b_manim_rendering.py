"""
Test Step 3b: Manim Code Rendering

Tests rendering Manim code to video.
Requires Manim to be installed.
"""

import asyncio
import json
from pathlib import Path

from app.services.pipeline.animation.generation import ManimGenerator


async def test_manim_rendering():
    """Test rendering Manim code to video"""
    
    print("🎥 Step 3b: Rendering Manim Code...")
    print("-" * 60)
    
    # Check if we have generated code from Step 3a
    code_path = Path("test_outputs/step3a_section_0.py")
    
    if not code_path.exists():
        # Try looking for any generated code
        test_outputs = Path("test_outputs")
        if test_outputs.exists():
            code_files = list(test_outputs.glob("step3a_*.py"))
            if code_files:
                code_path = code_files[0]
                print(f"📂 Found code file: {code_path}")
            else:
                print("❌ No Manim code found! Run test_step3a_manim_generation.py first.")
                return
        else:
            print("❌ No test_outputs directory found! Run previous steps first.")
            return
    
    # Read the code
    with open(code_path, "r", encoding="utf-8") as f:
        manim_code = f.read()
    
    print(f"📄 Code file: {code_path.name}")
    print(f"📏 Code length: {len(manim_code)} chars")
    
    # Initialize generator
    generator = ManimGenerator()
    
    # Create output directory
    output_dir = Path("test_outputs/rendered")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_path = output_dir / "step3b_rendered.mp4"
    
    try:
        print("\n🎬 Starting Manim rendering...")
        print("⏳ This may take 30-90 seconds depending on complexity...")
        
        # Render the code
        success = await generator.render_manim_code(
            code=manim_code,
            output_path=str(output_path),
            section_id="test_section"
        )
        
        if success:
            print("\n✅ Rendering Complete!")
            print(f"🎥 Video saved to: {output_path}")
            
            # Check file size
            if output_path.exists():
                size_mb = output_path.stat().st_size / (1024 * 1024)
                print(f"📦 File size: {size_mb:.2f} MB")
            
            # Save render info
            info_path = output_dir / "step3b_info.json"
            info = {
                "code_file": str(code_path),
                "output_video": str(output_path),
                "success": True
            }
            with open(info_path, "w") as f:
                json.dump(info, f, indent=2)
            
            print(f"\n💡 You can play the video with:")
            print(f"   ffplay {output_path}")
            print(f"   or open it in your video player")
            
        else:
            print("\n❌ Rendering failed!")
            print("Check the Manim logs above for error details.")
        
        return success
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("STEP 3b: MANIM RENDERING TEST")
    print("=" * 60)
    asyncio.run(test_manim_rendering())
