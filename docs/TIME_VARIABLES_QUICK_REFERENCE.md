# Visual Script Time Variables - Quick Reference

## Overview
The visual script system now uses **time variables** instead of hardcoded seconds, making timing easier to manage and debug.

## Key Concepts

### 1. Time Variables Replace Hardcoded Seconds

**Old (❌):**
```markdown
| id | appear_at | hide_at |
|----|-----------|---------|
| title | 0.0s | 8.8s |
| eq | 3.0s | end |
```

**New (✅):**
```markdown
| id | appear_at | hide_at |
|----|-----------|---------|
| title | title_appear | title_hide |
| eq | eq_appear | end |
```

### 2. All Times Defined At Bottom

The visual script defines ALL numeric values in a single section at the end:

```markdown
## TIME VARIABLE DEFINITIONS:
```python
# Segment boundaries
segment_1_begin = 0.0
segment_1_end = 18.5

# Event times
title_appear = 0.0
title_hide = 18.5
eq_appear = 3.0

# Total
total_duration = 54.5
```
```

### 3. Direct Translation to Python

Variables in visual script → Same variables in Python code:

**Visual Script:**
```markdown
[title_appear] Write(title) | run_time: 1.5s
```

**Generated Python:**
```python
title_appear = 0.0
title_write_duration = 1.5

self.play(Write(title), run_time=title_write_duration)
```

## Variable Naming Conventions

### Segment Boundaries
- `segment_1_begin`, `segment_1_end`
- `segment_2_begin`, `segment_2_end`
- `intro_begin`, `intro_end`
- `conclusion_begin`, `conclusion_end`

### Object Lifecycle
- `[object]_appear` - when object becomes visible
- `[object]_hide` - when object is removed
- Examples: `title_appear`, `diagram_hide`, `eq_appear`

### Animation Events
- `[action]_start`, `[action]_end`
- Examples: `transition_start`, `build_diagram_start`, `explanation_complete`

### Narration Timing
- `phrase_1_begin`, `phrase_1_end`
- `phrase_2_begin`, `phrase_2_end`

### Wait Points
- `wait_[description]`
- Examples: `wait_after_title`, `wait_for_emphasis`, `hold_final_state`

## Python Code Structure

### Required Order in construct()

```python
def construct(self):
    # 1. Theme setup
    self.camera.background_color = BLACK
    
    # 2. TIMING VARIABLES (ALL defined here!)
    segment_1_begin = 0.0
    title_appear = 0.0
    # ... all time variables
    
    # 3. CREATE OBJECTS (before using them)
    title = Text("Title")
    eq = MathTex(r"x^2")
    # ... all objects for this segment
    
    # 4. ANIMATE (using time variables)
    self.play(Write(title), run_time=1.5)
    self.wait(calculated_wait_time)
    # ... animations
    
    # 5. CLEANUP (using hide_at times)
    self.play(FadeOut(title, eq), run_time=0.5)
    
    # 6. NEXT SEGMENT (repeat 3-5)
```

## Calculated Wait Times

Instead of guessing wait times, calculate them:

```python
# Define events
title_appear = 0.0
title_write_duration = 1.5
eq_appear = 3.0
eq_fade_duration = 1.0
next_event = 8.0

# Calculate waits
wait_after_title = eq_appear - (title_appear + title_write_duration)
# wait_after_title = 3.0 - (0.0 + 1.5) = 1.5s

wait_after_eq = next_event - (eq_appear + eq_fade_duration)
# wait_after_eq = 8.0 - (3.0 + 1.0) = 4.0s

# Use in animation
self.play(Write(title), run_time=title_write_duration)
self.wait(wait_after_title)

self.play(FadeIn(eq), run_time=eq_fade_duration)
self.wait(wait_after_eq)
```

## Object Removal Schedule

Track when every object should be cleaned up:

```markdown
## REMOVAL SCHEDULE:
- [title_hide] FadeOut: title_main, subtitle
- [diagram_cleanup] FadeOut: circle_1, arrow_1, label_1
- [transition_to_next] FadeOut: example_box
- [end] Still visible: conclusion_text, final_equation
```

**Python Implementation:**
```python
# At title_hide time
self.play(FadeOut(title_main, subtitle), run_time=0.5)

# At diagram_cleanup time
self.play(FadeOut(circle_1, arrow_1, label_1), run_time=0.5)

# At transition_to_next time
self.play(FadeOut(example_box), run_time=0.5)

# conclusion_text and final_equation stay until end
```

