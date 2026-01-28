"""
Test Agentic Manim Generation

Tests the full agentic tool-based Manim generation flow:
- Real section data
- Real tool calls (generate_manim_code, fix_manim_code)
- Real validation feedback
- Real iteration loop
"""

import asyncio
import json
import sys
from pathlib import Path

# Ensure app module is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.pipeline.animation.generation import ManimGenerator
from app.config.models import set_active_pipeline


async def test_agentic_generation():
    """Test full agentic Manim generation with real tool calls"""
    
    print("=" * 80)
    print("🤖 TESTING AGENTIC MANIM GENERATION")
    print("=" * 80)
    
    # Configure pipeline
    set_active_pipeline("default")
    
    # Initialize generator
    generator = ManimGenerator()
    
    print(f"\n✓ Generator initialized")
    print(f"  - GenerationHandler: {type(generator.generation_handler).__name__}")
    print(f"  - CorrectionHandler: {type(generator.correction_handler).__name__}")
    print(f"  - Max agentic iterations: {generator.generation_handler.MAX_ITERATIONS}")
    
    # Create realistic test section
    section = {
        "section_id": "test_pythagoras",
        "title": "Pythagorean Theorem",
        "narration": """The Pythagorean theorem is one of the most famous theorems in mathematics.
        It states that in a right triangle, the square of the length of the hypotenuse 
        equals the sum of the squares of the lengths of the other two sides. 
        This can be written as a squared plus b squared equals c squared.""",
        "tts_narration": "The Pythagorean theorem states that a² + b² = c²",
        "visual_description": "Show a right triangle with sides a, b, and hypotenuse c. Display the equation a² + b² = c².",
        "style": "3b1b",
        "language": "en",
        "animation_type": "equation",
        "audio_duration": 20.0,
        "segments": [
            {
                "tts_text": "The Pythagorean theorem states that",
                "duration": 3.0
            },
            {
                "tts_text": "in a right triangle",
                "duration": 2.0
            },
            {
                "tts_text": "a squared plus b squared equals c squared",
                "duration": 4.0
            }
        ]
    }
    
    print(f"\n📝 Test Section:")
    print(f"  - Title: {section['title']}")
    print(f"  - Duration: {section['audio_duration']}s")
    print(f"  - Animation type: {section['animation_type']}")
    print(f"  - Style: {section['style']}")
    print(f"  - Segments: {len(section['segments'])}")
    
    # Create output directory
    output_dir = Path("test_outputs/agentic_test")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n🚀 Starting agentic generation...")
    print("-" * 80)
    
    try:
        # Call the agentic generation
        code, visual_script = await generator._generate_manim_code(
            section=section,
            audio_duration=section['audio_duration'],
            output_dir=str(output_dir),
            section_index=0,
            reuse_visual_script=False
        )
        
        print("\n" + "=" * 80)
        print("✓ GENERATION COMPLETE")
        print("=" * 80)
        
        if code:
            print(f"\n📄 Generated Code ({len(code)} characters):")
            print("-" * 80)
            print(code[:500] + "..." if len(code) > 500 else code)
            print("-" * 80)
            
            # Save code
            code_file = output_dir / "generated_code.py"
            with open(code_file, "w", encoding="utf-8") as f:
                f.write(code)
            print(f"\n💾 Code saved to: {code_file}")
            
            # Validate the code
            validation = generator.validator.validate_code(code)
            print(f"\n🔍 Validation Result:")
            print(f"  - Valid: {validation['valid']}")
            if not validation['valid']:
                print(f"  - Error: {validation.get('error', 'Unknown')}")
            if validation.get('warnings'):
                print(f"  - Warnings: {validation['warnings']}")
        else:
            print("\n❌ No code generated")
        
        if visual_script:
            print(f"\n📋 Visual Script Generated:")
            script_file = output_dir / "visual_script.txt"
            with open(script_file, "w", encoding="utf-8") as f:
                f.write(str(visual_script))
            print(f"   Saved to: {script_file}")
        
        # Check cost tracking
        cost_summary = generator.get_cost_summary()
        print(f"\n💰 Cost Summary:")
        print(f"  - Total requests: {cost_summary.get('total_requests', 0)}")
        print(f"  - Total cost: ${cost_summary.get('total_cost_usd', 0):.4f}")
        print(f"  - Input tokens: {cost_summary.get('total_input_tokens', 0):,}")
        print(f"  - Output tokens: {cost_summary.get('total_output_tokens', 0):,}")
        
        print("\n" + "=" * 80)
        print("✓ TEST COMPLETE")
        print("=" * 80)
        
        return code
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_with_real_rendering():
    """Test generation AND rendering to verify code actually works"""
    
    print("\n" + "=" * 80)
    print("🎬 TESTING GENERATION + RENDERING")
    print("=" * 80)
    
    # First generate code
    code = await test_agentic_generation()
    
    if not code:
        print("\n❌ Generation failed, cannot test rendering")
        return
    
    print("\n" + "-" * 80)
    print("🎥 Now testing actual Manim rendering...")
    print("-" * 80)
    
    # Set up for rendering
    set_active_pipeline("default")
    generator = ManimGenerator()
    
    output_dir = Path("test_outputs/agentic_test/render")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    section = {
        "title": "Pythagorean Theorem",
        "audio_duration": 20.0,
        "style": "3b1b",
        "language": "en"
    }
    
    try:
        # Try to render
        result = await generator.generate_section_video(
            section=section,
            output_dir=str(output_dir),
            section_index=0,
            audio_duration=20.0,
            style="3b1b",
            language="en",
            clean_retry=0
        )
        
        if result and result.get("video_path"):
            print(f"\n✓ VIDEO RENDERED SUCCESSFULLY!")
            print(f"  - Video: {result['video_path']}")
            print(f"  - Code: {result['manim_code_path']}")
            print("\n🎉 Full pipeline working: generation → validation → rendering")
        else:
            print(f"\n⚠️  Rendering completed but no video produced")
            print(f"   This might indicate the code has runtime issues")
            
    except Exception as e:
        print(f"\n⚠️  Render error (this is expected for agentic validation test): {e}")
        print(f"   The code passed agentic validation but failed at render time")
        print(f"   This shows the difference between validation and actual execution")


