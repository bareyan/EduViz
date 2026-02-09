"""
User prompts for the Animation Pipeline.

These define the specific instructions for each generation phase.
"""

from app.services.infrastructure.llm.prompting_engine.prompts.base import PromptTemplate


# =============================================================================
# PHASE 1: CHOREOGRAPHY PLANNING
# =============================================================================

CHOREOGRAPHY_USER = PromptTemplate(
    template="""Create a detailed Visual Choreography Plan for this educational content.

## CONTENT
**Title**: {title}
**Duration**: {target_duration}s
**Theme**: {theme_info}
**Language**: {language_name}
**Visual Strategy**:
{visual_strategy}

**Narration**:
{narration}

**Segment Timings**:
{timing_info}

**Visual Hints**:
{visual_hints}

**Section Data (for visuals, may be non-narrated)**:
{section_data}

## YOUR TASK

Create a structured plan with:

1. **Object Lifecycle**: List every visual object, when it's created, and when it's removed
2. **Animation Timeline**: For each segment, describe:
   - What appears/disappears
   - How it animates (Create, FadeIn, Transform, etc.)
   - Exact start time and duration
3. **Spatial Layout**: Where objects are positioned
4. **Scene Type**: Choose `"2D"` or `"3D"` (default: "2D")

## LANGUAGE REQUIREMENT (CRITICAL)
- ALL text labels, titles, and non-mathematical text MUST be in **{language_name}**
- Match the language of the narration exactly
- Mathematical notation (MathTex, formulas) should remain in standard math notation
- Use `MathTex(...)` for standalone formulas and symbolic expressions
- Use `Tex(...)` for mixed prose + inline math (for example: "Value is $x$")
- Do NOT place LaTeX commands (for example `\\in`, `\\frac`) inside `Text(...)`
- Currency amounts like `$5` or `$12.99` are text, not math
- Example: For Russian narration, use Russian text like "Введение" instead of "Introduction"

## QUALITY GUIDANCE
- Reuse objects across segments; prefer Transform/ReplacementTransform over delete+recreate
- Maintain spatial anchors for recurring elements; avoid unnecessary repositioning
- Keep the scene visually stable; avoid clearing the whole scene unless narratively needed
- Introduce new elements only when they support narration; avoid clutter
- Make transitions explicit: add FadeOut/Transform steps when elements are no longer needed
- **SPATIAL RELATIONSHIPS**: Define relative positioning to prevent overlaps:
  - Use "relative_to" + "relation" fields to position objects relative to each other
  - Examples: title "above" equation, note_box "right_of" diagram, label "below" graph
  - "spacing" controls distance (0.3-1.0 recommended, larger for separation)
  - Minimum non-touch margins for co-visible objects:
    text-text >= 0.4, text-shape >= 0.3, shape-shape >= 0.2
  - First/anchor objects use "relative_to": null and absolute "position"
  - This ensures implementation stage maintains proper spacing automatically
- **SCREEN ZONING (MANDATORY)**:
  - Assign every object a `layout_zone` from:
    top_left, top_center, top_right, mid_left, center, mid_right,
    bottom_left, bottom_center, bottom_right
  - Co-visible objects should occupy distinct zones unless one replaces another
  - Do not stack multiple text-heavy objects at `center`
- **VISUAL INTENT METADATA**:
  - For EVERY step, include `visual_change`: what viewers should see change on screen
  - For EVERY step, include `narration_cue`: short phrase from narration this step aligns to
  - Use optional `data_binding` when step/object maps to supporting_data or a referenced content item
- If narration cites Figure/Table/Equation/Appendix, include object(s) that recreate it and bind them via `data_binding`
- Do NOT invent external files or fake paths.
- Use `asset_path` ONLY when a concrete usable file path is already present in Section Data; otherwise leave it empty.

## CONSTRAINTS (STRICT)
- Max 20 objects total
- Max 6 steps per segment
- Notes length: 12 words or fewer
- Never plan co-visible objects with zero gap or touching boundaries
- Avoid line breaks inside strings
- Position must be one of: center, left, right, up, down, upper_left, upper_right, lower_left, lower_right, or x,y
- Use ONLY Manim direction constants: UP, DOWN, LEFT, RIGHT, UL, UR, DL, DR, IN, OUT, ORIGIN
- DO NOT use TOP or BOTTOM
- 3D objects allowed ONLY when scene_type is "3D"

## 3D OBJECTS (if scene_type = "3D")
- ThreeDAxes, Sphere, Cube, Cylinder, Cone, Torus, Surface, ParametricSurface
- Provide optional camera: phi, theta, distance, ambient_rotation_rate

## OUTPUT FORMAT (STRICT JSON ONLY)

Return a single JSON object with this schema:

{{
  "scene_type": "2D|3D",
  "camera": {{
    "phi": 1.1,
    "theta": -0.8,
    "distance": 6.0,
    "ambient_rotation_rate": 0.0
  }},
  "objects": [
    {{
      "id": "string",
      "type": "string",
      "text": "string",
      "latex": "string",
      "appears_at": 0.0,
      "removed_at": 5.0,
      "notes": "string",
      "visual_description": "string",
      "layout_zone": "top_left|top_center|top_right|mid_left|center|mid_right|bottom_left|bottom_center|bottom_right",
      "relative_to": "object_id|null",
      "relation": "above|below|left_of|right_of|null",
      "spacing": 0.5
    }}
  ],
  "segments": [
    {{
      "segment_index": 0,
      "start_time": 0.0,
      "end_time": 6.0,
      "steps": [
        {{
          "time": 0.0,
          "action": "Create|FadeIn|Transform|ReplacementTransform|Write|Wait|FadeOut",
          "target": "object_id",
          "source": "object_id",
          "position": "string",
          "duration": 1.5,
          "notes": "string",
          "visual_change": "string",
          "narration_cue": "string",
          "data_binding": "string"
        }}
      ]
    }}
  ],
  "screen_bounds": {{
    "x": [-5.5, 5.5],
    "y": [-3.0, 3.0]
  }}
}}

Be precise with timing. Total must equal {target_duration}s.""",
    description="User prompt for choreography planning phase"
)

