"""
Test Step 3a: Manim Code Generation

Tests generating Manim animation code from a script section.
"""

import asyncio
import json
from pathlib import Path

from app.services.pipeline.animation.generation import ManimGenerator
from app.config.models import set_active_pipeline


async def test_manim_generation():
    """Test Manim code generation from a script section"""
    
    # Configure pipeline
    set_active_pipeline("default")
    
    # Initialize generator
    generator = ManimGenerator()
    
    print("🎨 Step 3a: Generating Manim Code...")
    print("-" * 60)
    
    # Check if we have a script from Step 2
    script_path = Path("test_outputs/step2_script.json")
    
    if script_path.exists():
        print("📂 Loading script from Step 2 test...")
        with open(script_path, "r", encoding="utf-8") as f:
            script = json.load(f)
        sections = script.get("sections", [])
    else:
        print("⚠️  No script found. Using sample section...")
        # Sample section for testing
        sections = [{
            "section_id": "test_section_1",
            "title": "Introduction to Pythagorean Theorem",
            "narration": "The Pythagorean theorem states that in a right triangle, the square of the hypotenuse equals the sum of squares of the other two sides.",
            "visual_elements": [
                {
                    "type": "diagram",
                    "description": "Draw a right triangle with sides labeled a, b, and c (hypotenuse)"
                },
                {
                    "type": "equation",
                    "content": "a^2 + b^2 = c^2"
                }
            ],
            "estimated_duration": 15
        }]
    
    if not sections:
        print("❌ No sections found to process!")
        return
    
    # Test first section
    section = sections[0]
    section_id = section.get("section_id", "section_0")
    
    print(f"\n📝 Processing Section: {section.get('title', 'N/A')}")
    print(f"   Narration length: {len(section.get('narration', ''))} chars")
    print(f"   Visual elements: {len(section.get('visual_elements', []))}")
    
    try:
        # Generate Manim code
        result = await generator.generate_section(
            section=section,
            section_id=section_id
        )
        
        # Save results
        output_dir = Path("test_outputs")
        output_dir.mkdir(exist_ok=True)
        
        # Save generated code
        code_path = output_dir / f"step3a_{section_id}.py"
        with open(code_path, "w", encoding="utf-8") as f:
            f.write(result["code"])
        
        # Save metadata
        metadata_path = output_dir / f"step3a_{section_id}_metadata.json"
        metadata = {
            "section_id": section_id,
            "title": section.get("title"),
            "code_length": len(result["code"]),
            "has_errors": result.get("has_errors", False),
            "correction_attempts": result.get("correction_attempts", 0)
        }
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
        
        print("\n✅ Manim Code Generation Complete!")
        print(f"📄 Code saved to: {code_path}")
        print(f"📊 Metadata saved to: {metadata_path}")
        print(f"\n📈 Stats:")
        print(f"  - Code length: {len(result['code'])} chars")
        print(f"  - Has errors: {result.get('has_errors', False)}")
        print(f"  - Correction attempts: {result.get('correction_attempts', 0)}")
        
        # Show code preview
        lines = result["code"].split("\n")
        print(f"\n🔍 Code Preview (first 20 lines):")
        print("-" * 60)
        for i, line in enumerate(lines[:20], 1):
            print(f"{i:3d} | {line}")
        if len(lines) > 20:
            print(f"... ({len(lines) - 20} more lines)")
        
        return result
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    print("=" * 60)
    print("STEP 3a: MANIM CODE GENERATION TEST")
    print("=" * 60)
    asyncio.run(test_manim_generation())
