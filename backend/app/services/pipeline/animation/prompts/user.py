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

**Narration**:
{narration}

**Segment Timings**:
{timing_info}

**Visual Hints**:
{visual_hints}

## YOUR TASK

Create a structured plan with:

1. **Object Lifecycle**: List every visual object, when it's created, and when it's removed
2. **Animation Timeline**: For each segment, describe:
   - What appears/disappears
   - How it animates (Create, FadeIn, Transform, etc.)
   - Exact start time and duration
3. **Spatial Layout**: Where objects are positioned
4. **Scene Type**: Choose `"2D"` or `"3D"` (default: "2D")

## QUALITY GUIDANCE
- Reuse objects across segments; prefer Transform/ReplacementTransform over delete+recreate
- Maintain spatial anchors for recurring elements; avoid unnecessary repositioning
- Keep the scene visually stable; avoid clearing the whole scene unless narratively needed
- Introduce new elements only when they support narration; avoid clutter
- Make transitions explicit: add FadeOut/Transform steps when elements are no longer needed

## CONSTRAINTS (STRICT)
- Max 20 objects total
- Max 6 steps per segment
- Notes length: 12 words or fewer
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
      "asset_path": "string",
      "appears_at": 0.0,
      "removed_at": 5.0,
      "notes": "string"
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
          "notes": "string"
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

**Narration**:
{narration}

**Segment Timings**:
{timing_info}

**Visual Hints**:
{visual_hints}

## REQUIREMENTS (STRICT)
- Max 10 objects total
- Max 3 steps per segment
- No line breaks inside strings
- Keep output as small as possible
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
      "asset_path": "string",
      "appears_at": 0.0,
      "removed_at": 5.0
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
          "duration": 1.5
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

**Narration**:
{narration}

**Segment Timings**:
{timing_info}

**Visual Hints**:
{visual_hints}

## REQUIREMENTS (STRICT)
- Max 10 objects total
- No notes or narration fields
- No line breaks inside strings
- Keep output as small as possible
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
      "asset_path": "string",
      "appears_at": 0.0,
      "removed_at": 5.0
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
          "duration": 1.5
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

## REQUIREMENTS
- **Total Duration**: {total_duration}s (must match exactly)
- **Class Name**: Scene{section_id_title}
- **Theme**: {theme_info}
- If scene_type is missing, assume 2D

## CODE REQUIREMENTS
1. Start with `from manim import *`
2. If plan scene_type is "3D", use `class Scene{section_id_title}(ThreeDScene)`
3. If plan scene_type is "2D" or missing, use `class Scene{section_id_title}(Scene)`
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
- Axes -> `Axes(...)`
- ThreeDAxes -> `ThreeDAxes(...)`
- Sphere/Cube/Cylinder/Cone/Torus -> corresponding Manim mobject

## TIMING RULES (STRICT)
- Every `self.play(...)` MUST include `run_time=...`
- Every segment must be padded with `self.wait(...)` so total duration matches
- Use only allowed direction constants: UP, DOWN, LEFT, RIGHT, UL, UR, DL, DR, IN, OUT, ORIGIN
- DO NOT use TOP or BOTTOM

## OUTPUT
Return the complete, runnable Python file in a code block.

## FINAL SELF-CHECK (MUST PASS)
- Has `from manim import *`
- Defines `class Scene{section_id_title}(Scene)` or `class Scene{section_id_title}(ThreeDScene)`
- Background set by theme (do not override)
- No lists passed directly into `self.play(...)`
- No `self.wait(0)`
- No `ValueTracker.number`
- Only allowed rate functions
- All objects within bounds""",
    description="Single-shot full file implementation prompt"
)


# =============================================================================
# PHASE 3: SURGICAL FIXES
# =============================================================================

SURGICAL_FIX_USER = PromptTemplate(
    template="""The Manim code has validation errors. Fix them surgically.

## CURRENT CODE
```python
{code}
```

## ERRORS
{errors}

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

## INSTRUCTIONS
Return STRICT JSON ONLY with this schema:
{{
  "edits": [
    {{
      "search_text": "exact literal code snippet to replace",
      "replacement_text": "replacement snippet"
    }}
  ],
  "full_code_lines": ["optional full corrected file as an array of lines"],
  "full_code": "optional full corrected file if lines are not possible",
  "notes": "optional brief notes"
}}

Guidelines:
- Prefer minimal, localized edits.
- `search_text` must match EXACTLY (include 2-3 lines of context).
- Use the error line number to find the precise block.
- If static syntax errors exist, return ONLY `full_code_lines` (no edits).
- If multiple changes are needed and edits are too risky, return `full_code_lines`.
- Auto-fix directions: `BOTTOM` -> `DOWN`, `TOP` -> `UP`

Common syntax fixes (if needed):
- `tracker.number` → `tracker.get_value()`
- `ease_in_expo` → `smooth`
- `self.wait(0)` → remove the line""",
    description="Surgical fix prompt with spatial guidance"
)


# =============================================================================
# LEGACY COMPATIBILITY (will be removed)
# =============================================================================

ANIMATOR_USER = CHOREOGRAPHY_USER  # Alias for backward compatibility
