
import os
import sys
import json

# Ensure backend module is found
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(current_dir)

from app.services.pipeline.animation.generation.validation.code_validator import CodeValidator

def main():
    # 1. Paste your tool output JSON here
    tool_input = {
      "objects_used": [
        "Text",
        "MathTex",
        "Arrow"
      ],
      "estimated_duration": 7.5,
      "code": "# Segment 2: Introduction to Limits\n# Narration: \"A limit tells us...\"\n# Duration: 3.0s audio + 0.5s pause = 3.5s total\ntitle = Text(\"Introduction to Limits\", font_size=36).to_edge(UP)\nself.play(Write(title), run_time=2.0)\nself.wait(1.0) # Finish 3.0s audio duration\nself.wait(0.5) # Post-narration pause\n\n# Segment 3: ...approaches a value.\n# Narration: \"...approaches a value.\"\n# Duration: 4.0s audio + 0.0s pause = 4.0s total\nlimit_eq = MathTex(r\"\\lim_{x \\to a} f(x) = L\", font_size=48)\nlimit_eq.next_to(title, DOWN, buff=1.5)\nself.play(FadeIn(limit_eq, shift=UP), run_time=1.5)\n\n# Highlight 'x approaches a'\narrow = Arrow(DOWN, UP, color=BLUE).next_to(limit_eq[0][1:4], DOWN, buff=0.2)\nx_approaches = Text(\"x approaches a\", font_size=24, color=BLUE).next_to(arrow, DOWN)\nself.play(Create(arrow), Write(x_approaches), run_time=1.5)\n\nself.wait(1.0) # Finish 4.0s audio duration\n# No post-pause for segment 3\n"

    }
    
    code = tool_input.get("code", "")
    print("--- Validating Code Snippet ---")
    print(f"Code Length: {len(code)} chars")
    
    # 2. Run Validator
    # The CodeValidator is now smart enough to auto-wrap snippets!
    validator = CodeValidator()
    result = validator.validate(code)
    
    # 3. Print Results
    print(f"\nVALID: {result.valid}")
    
    if not result.valid:
        print("\n--- ERRORS ---")
        print(result.get_error_summary())
    else:
        print("\n--- WARNINGS (if any) ---")
        if result.structure.warnings:
            for w in result.structure.warnings:
                print(f"[Structure] {w}")
        if result.spatial.warnings:
            for w in result.spatial.warnings:
                print(f"[Spatial] {w.message}")

    # 4. Show the Feedback you should paste back to AI Studio
    print("\n" + "="*40)
    print("PASTE THIS BACK TO AI STUDIO:")
    print("="*40)
    if result.valid:
        print("Validation Successful. Code structure, imports, and spatial layout are correct.")
    else:
        print(f"Validation Failed:\n{result.get_error_summary()}")

if __name__ == "__main__":
    main()
