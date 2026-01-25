# Visual Script Reuse on Clean Retry

## Overview

This document explains how the system now reuses the same visual script when retrying failed animations, improving consistency and reducing costs.

## Problem

### Before This Change

When a Manim animation failed (syntax error, render error, etc.) and the system triggered a "clean retry", it would:

1. **Regenerate the visual script** from scratch (Shot 1)
2. Re-analyze the new visual script (Shot 1.5)
3. Generate new Manim code from the new visual script (Shot 2)
4. Render the new code

**Issues:**
- 🔴 **Inconsistency**: Each retry could produce a completely different animation
- 💰 **Extra cost**: Regenerating visual script uses expensive API calls
- ⏱️ **Time waste**: Visual script generation takes 30-60 seconds
- 🐛 **Harder debugging**: Can't compare retries since they're based on different plans

### Example of Old Behavior

**First attempt:**
- Visual script: "Show title, then equation x^2 + y^2 = r^2, then diagram"
- Error: Syntax error in MathTex

**Retry (old system):**
- NEW visual script: "Show equation first, then title with animation"
- Completely different approach!

## Solution

### Reuse Visual Script on Clean Retry

The visual script is now the **stable foundation** for all retry attempts.

**New behavior on clean retry:**
1. ♻️ **Reuse existing visual script** from file (no regeneration!)
2. Skip Shot 1.5 analysis (already done)
3. Generate NEW Manim code from the SAME visual script (Shot 2)
4. Render the new code

**Benefits:**
- ✅ **Consistency**: All retries implement the same visual plan
- ✅ **Cost savings**: Skip expensive visual script generation (~$0.10-0.30 per section)
- ✅ **Time savings**: Save 30-60 seconds per retry
- ✅ **Better debugging**: Easy to compare different code implementations of same plan
- ✅ **Predictable results**: Retries fix code bugs, not change the entire animation

## Implementation

### Code Changes

#### 1. Added `reuse_visual_script` Parameter

**File:** `backend/app/services/manim_generator/__init__.py`

```python
async def _generate_manim_code(
    self, 
    section: Dict[str, Any], 
    target_duration: float,
    output_dir: Optional[str] = None,
    section_index: int = 0,
    reuse_visual_script: bool = False  # NEW!
) -> Tuple[str, Optional[str]]:
```

#### 2. Logic to Load Existing Visual Script

**Before Shot 1:**
```python
visual_script = None

# Try to reuse existing visual script on clean retry
if reuse_visual_script and output_dir:
    script_file = Path(output_dir) / f"visual_script_{section_index}.md"
    if script_file.exists():
        print(f"[ManimGenerator] ♻️ Reusing existing visual script from {script_file}")
        with open(script_file, "r") as f:
            visual_script = f.read().strip()
        print(f"[ManimGenerator] Loaded existing visual script: {len(visual_script)} chars")

# Generate new visual script only if not reusing or file doesn't exist
if not visual_script:
    # ... generate new visual script
```

#### 3. Pass Flag on Clean Retry

**In `generate_section_video()`:**
```python
# On clean retry, reuse the existing visual script
reuse_visual_script = (clean_retry > 0)
manim_code, visual_script = await self._generate_manim_code(
    section, 
    target_duration, 
    output_dir=output_dir, 
    section_index=section_index,
    reuse_visual_script=reuse_visual_script  # Pass flag
)
```

### Flow Diagram

#### First Attempt (clean_retry = 0)

```
┌─────────────────────────────────────┐
│ 1. Generate Visual Script (Shot 1) │ 💰 $0.15
│    - Create detailed storyboard    │
│    - Define objects & timing       │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 2. Save visual_script_0.md          │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 3. Analyze Layout (Shot 1.5)       │ 💰 $0.02
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 4. Generate Manim Code (Shot 2)    │ 💰 $0.10
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 5. Render Animation                 │
└──────────────┬──────────────────────┘
               │
               ▼
           ❌ FAILS (syntax error)
```

#### Clean Retry (clean_retry = 1) - NEW BEHAVIOR

```
┌─────────────────────────────────────┐
│ 1. ♻️ Load visual_script_0.md      │ 💰 $0.00 (SAVED!)
│    (reuse_visual_script = True)    │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 2. ⏭️ Skip Analysis                 │ 💰 $0.00 (SAVED!)
│    (already done in first attempt) │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 3. Generate NEW Manim Code          │ 💰 $0.10
│    (Shot 2 with SAME visual script)│
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│ 4. Render Animation                 │
└──────────────┬──────────────────────┘
               │
               ▼
           ✅ SUCCESS!
```

**Cost Savings Per Retry:** ~$0.17 (57% reduction)  
**Time Savings Per Retry:** ~40 seconds

## Examples

### Example 1: Syntax Error Fix

**Visual Script (stays the same):**
```markdown
## SEGMENT 1: [segment_1_begin - segment_1_end]

### Objects:
| id | type | content | appear_at | hide_at |
|----|------|---------|-----------|---------|
| title | Text | "Introduction" | title_appear | title_hide |
| eq | MathTex | "E = mc^2" | eq_appear | end |

## TIME VARIABLE DEFINITIONS:
segment_1_begin = 0.0
title_appear = 0.0
eq_appear = 2.0
...
```

