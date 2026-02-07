"""
User prompts for the Animation Pipeline.

These define the specific instructions for each generation phase.
"""

from app.services.infrastructure.llm.prompting_engine.prompts.base import PromptTemplate


# =============================================================================
# PHASE 1: CHOREOGRAPHY PLANNING
# =============================================================================

CHOREOGRAPHY_USER = PromptTemplate(
    template="""Create a detailed Visual Choreography Plan (Schema v2) for this educational content.

## CONTENT
**Title**: {title}
**Duration**: {target_duration}s
**Theme**: {theme_info}
**Language**: {language_name}

**Narration**:
{narration}

**Segment Timings**:
{timing_info}

**Visual Hints**:
{visual_hints}

**Section Data (for visuals, may be non-narrated)**:
{section_data}

## YOUR TASK
- Build an executable choreography JSON object.
- Plan object lifecycle, spatial placement, and timeline actions.
- Prefer stable anchors and transforms over delete+recreate.
- Choose scene mode: `"2D"` (default) or `"3D"`.

## LANGUAGE REQUIREMENT (CRITICAL)
- ALL text labels, titles, and non-mathematical text MUST be in **{language_name}**
- Match the language of the narration exactly
- Mathematical notation (MathTex, formulas) should remain in standard math notation
- Example: For Russian narration, use Russian text like "Введение" instead of "Introduction"

## QUALITY GUIDANCE
- Reuse objects across segments; prefer Transform/ReplacementTransform over delete+recreate.
- Keep scene stable; avoid full clears unless narratively required.
- Keep max visible objects around 10.
- Explicitly add FadeOut/Transform when objects are replaced.
- Use absolute anchors for major objects, then relative placement for dependents.

## ENGAGEMENT DIRECTIVES (MANDATORY)
- Prioritize visual storytelling (diagrams, flows, graphs, comparisons), not narration-as-subtitles.
- Keep Text labels short (prefer 1-4 words). Do NOT copy narration sentences onto screen.
- For sections >= 15s, ensure at least 60% of planned objects are non-Text/MathTex objects.
- Each segment must include at least one non-text visual action (Create/FadeIn/Transform/ReplacementTransform/FadeOut on a non-text object).
- Across the full section, use at least 3 distinct non-text object kinds (for example: Circle, Rectangle, Line, Arrow, Axes, NumberPlane).
- Prefer progressive visual builds (state A -> state B -> state C) over static cards.

## CONSTRAINTS (STRICT)
- Max 24 objects total.
- Max 8 actions per segment.
- Notes are concise and optional.
- Use true JSON `null` values, never the string `"null"`.
- Quantize all times to milliseconds (3 decimal places).
- Forbidden direction constants: TOP, BOTTOM.
- 3D objects allowed only when `scene.mode` is `"3D"`.

## OUTPUT FORMAT (STRICT JSON ONLY)

Return a single JSON object with this structure:

{{
  "version": "2.0",
  "scene": {{
    "mode": "2D|3D",
    "camera": null,
    "safe_bounds": {{
      "x_min": -5.5,
      "x_max": 5.5,
      "y_min": -3.0,
      "y_max": 3.0
    }}
  }},
  "objects": [
    {{
      "id": "string",
      "kind": "Text|MathTex|Rectangle|Circle|Line|Arrow|Dot|Axes|NumberPlane|Polygon|Brace|ThreeDAxes|Sphere|Cube|Cylinder|Cone|Torus|Surface|ParametricSurface",
      "content": {{
        "text": "string|null",
        "latex": "string|null",
        "asset_path": "string|null"
      }},
      "placement": {{
        "type": "absolute|relative",
        "absolute": {{ "x": 0.0, "y": 2.6 }},
        "relative": {{ "relative_to": "object_id", "relation": "above|below|left_of|right_of", "spacing": 0.5 }}
      }},
      "lifecycle": {{ "appear_at": 0.0, "remove_at": 5.0 }}
    }}
  ],
  "timeline": [
    {{
      "segment_index": 0,
      "start_at": 0.0,
      "end_at": 6.0,
      "actions": [
        {{
          "at": 0.0,
          "op": "Create|FadeIn|Transform|ReplacementTransform|Write|Wait|FadeOut",
          "target": "object_id",
          "source": "object_id|null",
          "run_time": 1.5
        }}
      ]
    }}
  ],
  "constraints": {{
    "language": "{language_name}",
    "max_visible_objects": 10,
    "forbidden_constants": ["TOP", "BOTTOM"]
  }},
  "notes": []
}}

Total timeline should cover {target_duration}s.""",
    description="User prompt for choreography planning phase"
)

# =============================================================================
# COMPACT CHOREOGRAPHY (FALLBACK)
# =============================================================================

