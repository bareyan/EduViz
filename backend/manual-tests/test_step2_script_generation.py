"""
Test Step 2: Script Generation

Tests the script generation phase in isolation.
This creates the video script with narration and visual descriptions.
"""

import asyncio
import json
from pathlib import Path

from app.services.script_generation import ScriptGenerator
from app.config.models import set_active_pipeline


async def test_script_generation():
    """Test script generation with a sample topic"""
    
    # Configure pipeline
    set_active_pipeline("default")  # or "high_quality", "cost_optimized"
    
    # Initialize generator
    generator = ScriptGenerator()
    
    # Sample topic (you can customize this)
    topic = {
        "index": 0,
        "title": "Pythagorean Theorem",
        "description": "The fundamental relationship between the sides of a right triangle",
        "difficulty": "beginner",
        "estimated_duration": 5
    }
    
    # Sample material content (or use a real file)
    # For testing, you can either:
    # 1. Use a file path: file_path = "path/to/your/document.pdf"
    # 2. Or use inline content as shown below
    
    print("🎬 Step 2: Generating Script...")
    print(f"Topic: {topic['title']}")
    print("-" * 60)
    
    try:
        # Option 1: Use a real file if you have one
        file_path = input("Enter path to document (or press Enter to skip): ").strip()
        if not file_path:
            file_path = None
            print("Using inline sample content instead...")
        
        # Generate script
        script = await generator.generate_script(
            file_path=file_path,
            topic=topic,
            max_duration_minutes=10,
            video_mode="comprehensive",  # or "overview"
            language="en",
            content_focus="as_document",  # or "practice", "theory"
            document_context="auto"  # or "standalone", "series"
        )
        
        # Save results
        output_dir = Path("test_outputs")
        output_dir.mkdir(exist_ok=True)
        
        script_path = output_dir / "step2_script.json"
        with open(script_path, "w", encoding="utf-8") as f:
            json.dump(script, f, indent=2, ensure_ascii=False)
        
        print("\n✅ Script Generation Complete!")
        print(f"📄 Script saved to: {script_path}")
        print(f"\n📊 Results:")
        print(f"  - Title: {script.get('title', 'N/A')}")
        print(f"  - Sections: {len(script.get('sections', []))}")
        print(f"  - Learning Objectives: {len(script.get('learning_objectives', []))}")
        
        # Show first section as preview
        sections = script.get('sections', [])
        if sections:
            first_section = sections[0]
            print(f"\n📝 First Section Preview:")
            print(f"  - Title: {first_section.get('title', 'N/A')}")
            print(f"  - Narration length: {len(first_section.get('narration', ''))} chars")
            print(f"  - Visual elements: {len(first_section.get('visual_elements', []))}")
        
        return script
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    print("=" * 60)
    print("STEP 2: SCRIPT GENERATION TEST")
    print("=" * 60)
    asyncio.run(test_script_generation())
