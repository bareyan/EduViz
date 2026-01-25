# Visual Script Improvements - Time Variable System

## Overview

This document describes the major refactoring of the visual script generation system to address bugs related to timing, object lifecycle management, and code maintainability.

## Problems Identified

### Before Refactoring

1. **Hardcoded timestamps scattered everywhere**: Times like `0.0s`, `3.5s`, `8.2s` were embedded throughout the visual script and generated code, making adjustments difficult
2. **No centralized timing logic**: Each animation had inline time calculations
3. **Objects left on scene**: Poor tracking of object lifecycles led to overlaps and visual clutter
4. **Difficult debugging**: Hard to understand the timeline at a glance
5. **Time conflicts**: Easy to create overlapping animations or orphaned objects

### Example of Old Approach

**Old Visual Script (problematic):**
```markdown
### Objects:
| id | type | appear_at | hide_at |
|----|------|-----------|---------|
| title_1 | Text | 0.0s | 8.8s |
| eq_main | MathTex | 3.0s | end |

### Actions:
- [0.0s] Write(title_1) | run_time: 1.5s
- [3.0s] FadeIn(eq_main) | run_time: 1.0s
- [8.8s] FadeOut(title_1) | run_time: 0.5s
```

**Old Generated Code (problematic):**
```python
def construct(self):
    title = Text("Title")
    self.play(Write(title), run_time=1.5)
    self.wait(1.5)  # Magic number - where did this come from?
    
    eq = MathTex(r"E = mc^2")
    self.play(FadeIn(eq), run_time=1.0)
    self.wait(4.8)  # Another magic number
    
    self.play(FadeOut(title), run_time=0.5)
    # eq is still on screen - was it supposed to be removed?
```

**Problems:**
- Wait times are calculated inline and hard to verify
- No clear connection between visual script times and code
- Easy to lose track of what should be on screen when
- Adjusting one time requires recalculating many wait() calls

## New Approach: Time Variable System

### Key Innovations

1. **Semantic Time Variables**: Use meaningful names instead of numbers
   - `title_appear`, `title_hide` instead of `0.0s`, `8.8s`
   - `segment_1_begin`, `segment_1_end` instead of `0.0s`, `18.5s`
   - `diagram_build_start`, `diagram_build_end` instead of `20.0s`, `25.0s`

2. **Single Source of Truth**: All numeric times defined in ONE place at the bottom of visual script
   - Visual script uses variables throughout
   - At the end: TIME VARIABLE DEFINITIONS section with actual numbers
   - Easy to adjust - change one definition, everything updates

3. **Direct Python Translation**: Variables map 1:1 to Python code
   - Visual script: `title_appear`, `title_hide`
   - Python code: `title_appear = 0.0`, `title_hide = 8.8`
   - Same names, same semantics

4. **Calculated Wait Times**: Let Python do the math
   - Instead of: `self.wait(1.5)` (where did 1.5 come from?)
   - Use: `wait_time = eq_appear - (title_appear + title_write_duration)`
   - Self-documenting and verifiable

5. **Explicit Object Lifecycle**: REMOVAL SCHEDULE tracks when each object should be cleaned up
   - Lists all FadeOut times in chronological order
   - Groups objects by their hide_at time
   - Prevents object leaks and overlaps

## New Visual Script Format

### Structure with Time Variables

```markdown
---
VISUAL SCRIPT: Example Section
TOTAL DURATION: 54.5s
---

## SEGMENT 1: [segment_1_begin - segment_1_end]

### Narration Script:
```
[phrase_1_begin - phrase_1_end] "Hello everyone."
[phrase_2_begin - phrase_2_end] "Today we'll explore..."
```

### Objects:
| id | type | content | size | position | appear_at | hide_at |
|----|------|---------|------|----------|-----------|---------|
| title_main | Text | "Main Title" | 36 | (0, 3.2) | title_appear | title_hide |
| eq_intro | MathTex | "E = mc^2" | 0.7 | (0, 1.0) | eq_appear | eq_hide |
| diagram_1 | Circle | radius=0.5 | - | (2, 0) | diagram_appear | segment_2_begin |

### Actions:
- [title_appear] Write(title_main) | run_time: 1.5s
- [eq_appear] FadeIn(eq_intro) | run_time: 1.0s
- [diagram_appear] Create(diagram_1) | run_time: 0.8s
- [wait_segment_1] self.wait(X)s

---

## SEGMENT 2: [segment_2_begin - segment_2_end]

### Cleanup:
- [segment_2_begin] FadeOut(title_main, diagram_1) | run_time: 0.5s

### Objects:
| id | type | content | appear_at | hide_at |
|----|------|---------|-----------|---------|
| new_title | Text | "Part 2" | title_2_appear | end |

---

## TIME VARIABLE DEFINITIONS:
```python
# Segment boundaries
segment_1_begin = 0.0
segment_1_end = 18.5
segment_2_begin = 18.5
segment_2_end = 54.5