CHOREOGRAPHY_COMPACT_USER = PromptTemplate(
    template="""Create a compact Visual Choreography Plan (Schema v2) for this educational content.

## CONTENT
**Title**: {title}
**Duration**: {target_duration}s
**Theme**: {theme_info}
**Language**: {language_name}

**Narration**:
{narration}

**Segment Timings**:
{timing_info}

**Visual Hints**:
{visual_hints}

## LANGUAGE REQUIREMENT (CRITICAL)
- ALL text labels and titles MUST be in **{language_name}**
- Mathematical notation should remain in standard math notation

## REQUIREMENTS (STRICT)
- Max 14 objects total.
- Max 5 actions per segment.
- Keep output concise.
- Use true JSON `null`; never `"null"`.
- Times are milliseconds precision (3 decimals).
- Forbidden direction constants: TOP, BOTTOM.

## ENGAGEMENT DIRECTIVES (MANDATORY)
- Avoid subtitle-like narration text on screen; keep labels short.
- For sections >= 15s, include at least 2 non-text object kinds and at least one Transform or ReplacementTransform.
- Each segment should include a visible non-text motion/change, not just text swaps.

## OUTPUT FORMAT (STRICT JSON ONLY)

Return a single JSON object with this structure:

{{
  "version": "2.0",
  "scene": {{
    "mode": "2D|3D",
    "camera": null,
    "safe_bounds": {{
      "x_min": -5.5,
      "x_max": 5.5,
      "y_min": -3.0,
      "y_max": 3.0
    }}
  }},
  "objects": [
    {{
      "id": "string",
      "kind": "Text|MathTex|Rectangle|Circle|Line|Arrow|Dot|Axes|NumberPlane|Polygon|Brace|ThreeDAxes|Sphere|Cube|Cylinder|Cone|Torus|Surface|ParametricSurface",
      "content": {{ "text": "string|null", "latex": "string|null", "asset_path": "string|null" }},
      "placement": {{
        "type": "absolute|relative",
        "absolute": {{ "x": 0.0, "y": 0.0 }},
        "relative": {{ "relative_to": "id", "relation": "above|below|left_of|right_of", "spacing": 0.5 }}
      }},
      "lifecycle": {{ "appear_at": 0.0, "remove_at": 5.0 }}
    }}
  ],
  "timeline": [
    {{
      "segment_index": 0,
      "start_at": 0.0,
      "end_at": 6.0,
      "actions": [
        {{
          "at": 0.0,
          "op": "Create|FadeIn|Transform|ReplacementTransform|Write|Wait|FadeOut",
          "target": "object_id",
          "source": "object_id|null",
          "run_time": 1.5
        }}
      ]
    }}
  ],
  "constraints": {{
    "language": "{language_name}",
    "max_visible_objects": 10,
    "forbidden_constants": ["TOP", "BOTTOM"]
  }},
  "notes": []
}}

Total timeline should cover {target_duration}s.""",
    description="Compact choreography prompt for JSON truncation fallback"
)

# =============================================================================
# PHASE 2: FULL IMPLEMENTATION
# =============================================================================

