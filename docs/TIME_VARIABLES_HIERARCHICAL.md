# Hierarchical Time Variables - Segment Duration Based

## Overview

Time variables are now calculated **hierarchically** based on segment durations, making timing adjustments much more intuitive and preventing conflicts.

## Hierarchy Structure

```
Segment Durations (TOP LEVEL - primary control)
    ↓
Segment Boundaries (calculated from durations)
    ↓
Event Times (relative to segment boundaries)
    ↓
Wait Times (calculated from events)
```

## Example

### Visual Script Time Definitions

```python
# ═══════════════════════════════════════════════════════════════
# LEVEL 1: SEGMENT DURATIONS (adjust these to change pacing)
# ═══════════════════════════════════════════════════════════════
segment_1_duration = 18.5  # Introduction
segment_2_duration = 23.0  # Main content
segment_3_duration = 13.0  # Conclusion

# Verify total
total_duration = 54.5
assert segment_1_duration + segment_2_duration + segment_3_duration == total_duration

# ═══════════════════════════════════════════════════════════════
# LEVEL 2: SEGMENT BOUNDARIES (calculated from durations)
# ═══════════════════════════════════════════════════════════════
segment_1_begin = 0.0
segment_1_end = segment_1_begin + segment_1_duration  # = 18.5

segment_2_begin = segment_1_end  # = 18.5
segment_2_end = segment_2_begin + segment_2_duration  # = 41.5

segment_3_begin = segment_2_end  # = 41.5
segment_3_end = segment_3_begin + segment_3_duration  # = 54.5

# ═══════════════════════════════════════════════════════════════
# LEVEL 3: EVENT TIMES (relative to segment boundaries)
# ═══════════════════════════════════════════════════════════════

# Segment 1 events
title_appear = segment_1_begin + 0.0      # = 0.0
title_hide = segment_1_end                # = 18.5

eq_appear = segment_1_begin + 3.0         # = 3.0
eq_hide = segment_2_begin + 6.5           # = 25.0 (stays into segment 2)

diagram_appear = segment_1_begin + 8.0    # = 8.0
diagram_hide = segment_1_end              # = 18.5

# Segment 2 events
new_title_appear = segment_2_begin + 0.5  # = 19.0
bullet_1_appear = segment_2_begin + 2.0   # = 20.5
bullet_2_appear = bullet_1_appear + 1.5   # = 22.0
bullet_3_appear = bullet_2_appear + 1.5   # = 23.5

# Segment 3 events
conclusion_appear = segment_3_begin + 1.0 # = 42.5
```

### Generated Python Code

```python
def construct(self):
    # ═══════════════════════════════════════════════════════════════
    # TIMING VARIABLES
    # ═══════════════════════════════════════════════════════════════
    
    # Segment durations (PRIMARY CONTROL)
    segment_1_duration = 18.5
    segment_2_duration = 23.0
    segment_3_duration = 13.0
    
    total_duration = 54.5
    
    # Segment boundaries (calculated)
    segment_1_begin = 0.0
    segment_1_end = segment_1_begin + segment_1_duration
    segment_2_begin = segment_1_end
    segment_2_end = segment_2_begin + segment_2_duration
    segment_3_begin = segment_2_end
    segment_3_end = segment_3_begin + segment_3_duration
    
    # Event times (relative to segments)
    title_appear = segment_1_begin + 0.0
    eq_appear = segment_1_begin + 3.0
    diagram_appear = segment_1_begin + 8.0
    
    new_title_appear = segment_2_begin + 0.5
    bullet_1_appear = segment_2_begin + 2.0
    
    # Animation durations
    title_write_duration = 1.5
    eq_fade_duration = 1.0
    
    # Calculated waits
    wait_after_title = eq_appear - (title_appear + title_write_duration)
    wait_after_eq = diagram_appear - (eq_appear + eq_fade_duration)
    # ═══════════════════════════════════════════════════════════════
    
    # ... rest of animation code
```

## Benefits

### 1. Intuitive Adjustments

**Want to make segment 1 longer?**
```python
# Old way: manually adjust 20+ time values
title_appear = 0.0
eq_appear = 3.0      # needs manual adjustment
diagram_appear = 8.0 # needs manual adjustment
segment_1_end = 18.5 # needs manual adjustment
segment_2_begin = 18.5  # needs manual adjustment
# ... many more

# New way: change ONE value
segment_1_duration = 22.0  # increased from 18.5
# Everything else recalculates automatically!
```

### 2. Clear Relationships

```python
# Old way - unclear relationships
eq_appear = 3.0        # 3 seconds from what?
bullet_1_appear = 20.5 # Why 20.5?

# New way - self-documenting
eq_appear = segment_1_begin + 3.0      # 3 seconds into segment 1
bullet_1_appear = segment_2_begin + 2.0 # 2 seconds into segment 2
```

### 3. Prevents Timing Conflicts

```python
# Segment boundaries automatically align
segment_1_end = segment_1_begin + segment_1_duration
segment_2_begin = segment_1_end  # Guaranteed to match!

# Can't accidentally have gaps or overlaps
```

### 4. Easy Validation

```python
# Verify segments sum correctly
total = segment_1_duration + segment_2_duration + segment_3_duration
assert total == 54.5, f"Timeline error: {total} != 54.5"

# Verify event is within segment
assert segment_1_begin <= eq_appear < segment_1_end, "eq_appear outside segment 1"
```

### 5. Independent Segment Pacing