# Segment 1 events
title_appear = 0.0
title_hide = 18.5
phrase_1_begin = 0.0
phrase_1_end = 2.0
phrase_2_begin = 2.0
phrase_2_end = 5.5

eq_appear = 3.0
eq_hide = 25.0
diagram_appear = 8.0

wait_segment_1 = 10.0

# Segment 2 events
title_2_appear = 19.0

# Verify total
total_duration = 54.5
assert segment_2_end == total_duration
```

## REMOVAL SCHEDULE:
- [title_hide] FadeOut: title_main, diagram_1
- [eq_hide] FadeOut: eq_intro
- [end] Still visible: new_title
---
```

## New Python Code Structure

### Generated Manim Code with Time Variables

```python
def construct(self):
    # === THEME SETUP ===
    self.camera.background_color = BLACK
    
    # ═══════════════════════════════════════════════════════════
    # TIMING VARIABLES (extracted from visual script)
    # ═══════════════════════════════════════════════════════════
    # Segment boundaries
    segment_1_begin = 0.0
    segment_1_end = 18.5
    segment_2_begin = 18.5
    segment_2_end = 54.5
    
    # Event times
    title_appear = 0.0
    title_hide = 18.5
    eq_appear = 3.0
    eq_hide = 25.0
    diagram_appear = 8.0
    
    # Animation durations
    title_write_duration = 1.5
    eq_fade_duration = 1.0
    diagram_create_duration = 0.8
    
    # Calculated waits (self-documenting!)
    wait_after_title = eq_appear - (title_appear + title_write_duration)
    wait_after_eq = diagram_appear - (eq_appear + eq_fade_duration)
    wait_end_segment_1 = segment_1_end - (diagram_appear + diagram_create_duration)
    
    # Total duration
    total_duration = 54.5
    # ═══════════════════════════════════════════════════════════
    
    # === SEGMENT 1: Create Objects ===
    title_main = Text("Main Title", font_size=36).to_edge(UP, buff=0.8)
    eq_intro = MathTex(r"E = mc^2").scale(0.7).move_to(UP * 1.0)
    diagram_1 = Circle(radius=0.5).move_to(RIGHT * 2)
    
    # === SEGMENT 1: Animations ===
    self.play(Write(title_main), run_time=title_write_duration)
    self.wait(wait_after_title)  # Clear: waiting for next event
    
    self.play(FadeIn(eq_intro), run_time=eq_fade_duration)
    self.wait(wait_after_eq)  # Clear: waiting for diagram
    
    self.play(Create(diagram_1), run_time=diagram_create_duration)
    self.wait(wait_end_segment_1)  # Clear: holding until segment end
    
    # === TRANSITION TO SEGMENT 2 ===
    cleanup_duration = 0.5
    self.play(
        FadeOut(title_main, diagram_1),  # Following REMOVAL SCHEDULE
        run_time=cleanup_duration
    )
    
    # === SEGMENT 2: Create Objects ===
    new_title = Text("Part 2", font_size=36).to_edge(UP, buff=0.8)
    
    # === SEGMENT 2: Animations ===
    self.play(Write(new_title), run_time=1.0)
    
    # eq_intro is still on screen (not in cleanup list)
    # Continue with segment 2...
```

## Benefits

### 1. Readability & Maintainability
**Before:**
```python
self.wait(1.5)  # Why 1.5? Where did this come from?
```

**After:**
```python
wait_after_title = eq_appear - (title_appear + title_write_duration)
self.wait(wait_after_title)  # Clear: waiting from title end to eq start
```

### 2. Easy Timing Adjustments
**Before:** To move an event from 8.0s to 10.0s:
- Find all occurrences of 8.0s
- Recalculate every wait() that depends on it
- Update visual script manually
- Hope you didn't miss anything

**After:** To move an event:
- Change ONE line: `diagram_appear = 10.0`
- All waits automatically recalculate
- Visual script and code stay in sync

### 3. Object Lifecycle Tracking
**REMOVAL SCHEDULE** explicitly lists when objects are removed:
```markdown
## REMOVAL SCHEDULE:
- [title_hide] FadeOut: title_main, diagram_1
- [eq_hide] FadeOut: eq_intro
- [end] Still visible: new_title
```

Benefits:
- See at a glance what gets cleaned up when
- Prevents object leaks (objects staying on screen too long)
- Prevents overlaps (removing objects before new ones appear)
- Easy to verify all objects are accounted for

### 4. Timeline Verification
All times in one place → easy to verify:
```python
# Check: does segment_1_end equal segment_2_begin?
assert segment_1_end == segment_2_begin

# Check: is diagram_appear after eq_appear?
assert diagram_appear > eq_appear + eq_fade_duration

# Check: does everything fit in total_duration?
assert segment_2_end == total_duration
```

### 5. Self-Documenting Code
Variable names explain the intent:
- `title_appear` is clearer than `0.0`
- `cleanup_segment_1` is clearer than `18.5`
- `wait_after_eq` is clearer than `5.0`

## Implementation Details

### Changes to `prompts.py`

