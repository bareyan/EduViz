"""
Test Animation Generation for Production Content: The Adjoint Trick

This script tests the full animation pipeline (generation + rendering) with 
real production script to verify it can handle complex, educational content.
"""

import asyncio
import sys
from pathlib import Path
import tempfile

# Add backend to path
backend_dir = Path(__file__).parent.parent
sys.path.insert(0, str(backend_dir))

# Load environment variables from .env

from app.services.pipeline.animation.generation import ManimGenerator


async def main():
    print("=" * 60)
    print("🎬 Production Animation Test: The Adjoint Trick")
    print("=" * 60)
    
    # The first section from the production script
    section = {
        "id": "full_tabular_example",
        "title": "Démonstration Complète sur Tableau",
        "narration": "Appliquons maintenant ce formalisme à notre exemple. Dans notre premier tableau, nous plaçons en base nos variables d'écart x3, x4 et x5. Les coefficients de la fonction objectif apparaissent sur la dernière ligne. On identifie la variable d'entrée en cherchant le coefficient le plus positif sous les variables hors-base : c'est notre colonne pivot. Pour trouver la variable sortante, nous effectuons les ratios sur le côté : on divise les constantes de la colonne de droite par les éléments strictement positifs de la colonne pivot. Le ratio le plus faible nous indique la ligne pivot. L'intersection définit notre pivot. Après une première itération, nous transformons le tableau pour obtenir une nouvelle base. On répète ce processus visuel : sélection de la colonne, calcul des ratios, pivotage. Une fois que tous les coefficients de la ligne Z sont négatifs ou nuls, l'algorithme s'arrête. Il ne nous reste qu'à lire la solution : les valeurs de x1 et x2 se trouvent directement dans la colonne des constantes, nous donnant le profit maximal calculé précédemment.",
        "tts_narration": "Appliquons maintenant ce formalisme à notre exemple. Dans notre premier tableau, nous plaçons en base nos variables d'écart ix trois, ix quatre et ix cinq. Les coefficients de la fonction objectif apparaissent sur la dernière ligne. On identifie la variable d'entrée en cherchant le coefficient le plus positif sous les variables hors-base : c'est notre colonne pivot. Pour trouver la variable sortante, nous effectuons les ratios sur le côté : on divise les constantes de la colonne de droite par les éléments strictement positifs de la colonne pivot. Le ratio le plus faible nous indique la ligne pivot. L'intersection définit notre pivot. Après une première itération, nous transformons le tableau pour obtenir une nouvelle base. On répète ce processus visuel : sélection de la colonne, calcul des ratios, pivotage. Une fois que tous les coefficients de la ligne Zède sont négatifs ou nuls, l'algorithme s'arrête. Il ne nous reste qu'à lire la solution : les valeurs de ix un et ix deux se trouvent directement dans la colonne des constantes, nous donnant le profit maximal calculé précédemment.",
        "duration_seconds": 87.12,
        "narration_segments": [
          {
            "text": "Appliquons maintenant ce formalisme à notre exemple.",
            "estimated_duration": 4.16,
            "segment_index": 0
          },
          {
            "text": "Dans notre premier tableau, nous plaçons en base nos variables d'écart ix trois, ix quatre et ix cinq.",
            "estimated_duration": 8.16,
            "segment_index": 1
          },
          {
            "text": "Les coefficients de la fonction objectif apparaissent sur la dernière ligne.",
            "estimated_duration": 6.08,
            "segment_index": 2
          },
          {
            "text": "On identifie la variable d'entrée en cherchant le coefficient le plus positif sous les variables hors-base : c'est notre colonne pivot.",
            "estimated_duration": 10.8,
            "segment_index": 3
          },
          {
            "text": "Pour trouver la variable sortante, nous effectuons les ratios sur le côté : on divise les constantes de la colonne de droite par les éléments strictement positifs de la colonne pivot.",
            "estimated_duration": 14.64,
            "segment_index": 4
          },
          {
            "text": "Le ratio le plus faible nous indique la ligne pivot. L'intersection définit notre pivot.",
            "estimated_duration": 7.04,
            "segment_index": 5
          },
          {
            "text": "Après une première itération, nous transformons le tableau pour obtenir une nouvelle base.",
            "estimated_duration": 7.2,
            "segment_index": 6
          },
          {
            "text": "On répète ce processus visuel : sélection de la colonne, calcul des ratios, pivotage.",
            "estimated_duration": 6.8,
            "segment_index": 7
          },
          {
            "text": "Une fois que tous les coefficients de la ligne Zède sont négatifs ou nuls, l'algorithme s'arrête.",
            "estimated_duration": 7.76,
            "segment_index": 8
          },
          {
            "text": "Il ne nous reste qu'à lire la solution : les valeurs de ix un et ix deux se trouvent directement dans la colonne des constantes, nous donnant le profit maximal calculé précédemment.",
            "estimated_duration": 14.48,
            "segment_index": 9
          }
        ],
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