FULL_IMPLEMENTATION_USER = PromptTemplate(
    template="""Implement the COMPLETE Manim animation based on this choreography plan.

## CHOREOGRAPHY PLAN (notes may be omitted in compact plans)
{plan}

## SEGMENT TIMINGS
{segment_timings}

## SECTION DATA (for visuals, may be non-narrated)
{section_data}

## REQUIREMENTS
- **Total Duration**: {total_duration}s (must match exactly)
- **Class Name**: Section{section_id_title}
- **Theme**: {theme_info}
- **Language**: {language_name}
- If `scene.mode` is missing, assume "2D"

## LANGUAGE REQUIREMENT (CRITICAL)
- ALL text labels, titles, and non-mathematical text MUST be in **{language_name}**
- Match the language used in the choreography plan
- Mathematical notation (MathTex, formulas) should remain in standard math notation
- Example: For Russian, use `Text("Введение")` instead of `Text("Introduction")`
- Example: For Ukrainian, use `Text("Вступ")` instead of `Text("Introduction")`

## CODE REQUIREMENTS
1. Start with `from manim import *  # type: ignore`
2. If plan `scene.mode` is "3D", use `class Section{section_id_title}(ThreeDScene)`
3. If plan `scene.mode` is "2D" or missing, use `class Section{section_id_title}(Scene)`
4. Implement `def construct(self):`
5. Do NOT override the theme background (it is enforced)
6. **STRICTLY FOLLOW the Constraints & Patterns below to avoid crashes.**

## MANIM PATTERNS & CRITICAL CONSTRAINTS
{patterns}

## TYPE-TO-MANIM MAPPING (COMPACT)
- Text -> `Text("...", font_size=36, color=WHITE)`
- MathTex -> `MathTex(r"...")`
- Rectangle -> `Rectangle(...)`
- Circle -> `Circle(...)`
- Line -> `Line(...)`
- Arrow -> `Arrow(...)`
- Dot -> `Dot(...)`
- Axes -> `Axes(...)`
- NumberPlane -> `NumberPlane(...)`
- Polygon -> `Polygon(...)`
- Brace -> `Brace(...)`
- ThreeDAxes -> `ThreeDAxes(...)`
- Sphere/Cube/Cylinder/Cone/Torus -> corresponding Manim mobject

## VISUAL ENGAGEMENT RULES (MANDATORY)
- Convert narration ideas into animated diagrams, comparisons, flows, or plots, not long paragraph text.
- Keep Text objects short label-style. If text would exceed 6 words, break it into concise labels and support with geometry.
- For sections >= 15s, include at least 3 non-text animated elements and at least one state-to-state morph (`Transform` or `ReplacementTransform`).
- Introduce meaningful visual change every ~4-6 seconds (motion, morph, reveal, highlight), not only waits.
- Prefer grouped concept visuals (nodes + edges + labels) over isolated text lines.

## TIMING RULES (STRICT)
- Every `self.play(...)` MUST include `run_time=...`
- Every segment must be padded with `self.wait(...)` so total duration matches
- Use only allowed direction constants: UP, DOWN, LEFT, RIGHT, UL, UR, DL, DR, IN, OUT, ORIGIN
- DO NOT use TOP or BOTTOM
- Keep timing code clean: compute waits directly, avoid meta "re-sync" commentary in output code.

## SELF-CORRECTION (THINK BEFORE WRITING)
- **Version Check**: Am I using Manim Community v0.19.2 syntax? (e.g., `font_size` instead of `size`)
- **Spatial Check**: Is any object moving beyond X: 5.5 or Y: 3.0?
- **Overlap Check**: Did I FadeOut the previous text before FadingIn the new text?
- **Color Check**: Am I using only official Manim colors (e.g., `BLUE_C` NOT `CYAN`)?
- **Language Check**: Are all Text() strings in {language_name}?

## OUTPUT
Return the complete, runnable Python file in a code block.

## FINAL SELF-CHECK (MUST PASS)
- Has `from manim import *`
- Defines `class Section{section_id_title}(Scene)` or `class Section{section_id_title}(ThreeDScene)`
- Background set by theme (do not override)
- No lists passed directly into `self.play(...)`
- No `self.wait(0)` or `self.wait(x if condition else 0)` - these CRASH
- No `ValueTracker.number`
- Only allowed rate functions
- All objects within bounds
- All Text() strings are in {language_name}""",
    description="Single-shot full file implementation prompt"
)


# =============================================================================
# PHASE 3: SURGICAL FIXES
# =============================================================================

SURGICAL_FIX_USER = PromptTemplate(
    template="""Fix the listed errors in the ManimCE v0.19.2 code using SURGICAL text replacements.

You MUST output a single JSON object that matches the required schema:
- analysis: string (<=200 chars)
- edits: 1–2 objects with exact search_text and replacement_text

RULES:
- search_text MUST be copied EXACTLY from CURRENT CODE (including whitespace).
- Include 2–3 lines of surrounding context (max ~10 lines total).
- Replace ONLY the minimum lines needed to fix the errors.
- Do NOT reformat or make cosmetic changes.

## CURRENT CODE
```python
{code}
```

## ERRORS TO FIX
```
{errors}
```

{visual_context}

## SPATIAL FIX STRATEGIES

### Overlapping Objects
When two objects overlap, separate them by modifying position:
- Use `.next_to(other_obj, direction, buff=0.3)` to position relative to another
- Use `.shift(direction * amount)` to move (e.g., `.shift(UP * 0.5)`)
- Use `.move_to(point)` for exact coordinates
- Safe positions: Y from -2.5 to 2.5, X from -5 to 5

Example fix for overlap:
```python
# Before (overlapping)
text1.move_to(ORIGIN)
text2.move_to(ORIGIN)

# After (separated)
text1.move_to(UP * 0.5)
text2.move_to(DOWN * 0.5)
```

### Out of Bounds
When object exceeds screen edges (error shows direction like "Right (+0.88)"):
- Shift opposite direction: "Right" violation → `.shift(LEFT * 1)`
- Scale down: `.scale(0.7)` to make smaller
- Reposition to safe zone: `.move_to(LEFT * 2)` instead of edge

### Low Contrast
When text blends with background (#171717 is dark):
- Use bright colors: WHITE, YELLOW, BLUE, GREEN, RED, ORANGE
- Avoid: GRAY, BLACK, or any dark colors
- Fix: Add `color=WHITE` in constructor OR `.set_color(WHITE)`

Common syntax fixes:
- `tracker.number` → `tracker.get_value()`
- `ease_in_expo` → `smooth`
- `self.wait(0)` → remove the line
- `BOTTOM` → `DOWN`, `TOP` → `UP`""",
    description="Surgical fix prompt with spatial guidance"
)


SURGICAL_FIX_FOLLOWUP = PromptTemplate(
    template="""The previous edits were applied, but validation failed with the following errors.

## REVISED CODE STATE
```python
{code}
```

## NEW ERRORS
```
{errors}
```

Please analyze the new state and errors. Provide a new JSON correction following the same schema.""",
    description="Follow-up prompt for conversational fixing"
)