# =============================================================================
# COMPACT CHOREOGRAPHY (FALLBACK)
# =============================================================================

CHOREOGRAPHY_COMPACT_USER = PromptTemplate(
    template="""Create a compact Visual Choreography Plan for this educational content.

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
- Max 10 objects total
- Max 3 steps per segment
- No line breaks inside strings
- Keep output as small as possible
- Prefer including `visual_change` and `narration_cue` when token budget allows
- Keep `layout_zone` for each object when token budget allows
- Do NOT invent external files or fake paths.
- Use `asset_path` ONLY when a concrete usable file path is already present in the provided content.
- Position must be one of: center, left, right, up, down, upper_left, upper_right, lower_left, lower_right, or x,y
- Use ONLY Manim direction constants: UP, DOWN, LEFT, RIGHT, UL, UR, DL, DR, IN, OUT, ORIGIN
- DO NOT use TOP or BOTTOM
- 3D objects allowed ONLY when scene_type is "3D"

## OUTPUT FORMAT (STRICT JSON ONLY)

Return a single JSON object with this schema:

{{
  "scene_type": "2D|3D",
  "camera": {{
    "phi": 1.1,
    "theta": -0.8,
    "distance": 6.0,
    "ambient_rotation_rate": 0.0
  }},
  "objects": [
    {{
      "id": "string",
      "type": "string",
      "text": "string",
      "latex": "string",
      "appears_at": 0.0,
      "removed_at": 5.0,
      "layout_zone": "string",
      "relative_to": "object_id|null",
      "relation": "above|below|left_of|right_of|null",
      "spacing": 0.5
    }}
  ],
  "segments": [
    {{
      "segment_index": 0,
      "start_time": 0.0,
      "end_time": 6.0,
      "steps": [
        {{
          "time": 0.0,
          "action": "Create|FadeIn|Transform|ReplacementTransform|Write|Wait|FadeOut",
          "target": "object_id",
          "source": "object_id",
          "position": "string",
          "duration": 1.5,
          "visual_change": "string",
          "narration_cue": "string",
          "data_binding": "string"
        }}
      ]
    }}
  ],
  "screen_bounds": {{
    "x": [-5.5, 5.5],
    "y": [-3.0, 3.0]
  }}
}}

Be precise with timing. Total must equal {target_duration}s.""",
    description="Compact choreography prompt for JSON truncation fallback"
)

# =============================================================================
# CHOREOGRAPHY CHUNKED FALLBACK (OBJECTS + SEGMENTS)
# =============================================================================

CHOREOGRAPHY_OBJECTS_USER = PromptTemplate(
    template="""Create a compact Visual Object Catalog for this educational content.

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
- Max 10 objects total
- No notes or narration fields
- No line breaks inside strings
- Keep output as small as possible
- If possible, include `visual_description` to clarify object intent
- Keep `layout_zone` if possible to support overlap-free placement
- Do NOT invent external files or fake paths.
- Use `asset_path` ONLY when a concrete usable file path is already present in the provided content.
- 3D objects allowed ONLY when scene_type is "3D"

## OUTPUT FORMAT (STRICT JSON ONLY)

Return a single JSON object with this schema:

{{
  "scene_type": "2D|3D",
  "camera": {{
    "phi": 1.1,
    "theta": -0.8,
    "distance": 6.0,
    "ambient_rotation_rate": 0.0
  }},
  "objects": [
    {{
      "id": "string",
      "type": "string",
      "text": "string",
      "latex": "string",
      "appears_at": 0.0,
      "removed_at": 5.0,
      "visual_description": "string",
      "layout_zone": "string"
    }}
  ]
}}
""",
    description="Chunked choreography fallback: objects catalog"
)