async def test_correction_loop():
    """Test the correction tool handler specifically"""
    
    print("\n" + "=" * 80)
    print("🔧 TESTING CORRECTION TOOL HANDLER")
    print("=" * 80)
    
    set_active_pipeline("default")
    generator = ManimGenerator()
    
    # Code with a deliberate error
    bad_code = """
        title = Text("Test", font_size=36)
        self.play(Write(title))
        self.wait(-1)  # Negative wait - will fail
"""
    
    error_message = "ValueError: wait time must be positive"
    
    print("\n📝 Testing correction on code with error:")
    print(bad_code)
    print(f"\n❌ Error: {error_message}")
    
    print("\n🔧 Calling GenerationToolHandler.fix()...")
    
    try:
        result = await generator.correction_handler.fix(
            code=bad_code,
            error_message=error_message,
            section={"audio_duration": 10.0},
            attempt=0
        )
        
        print(f"\n📊 Correction Result:")
        print(f"  - Success: {result.success}")
        print(f"  - Iterations: {result.iterations}")
        
        if result.success and result.code:
            print(f"\n✓ Corrected Code:")
            print("-" * 80)
            print(result.code)
            print("-" * 80)
        else:
            print(f"\n❌ Correction failed: {result.error}")
        
        if result.feedback_history:
            print(f"\n📋 Feedback history:")
            for entry in result.feedback_history:
                print(f"   - {entry}")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import sys
    
    print("\n" + "=" * 80)
    print("AGENTIC MANIM GENERATION TEST SUITE")
    print("=" * 80)
    print("\nAvailable tests:")
    print("  1. test_agentic_generation() - Full agentic generation with tool calls")
    print("  2. test_with_real_rendering() - Generation + actual Manim rendering")
    print("  3. test_correction_loop() - Test correction tool handler")
    print("\n")
    
    if len(sys.argv) > 1:
        test_name = sys.argv[1]
        if test_name == "1":
            asyncio.run(test_agentic_generation())
        elif test_name == "2":
            asyncio.run(test_with_real_rendering())
        elif test_name == "3":
            asyncio.run(test_correction_loop())
        else:
            print(f"Unknown test: {test_name}")
    else:
        # Run all tests
        print("Running test 1: Agentic Generation")
        asyncio.run(test_agentic_generation())
        
        print("\n\nWould you like to run the full rendering test? (y/n)")
        response = input("> ").strip().lower()
        if response == 'y':
            asyncio.run(test_with_real_rendering())
        
        print("\n\nWould you like to test the correction handler? (y/n)")
        response = input("> ").strip().lower()
        if response == 'y':
            asyncio.run(test_correction_loop())