```python
# Speed up segment 2 without affecting others
segment_2_duration = 18.0  # reduced from 23.0

# All segment 2 events stay in the same relative positions
# Segments 1 and 3 are unaffected
```

## Comparison: Old vs New

### Old Approach (Flat)

```python
# All times as independent values - hard to understand relationships
segment_1_begin = 0.0
segment_1_end = 18.5
segment_2_begin = 18.5
segment_2_end = 41.5

title_appear = 0.0
eq_appear = 3.0
diagram_appear = 8.0
title_hide = 18.5

new_title_appear = 19.0
bullet_1_appear = 20.5
bullet_2_appear = 22.0
```

**Problems:**
- ❌ Hard to see relationships
- ❌ Adjusting segment duration requires updating many values
- ❌ Easy to create conflicts (e.g., segment_1_end != segment_2_begin)
- ❌ Can't quickly verify timeline is valid

### New Approach (Hierarchical)

```python
# Level 1: Durations (single source of truth for pacing)
segment_1_duration = 18.5
segment_2_duration = 23.0

# Level 2: Boundaries (calculated)
segment_1_begin = 0.0
segment_1_end = segment_1_begin + segment_1_duration
segment_2_begin = segment_1_end
segment_2_end = segment_2_begin + segment_2_duration

# Level 3: Events (relative to segments)
title_appear = segment_1_begin + 0.0
eq_appear = segment_1_begin + 3.0
diagram_appear = segment_1_begin + 8.0

new_title_appear = segment_2_begin + 0.5
bullet_1_appear = segment_2_begin + 2.0
bullet_2_appear = bullet_1_appear + 1.5
```

**Benefits:**
- ✅ Clear hierarchy and relationships
- ✅ Change duration → everything recalculates
- ✅ Impossible to have misaligned boundaries
- ✅ Easy to validate (assert sum of durations == total)

## Real-World Example

### Scenario: Speed Up Middle Section

**Requirement:** "Make the main content section 5 seconds shorter"

**Old way:**
```python
# Find all affected times (15+ variables)
segment_2_begin = 18.5
segment_2_end = 36.5  # was 41.5, reduced by 5
segment_3_begin = 36.5  # was 41.5, must update
segment_3_end = 49.5  # was 54.5, must update

# Update all segment 2 events? No! They stay the same
# But must verify nothing breaks...

# Update all segment 3 events? 
conclusion_appear = 37.5  # was 42.5, subtract 5
final_text_appear = 40.0  # was 45.0, subtract 5
# ... many more
```

**New way:**
```python
# Change ONE line
segment_2_duration = 18.0  # was 23.0, reduced by 5

# Done! Everything else recalculates:
# - segment_2_end = segment_2_begin + 18.0
# - segment_3_begin = segment_2_end (auto-updates)
# - segment_3_end = segment_3_begin + segment_3_duration (auto-updates)
# - All segment 2 events stay relative (no changes needed)
# - All segment 3 events stay relative (no changes needed)
```

## Best Practices

### 1. Group by Segment

```python
# Good: organized by segment
# Segment 1 events
title_appear = segment_1_begin + 0.0
eq_appear = segment_1_begin + 3.0

# Segment 2 events  
new_title_appear = segment_2_begin + 0.5
bullet_1_appear = segment_2_begin + 2.0
```

### 2. Use Relative Offsets

```python
# Good: relative to segment boundary
eq_appear = segment_1_begin + 3.0

# Bad: absolute time (breaks if segment moves)
eq_appear = 3.0
```

### 3. Chain Related Events

```python
# Good: events that follow each other
bullet_1_appear = segment_2_begin + 2.0
bullet_2_appear = bullet_1_appear + 1.5
bullet_3_appear = bullet_2_appear + 1.5

# Adjusting bullet_1_appear automatically shifts 2 and 3
```

### 4. Use Segment Boundaries for Cleanup

```python
# Good: cleanup at segment boundaries
title_hide = segment_1_end
diagram_hide = segment_1_end

# If segment_1_duration changes, cleanup times adjust automatically
```

### 5. Add Validation

```python
# Verify timeline adds up
total_calculated = sum([
    segment_1_duration,
    segment_2_duration,
    segment_3_duration
])
assert abs(total_calculated - total_duration) < 0.1, "Timeline mismatch"

# Verify events are in bounds
assert segment_1_begin <= eq_appear < segment_1_end
assert segment_2_begin <= bullet_1_appear < segment_2_end
```

## Migration Guide

### From Old to New

**Step 1: Extract durations**
```python
# Old
segment_1_end = 18.5

# Calculate duration
segment_1_duration = segment_1_end - segment_1_begin  # = 18.5
```

**Step 2: Calculate boundaries**
```python
# Replace
segment_1_end = 18.5
segment_2_begin = 18.5

# With
segment_1_end = segment_1_begin + segment_1_duration
segment_2_begin = segment_1_end
```

**Step 3: Make events relative**
```python
# Replace
eq_appear = 3.0

# With
eq_appear = segment_1_begin + 3.0
```

## Conclusion

Hierarchical time variables based on segment durations provide:
- 🎯 **Intuitive control** - adjust pacing at the segment level
- 🔗 **Clear relationships** - see how times depend on each other
- 🛡️ **Prevents conflicts** - boundaries automatically align
- ✅ **Easy validation** - verify timeline integrity
- ⚡ **Quick adjustments** - change one duration, everything updates

This approach transforms timing from a fragile collection of magic numbers into a robust, self-documenting system.