**First Attempt Code (has bug):**
```python
title = Text("Introduction", font_size=INVALID)  # ❌ INVALID is not defined
eq = MathTex(r"E = mc^2").scale(0.7)
```

**Retry Code (same visual script, fixed syntax):**
```python
title = Text("Introduction", font_size=36)  # ✅ Fixed!
eq = MathTex(r"E = mc^2").scale(0.7)
```

### Example 2: Layout Issue Fix

**Visual Script (stays the same):**
```markdown
### Objects:
| id | type | position | appear_at | hide_at |
|----|------|----------|-----------|---------|
| title | Text | (0, 3.2) | title_appear | end |
| list_items | VGroup | (0, 0) | items_appear | end |

## TIME VARIABLE DEFINITIONS:
title_appear = 0.0
items_appear = 2.0
```

**First Attempt Code (overflow issue):**
```python
title = Text("Very Long Title Here", font_size=48)  # ❌ Too large!
items = VGroup(*[Text(f"Item {i}", font_size=32) for i in range(10)])  # ❌ Too many!
```

**Retry Code (same visual script, better sizing):**
```python
title = Text("Very Long Title Here", font_size=36).scale_to_fit_width(10)  # ✅ Constrained!
items = VGroup(*[Text(f"Item {i}", font_size=24) for i in range(10)])
items.arrange(DOWN, buff=0.5).scale_to_fit_height(5.0)  # ✅ Constrained!
```

## Benefits Analysis

### Cost Savings

For a typical video with 10 sections:
- **Without visual script reuse:**
  - First attempts: 10 sections × $0.27 = $2.70
  - Retries (3 sections): 3 × $0.27 = $0.81
  - **Total: $3.51**

- **With visual script reuse:**
  - First attempts: 10 sections × $0.27 = $2.70
  - Retries (3 sections): 3 × $0.10 = $0.30
  - **Total: $3.00**
  - **Savings: $0.51 (15% reduction)**

### Time Savings

For 3 retries:
- **Without reuse:** 3 × 90 seconds = 270 seconds (4.5 minutes)
- **With reuse:** 3 × 50 seconds = 150 seconds (2.5 minutes)
- **Time saved: 120 seconds (2 minutes)**

### Quality Improvements

1. **Consistency**: All attempts implement the same plan
2. **Predictability**: Retries fix implementation, not change design
3. **Debugging**: Easy to identify if issue is in visual script vs code generation
4. **Stability**: Time variables remain consistent across retries

## Workflow Integration

### Decision Tree for Retry

```
Animation Failed?
       │
       ▼
   ┌───────┐
   │ Retry │
   └───┬───┘
       │
       ▼
Is visual_script_N.md present?
       │
       ├─ YES ─→ ♻️ Reuse it
       │          (clean_retry > 0)
       │
       └─ NO ──→ Generate new
                  (first attempt)
```

### File System State

**After first attempt:**
```
outputs/section_0/
  ├── visual_script_0.md         ← Saved here
  ├── visual_script_analysis_0.json
  ├── scene_0.py                 ← Generated code (attempt 1)
  └── videos/
```

**After retry:**
```
outputs/section_0/
  ├── visual_script_0.md         ← REUSED (not regenerated)
  ├── visual_script_analysis_0.json
  ├── scene_0.py                 ← NEW code (attempt 2)
  └── videos/
      └── scene_0.mp4            ← Success!
```

## Edge Cases

### Case 1: Visual Script File Missing

If `visual_script_0.md` is deleted or missing:
```python
if reuse_visual_script and output_dir:
    script_file = Path(output_dir) / f"visual_script_{section_index}.md"
    if script_file.exists():
        # Load it
    else:
        # Fall through to generation
```
**Result:** Gracefully falls back to generating new visual script

### Case 2: Corrupt Visual Script File

If file exists but is corrupt/empty:
```python
if not visual_script:  # Empty after loading
    # Generate new one
```
**Result:** Generates fresh visual script

### Case 3: First Attempt (No Retry)

```python
reuse_visual_script = (clean_retry > 0)  # False when clean_retry = 0
```
**Result:** Always generates new visual script on first attempt

## Future Enhancements

Potential improvements:

1. **Visual Script Versioning**: Save numbered versions on each retry
   - `visual_script_0_v1.md`, `visual_script_0_v2.md`, etc.
   - Track which version produced which code

2. **Smart Regeneration**: Detect if visual script itself is problematic
   - If 3+ retries fail with same visual script → regenerate it
   - Add parameter: `force_regenerate_visual_script`

3. **Cost Tracking**: Track savings from reuse
   - Add to stats: `visual_scripts_reused`, `cost_saved`

4. **Partial Reuse**: Reuse only the TIME VARIABLE DEFINITIONS
   - Keep timing stable but regenerate object descriptions

## Conclusion

Visual script reuse on clean retry:
- ✅ Maintains consistency across retry attempts
- ✅ Reduces costs by ~57% per retry
- ✅ Saves ~40 seconds per retry
- ✅ Makes debugging easier
- ✅ Provides stable foundation for code generation

This change ensures that retries focus on fixing **implementation bugs** (syntax, overflow, positioning) rather than changing the **creative vision** (object layout, timing, visual design).