## Common Patterns

### Pattern 1: Sequential Appearance

```python
# Variables
obj_1_appear = 0.0
obj_1_duration = 1.0
obj_2_appear = obj_1_appear + obj_1_duration + 0.5  # 0.5s gap
obj_2_duration = 1.0
obj_3_appear = obj_2_appear + obj_2_duration + 0.5

# Animation
self.play(FadeIn(obj_1), run_time=obj_1_duration)
self.wait(obj_2_appear - (obj_1_appear + obj_1_duration))

self.play(FadeIn(obj_2), run_time=obj_2_duration)
self.wait(obj_3_appear - (obj_2_appear + obj_2_duration))

self.play(FadeIn(obj_3), run_time=1.0)
```

### Pattern 2: Build and Hold

```python
# Variables
build_start = 2.0
build_duration = 3.0
build_end = build_start + build_duration
hold_duration = 4.0
cleanup_start = build_end + hold_duration

# Animation
self.play(Create(diagram), run_time=build_duration)
self.wait(hold_duration)  # Hold for narration
self.play(FadeOut(diagram), run_time=0.5)
```

### Pattern 3: Overlapping Transitions

```python
# Variables
old_content_hide = 8.0
hide_duration = 0.5
new_content_appear = old_content_hide + hide_duration
appear_duration = 1.0

# Animation - clean transition
self.play(FadeOut(old_content), run_time=hide_duration)
self.play(FadeIn(new_content), run_time=appear_duration)
```

### Pattern 4: Synchronized Multi-Object Cleanup

```python
# Variables
segment_1_end = 18.5
cleanup_duration = 0.5
segment_2_begin = segment_1_end + cleanup_duration

# Animation - clear everything at once
self.play(
    FadeOut(title, eq, diagram, arrow),
    run_time=cleanup_duration
)
# Now at segment_2_begin time
```

## Debugging Tips

### Verify Timeline Consistency

```python
# All times should be in order
assert title_appear < eq_appear < diagram_appear

# Segment boundaries should connect
assert segment_1_end == segment_2_begin

# Total should match
assert final_segment_end == total_duration
```

### Check for Time Conflicts

```python
# Object shouldn't hide before it appears
assert title_hide > title_appear

# Event should be after previous event + duration
assert eq_appear >= title_appear + title_write_duration

# Enough time for animation
assert cleanup_start - last_event >= last_animation_duration
```

### Print Timeline for Debugging

```python
print(f"Timeline:")
print(f"  title_appear: {title_appear}s")
print(f"  title_hide: {title_hide}s")
print(f"  eq_appear: {eq_appear}s")
print(f"  Total: {total_duration}s")
```

## Benefits Summary

✅ **Easy to adjust**: Change one variable, everything updates  
✅ **Self-documenting**: Variable names explain intent  
✅ **Verifiable**: Can check math and consistency  
✅ **No magic numbers**: Every time has a name and meaning  
✅ **Prevents conflicts**: Easy to see timeline at a glance  
✅ **Better debugging**: Clear where each time comes from  
✅ **Object lifecycle tracking**: Know exactly when to clean up  

## Migration from Old System

If you have old visual scripts with hardcoded times:

1. **Extract all unique times**: List every `X.Xs` value
2. **Create meaningful variables**: `0.0` → `intro_begin`, `8.8` → `segment_1_end`
3. **Replace throughout**: Update appear_at and hide_at columns
4. **Add TIME VARIABLE DEFINITIONS section**: Put all numeric values there
5. **Add REMOVAL SCHEDULE**: List all hide_at times in order
6. **Regenerate code**: Use new prompt templates

## Quick Checklist

When creating a visual script:
- [ ] Use time variables (not seconds) in all timing columns
- [ ] Include TIME VARIABLE DEFINITIONS section at bottom
- [ ] Include REMOVAL SCHEDULE section
- [ ] Verify all variables are defined
- [ ] Check that timeline is logical (times in order)
- [ ] Ensure every object has appear_at and hide_at

When generating Python code:
- [ ] Define all time variables at top of construct()
- [ ] Calculate wait times using variables
- [ ] Use variables in all self.wait() calls
- [ ] Follow REMOVAL SCHEDULE for FadeOut calls
- [ ] Verify total time equals target duration

---

**For more details, see:** `/docs/VISUAL_SCRIPT_IMPROVEMENTS.md`