CHOREOGRAPHY_SEGMENTS_USER = PromptTemplate(
    template="""Create compact choreography steps for the specified segment range.

## CONTENT
**Title**: {title}
**Duration**: {target_duration}s

**Segment Range**:
{segment_range}

**Segment Timings (subset)**:
{segment_chunk}

**Object Catalog (use ONLY these ids)**:
{object_catalog}

## REQUIREMENTS (STRICT)
- Only include segments from the provided chunk
- Max 3 steps per segment
- No line breaks inside strings
- Keep output as small as possible
- Prefer including `visual_change` and `narration_cue` when token budget allows
- Do NOT invent external files or fake paths.
- Position must be one of: center, left, right, up, down, upper_left, upper_right, lower_left, lower_right, or x,y
- Use ONLY Manim direction constants: UP, DOWN, LEFT, RIGHT, UL, UR, DL, DR, IN, OUT, ORIGIN
- DO NOT use TOP or BOTTOM

## OUTPUT FORMAT (STRICT JSON ONLY)

Return a single JSON object with this schema:

{{
  "segments": [
    {{
      "segment_index": 0,
      "start_time": 0.0,
      "end_time": 6.0,
      "steps": [
        {{
          "time": 0.0,
          "action": "Create|FadeIn|Transform|ReplacementTransform|Write|Wait|FadeOut",
          "target": "object_id",
          "source": "object_id",
          "position": "string",
          "duration": 1.5,
          "visual_change": "string",
          "narration_cue": "string",
          "data_binding": "string"
        }}
      ]
    }}
  ]
}}
""",
    description="Chunked choreography fallback: segment steps"
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
- **Class Name**: Scene{section_id_title}
- **Theme**: {theme_info}
- **Language**: {language_name}
- If scene_type is missing, assume 2D

## LANGUAGE REQUIREMENT (CRITICAL)
- ALL text labels, titles, and non-mathematical text MUST be in **{language_name}**
- Match the language used in the choreography plan
- Mathematical notation (MathTex, formulas) should remain in standard math notation
- Use `MathTex(...)` for standalone formulas; do not wrap math with `$...$` inside `MathTex`
- Use `Tex(...)` for mixed prose + inline math segments
- Do NOT place LaTeX commands inside `Text(...)`
- Currency amounts like `$5` or `$12.99` must stay in `Text(...)`
- Example: For Russian, use `Text("Введение")` instead of `Text("Introduction")`
- Example: For Ukrainian, use `Text("Вступ")` instead of `Text("Introduction")`

## CODE REQUIREMENTS
1. Start with `from manim import *  # type: ignore`
2. If plan scene_type is "3D", use `class Scene{section_id_title}(ThreeDScene)`
3. If plan scene_type is "2D" or missing, use `class Scene{section_id_title}(Scene)`
4. Implement `def construct(self):`
5. Do NOT override the theme background (it is enforced)
6. **STRICTLY FOLLOW the Constraints & Patterns below to avoid crashes.**
7. Prioritize step metadata when present:
   - `visual_change`: exact on-screen state change to implement
   - `narration_cue`: timing/meaning alignment for the step
   - `data_binding`: bind visuals to matching supporting/reference data
8. If these metadata fields are missing in a step, fall back to `action` + `notes`.
9. Honor object-level `layout_zone` + `relative_to` + `relation` to avoid overlap.
10. When multiple objects are visible together, spread them across zones and use
    `next_to(..., buff=...)` rather than `move_to(ORIGIN)` for all.
11. Maintain minimum clear margins between co-visible objects:
    text-text >= 0.4, text-shape >= 0.3, shape-shape >= 0.2.

## MANIM PATTERNS & CRITICAL CONSTRAINTS
{patterns}

## TYPE-TO-MANIM MAPPING (COMPACT)
- Text -> `Text("...", font_size=36, color=WHITE)`
- MathTex -> `MathTex(r"...")`
- Rectangle -> `Rectangle(...)`
- Circle -> `Circle(...)`
- Line -> `Line(...)`
- Arrow -> `Arrow(...)`
- Axes -> `Axes(...)`
- ThreeDAxes -> `ThreeDAxes(...)`
- Sphere/Cube/Cylinder/Cone/Torus -> corresponding Manim mobject

## TIMING RULES (STRICT)
- Every `self.play(...)` MUST include `run_time=...`
- Every segment must be padded with `self.wait(...)` so total duration matches
- Use only allowed direction constants: UP, DOWN, LEFT, RIGHT, UL, UR, DL, DR, IN, OUT, ORIGIN
- DO NOT use TOP or BOTTOM

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
- Defines `class Scene{section_id_title}(Scene)` or `class Scene{section_id_title}(ThreeDScene)`
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
- edits: 1–10 objects with exact search_text and replacement_text

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
