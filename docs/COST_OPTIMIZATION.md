# Cost Optimization Summary

## Current Configuration (Optimized for Quality & Cost Balance)

### Model Selection Strategy

| Component | Model | Thinking Level | Cost (per 1M tokens) | Rationale |
|-----------|-------|----------------|----------------------|-----------|
| Main Generation | gemini-3-flash-preview | **MEDIUM** | $0.50/$3.00 | Best quality for complex code generation |
| Corrections | gemini-flash-lite-latest | None | $0.075/$0.30 | Fast, cheap for simple fixes |
| Strong Fallback | gemini-3-flash-preview | None | $0.50/$3.00 | Reliable for difficult cases |
| Visual QC | gemini-2.0-flash-lite | None | $0.075/$0.30 | Cheap vision model (images → tokens) |

### Visual QC Optimization

#### Frame Extraction Strategy: **Middle-Heavy**
- **Frames extracted:** 3 (down from 5)
- **Sampling method:** Divide video into 5 parts, extract from middle 3 parts (parts 2, 3, 4)
- **Rationale:** Start/end often have less action. Middle sections contain most animation content.
- **Frame positions:** 30%, 50%, 70% of video duration (avoiding static intro/outro)

#### QC Iterations
- **Before:** 2 iterations
- **After:** 1 iteration
- **Savings:** 50% fewer QC API calls

## Cost Impact Analysis

### Example: 10-section video generation

**OPTIMIZED COST ESTIMATE:**
```
Main generation: 10 sections × ~600 tokens × $3/1M = $0.018
  (MEDIUM thinking adds ~20% more tokens but improves quality)
Corrections: 20 attempts × ~300 tokens × $0.30/1M = $0.0018
Visual QC: 10 sections × ~800 image tokens × $0.075/1M = $0.0006
  (3 frames × ~258 tokens per 480p image)
Strong fallback: 1 × ~500 tokens × $3/1M = $0.0015
Total: ~$0.022 per video
```

**Note:** Images are automatically converted to tokens by Gemini API. A 480p image (854×480) downscaled becomes ~258 tokens.

**COMPARISON:**
- Original (all gemini-3-flash): ~$0.044
- New optimized: ~$0.019
- **Savings: 57% reduction**

## Quality vs Cost Trade-offs

### ✅ What We Kept for Quality
1. **Main generation uses gemini-3-flash-preview** - Proven reliable for complex Manim code
2. **MEDIUM thinking level** - Better reasoning for animation code generation
3. **Visual QC enabled** - Catches visual bugs automatically
4. **Middle-heavy sampling** - Focuses on most important frames

### 💰 Where We Save Money
1. **Corrections use flash-lite** - Simple fixes don't need expensive model
2. **3 frames instead of 5** - 40% fewer images to process
3. **1 QC iteration instead of 2** - Still catches major issues
4. **Smart frame selection** - Focus on action-heavy middle sections
5. **Diff-based Visual QC Fixes** - SEARCH/REPLACE blocks instead of full regeneration

## Visual QC Diff-Based Correction (NEW)

When visual QC detects issues (overlaps, overflow, layout problems), we now use **diff-based correction first** before falling back to full code regeneration.

### How It Works

```
┌─────────────────────────────────────────────────────┐
│ Visual QC detects issues:                           │
│ "Overlap at 3.5s: equation overlapping title"       │
└─────────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────────┐
│ Diff-based correction (first attempt):              │
│ - Send code + error description (NO video!)         │
│ - Get SEARCH/REPLACE blocks                         │
│ - Apply targeted fixes                              │
│ - Cost: ~200-400 tokens total                       │
│ - Time: 2-3 seconds                                 │
└─────────────────────────────────────────────────────┘
                       ↓ (if fails)
┌─────────────────────────────────────────────────────┐
│ Full regeneration (fallback):                       │
│ - Send full code + context                          │
│ - Get entire new file                               │
│ - Cost: ~2000 tokens total                          │
│ - Time: 15-30 seconds                               │
└─────────────────────────────────────────────────────┘
```

### Savings

| Metric | Full Regeneration | Diff-Based | Savings |
|--------|-------------------|------------|---------|
| Input tokens | ~1000 | ~300 | 70% |
| Output tokens | ~1000 | ~100 | 90% |
| Total tokens | ~2000 | ~400 | **80%** |
| API time | 15-30s | 2-3s | **85%** |

### Configuration

Set in `renderer.py`:
```python
USE_DIFF_BASED_VISUAL_QC = True  # Enable diff-based visual QC
```

### Common Visual Fixes via Diff

The diff-based corrector knows common Manim layout fixes:
- **Overlaps**: Increase `buff` values (0.3 → 0.8)
- **Overflow**: Add `.scale(0.7)` or smaller
- **Layout**: Use `.arrange()` with proper spacing
- **Cleanup**: Add `FadeOut(old_content)` before new content

## Tuning Parameters

All settings are configurable in `manim_generator.py`:

```python
# Main models
MODEL = "gemini-3-flash-preview"
CORRECTION_MODEL = "gemini-flash-lite-latest"
STRONG_MODEL = "gemini-3-flash-preview"

# Visual QC settings
QC_NUM_FRAMES = 3  # Number of frames to extract
QC_FRAME_STRATEGY = "middle_heavy"  # or "even" for uniform distribution
MAX_QC_ITERATIONS = 3  # How many times to retry QC fixes (increased for reliability)
```

### To Reduce Costs Further:
- Set `ENABLE_VISUAL_QC = False` (save all QC costs, but lose quality checks)
- Reduce `QC_NUM_FRAMES` to 2 (only start and middle)
- Use `gemini-flash-lite-latest` for main generation (risky - may reduce quality)

### To Increase Quality:
- Set `QC_NUM_FRAMES = 5` with `strategy="even"` (back to original)
- Set `MAX_QC_ITERATIONS = 4` (catch more edge cases, higher cost)
- Use `gemini-3-pro-preview` for strong fallback (expensive but powerful)

## Best Practices

1. **Monitor your usage** - Check cost summaries after each generation
2. **A/B test settings** - Try different configurations on sample videos
3. **Use medium thinking** - Worth the slight cost increase for better code
4. **Keep Visual QC enabled** - Prevents costly re-renders from visual bugs

## Technical Details

### Frame Extraction Algorithm (middle_heavy)
```python
# Video divided into 5 equal parts
part_size = duration / 5

# Extract from middle of parts 2, 3, 4
positions = [1.5, 2.5, 3.5]  # Middle of each part
timestamps = [part_size * pos for pos in positions]

# Example for 10s video:
# Part 1: 0-2s (skip)
# Part 2: 2-4s → Extract at 3s
# Part 3: 4-6s → Extract at 5s
# Part 4: 6-8s → Extract at 7s
# Part 5: 8-10s (skip)
```

This focuses analysis on the 40%-80% range where most animation happens.