1. **`build_visual_script_prompt()`**:
   - Now instructs LLM to use time variables instead of hardcoded seconds
   - Requests TIME VARIABLE DEFINITIONS section at the bottom
   - Requests REMOVAL SCHEDULE for object cleanup tracking
   - Example format provided with variable names

2. **`build_code_from_script_prompt()`**:
   - Instructs LLM to extract time variables from visual script
   - Requires timing variables at START of construct()
   - Shows pattern for calculated wait times
   - Emphasizes using REMOVAL SCHEDULE for cleanup

### Backward Compatibility

The old system will continue to work for existing scripts, but:
- New generations will use time variables
- Regenerations will benefit from improved tracking
- Can manually convert old scripts by extracting times

## Examples

### Example 1: Simple Sequence

**Visual Script:**
```markdown
## TIME VARIABLE DEFINITIONS:
```python
intro_begin = 0.0
title_appear = 0.0
title_duration = 1.5
eq_appear = 2.0
eq_duration = 1.0
conclusion_appear = 5.0
intro_end = 8.0
```

**Generated Code:**
```python
# Timing variables
intro_begin = 0.0
title_appear = 0.0
title_duration = 1.5
eq_appear = 2.0
eq_duration = 1.0
conclusion_appear = 5.0
intro_end = 8.0

# Calculated waits
wait_before_eq = eq_appear - (title_appear + title_duration)
wait_before_conclusion = conclusion_appear - (eq_appear + eq_duration)
wait_to_end = intro_end - conclusion_appear

# Objects
title = Text("Title")
eq = MathTex(r"x^2 + y^2 = r^2")

# Animation
self.play(Write(title), run_time=title_duration)
self.wait(wait_before_eq)

self.play(FadeIn(eq), run_time=eq_duration)
self.wait(wait_before_conclusion)

conclusion = Text("Conclusion")
self.play(Write(conclusion))
self.wait(wait_to_end)
```

### Example 2: Complex Overlapping Animations

**Visual Script with REMOVAL SCHEDULE:**
```markdown
## TIME VARIABLE DEFINITIONS:
```python
segment_1_begin = 0.0
title_appear = 0.0
diagram_layer_1_appear = 2.0
diagram_layer_2_appear = 4.0
explanation_appear = 6.0

# Cleanup times
diagram_layer_1_hide = 8.0
title_hide = 10.0
segment_1_end = 10.0
```

## REMOVAL SCHEDULE:
- [diagram_layer_1_hide] FadeOut: diagram_layer_1
- [title_hide] FadeOut: title, diagram_layer_2
- [end] Still visible: explanation
```

**Generated Code:**
```python
# [Timing variables defined as above]

title = Text("Title")
diagram_layer_1 = Circle()
diagram_layer_2 = Square()
explanation = Text("Explanation")

# Segment 1
self.play(Write(title), run_time=1.5)
wait_1 = diagram_layer_1_appear - (title_appear + 1.5)
self.wait(wait_1)

self.play(Create(diagram_layer_1), run_time=1.0)
wait_2 = diagram_layer_2_appear - (diagram_layer_1_appear + 1.0)
self.wait(wait_2)

self.play(Create(diagram_layer_2), run_time=1.0)
wait_3 = explanation_appear - (diagram_layer_2_appear + 1.0)
self.wait(wait_3)

self.play(Write(explanation), run_time=1.0)
wait_4 = diagram_layer_1_hide - (explanation_appear + 1.0)
self.wait(wait_4)

# Cleanup per REMOVAL SCHEDULE
self.play(FadeOut(diagram_layer_1), run_time=0.5)
wait_5 = title_hide - (diagram_layer_1_hide + 0.5)
self.wait(wait_5)

self.play(FadeOut(title, diagram_layer_2), run_time=0.5)
# explanation stays on screen until end
```

## Testing & Validation

To verify the new system works correctly:

1. **Generate a new visual script**: Check that it uses variables throughout
2. **Check TIME VARIABLE DEFINITIONS**: Verify all variables are defined with numeric values
3. **Check REMOVAL SCHEDULE**: Verify all objects have a hide_at time or are listed as "still visible at end"
4. **Generate code**: Verify timing variables are at the top of construct()
5. **Run the animation**: Check that timing matches the visual script
6. **Verify object lifecycle**: No objects should linger or overlap unexpectedly

## Future Improvements

Potential enhancements:
1. **Automatic time conflict detection**: Warn if two objects overlap at the same position
2. **Timeline visualization**: Generate a visual timeline from the time variables
3. **Interactive timing editor**: GUI to adjust time variables and see impact
4. **Time variable templates**: Pre-defined patterns for common scenarios

## Conclusion

The time variable system addresses the root causes of timing bugs and object lifecycle issues:
- **Centralized timing** → easier to understand and adjust
- **Semantic naming** → self-documenting code
- **Explicit cleanup tracking** → no more object leaks
- **Calculated waits** → verifiable and maintainable

This refactoring significantly improves the quality and maintainability of generated animations while making debugging much easier.
