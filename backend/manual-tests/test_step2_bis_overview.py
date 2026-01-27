"""
Test Overview Script Generation

Quick test for the single-prompt overview mode.
Uses video_mode="overview" for short ~5 min videos.
"""

import asyncio
import json
from pathlib import Path

from app.services.script_generation import ScriptGenerator
from app.config.models import set_active_pipeline


async def test_overview_generation():
    """Test overview script generation"""
    
    # Use cost_optimized pipeline for budget-friendly generation
    set_active_pipeline("cost_optimized")
    
    # Initialize generator
    generator = ScriptGenerator()
    
    # Sample topic
    topic = {
        "index": 0,
        "title": "Introduction to Machine Learning",
        "description": "An overview of machine learning concepts and applications",
        "difficulty": "beginner",
        "estimated_duration": 5,
        "subject_area": "cs"
    }
    
    # Find a sample file or use a simple test file
    uploads_dir = Path("uploads")
    test_files = list(uploads_dir.glob("*.pdf")) + list(uploads_dir.glob("*.txt"))
    
    if test_files:
        file_path = str(test_files[0])
        print(f"📄 Using file: {file_path}")
    else:
        # Create a simple test file
        test_content = """
# Machine Learning Overview

Machine learning is a subset of artificial intelligence that enables systems to learn from data.

## Key Concepts

1. **Supervised Learning**: Learning from labeled examples
   - Classification: Categorizing data into classes
   - Regression: Predicting continuous values

2. **Unsupervised Learning**: Finding patterns in unlabeled data
   - Clustering: Grouping similar items
   - Dimensionality reduction: Simplifying complex data

3. **Neural Networks**: Models inspired by the human brain
   - Layers of interconnected nodes
   - Deep learning uses many layers

## Applications

- Image recognition
- Natural language processing  
- Recommendation systems
- Autonomous vehicles

## Conclusion

Machine learning is transforming many industries by enabling computers to learn from experience.
"""
        test_file = Path("test_ml_overview.txt")
        test_file.write_text(test_content)
        file_path = str(test_file)
        print(f"📄 Created test file: {file_path}")
    
    print("🎬 Testing OVERVIEW mode script generation...")
    print(f"Topic: {topic['title']}")
    print("-" * 60)
    
    try:
        # Generate script with overview mode
        script = await generator.generate_script(
            file_path=file_path,
            topic=topic,
            max_duration_minutes=5,
            video_mode="overview",  # <-- This is the key setting
            language="en",
        )
        
        # Save results
        output_dir = Path("test_outputs")
        output_dir.mkdir(exist_ok=True)
        
        script_path = output_dir / "overview_script.json"
        with open(script_path, "w", encoding="utf-8") as f:
            json.dump(script, f, indent=2, ensure_ascii=False)
        
        print("\n✅ Overview Script Generation Complete!")
        print(f"📄 Script saved to: {script_path}")
        print(f"\n📊 Results:")
        print(f"  - Title: {script.get('title', 'N/A')}")
        print(f"  - Sections: {len(script.get('sections', []))}")
        print(f"  - Total Duration: {script.get('total_duration_seconds', 0)} seconds ({script.get('total_duration_seconds', 0) / 60:.1f} min)")
        print(f"  - Video Mode: {script.get('video_mode', 'N/A')}")
        
        # Show all sections
        sections = script.get('sections', [])
        print(f"\n📝 Sections ({len(sections)}):")
        for i, section in enumerate(sections):
            duration = section.get('duration_seconds', 0)
            print(f"  {i+1}. {section.get('title', 'Untitled')} ({duration}s)")
            narration = section.get('narration', '')
            preview = narration[:100] + "..." if len(narration) > 100 else narration
            print(f"      Narration: {preview}")
        
        # Show cost summary
        cost_summary = script.get('cost_summary', {})
        if cost_summary:
            print(f"\n💰 Cost Summary:")
            print(f"  - Total cost: ${cost_summary.get('total_cost', 0):.4f}")
            print(f"  - Input tokens: {cost_summary.get('total_input_tokens', 0)}")
            print(f"  - Output tokens: {cost_summary.get('total_output_tokens', 0)}")
        
        return script
        
    except Exception as e:
        print(f"\n❌ Error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    result = asyncio.run(test_overview_generation())
    if result:
        print("\n✅ Test passed!")
    else:
        print("\n❌ Test failed!")
