# Visual Comparison: Current vs Proposed Error Correction

## Current System: Full Code Regeneration

```
┌──────────────────────────────────────────────────────────────┐
│ Step 1: Error Occurs                                         │
├──────────────────────────────────────────────────────────────┤
│ Manim rendering fails with error:                            │
│ "NameError: name 'BOTTOM' is not defined"                    │
│ at line 45                                                    │
└──────────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────────┐
│ Step 2: Send ENTIRE Code to LLM                              │
├──────────────────────────────────────────────────────────────┤
│ Input Tokens: ~800-1200 tokens                               │
│                                                               │
│ from manim import *                                           │
│                                                               │
│ class Section_1(Scene):                                       │
│     def construct(self):                                      │
│         # Theme setup                                         │
│         camera.background_color = "#1e1e1e"                   │
│         ...                                                   │
│         # 40+ lines of code                                   │
│         ...                                                   │
│         text.to_edge(BOTTOM)  # ← ERROR on line 45           │
│         ...                                                   │
│         # Another 40+ lines                                   │
│         ...                                                   │
│                                                               │
│ + Error Message: "NameError: name 'BOTTOM' is not defined"   │
│ + Section context (narration, duration, etc.)                │
└──────────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────────┐
│ Step 3: LLM Regenerates ENTIRE Code                          │
├──────────────────────────────────────────────────────────────┤
│ Output Tokens: ~800-1200 tokens                              │
│                                                               │
│ from manim import *                                           │
│                                                               │
│ class Section_1(Scene):                                       │
│     def construct(self):                                      │
│         # Theme setup                                         │
│         camera.background_color = "#1e1e1e"                   │
│         ...                                                   │
│         # EXACT SAME 40+ lines                                │
│         ...                                                   │
│         text.to_edge(DOWN)  # ← FIXED (only change)          │
│         ...                                                   │
│         # EXACT SAME remaining 40+ lines                      │
│         ...                                                   │
│                                                               │
│ Time: 15-30 seconds                                           │
│ Cost: ~2,000 tokens total                                     │
└──────────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────────┐
│ Step 4: Replace Entire File & Re-render                      │
├──────────────────────────────────────────────────────────────┤
│ - Overwrite entire code file                                  │
│ - Re-render with Manim                                        │
│                                                               │
│ If still fails: Repeat 1-3 times max                          │
│ (Each iteration costs another 2,000 tokens + 15-30 seconds)  │
└──────────────────────────────────────────────────────────────┘

📊 CURRENT SYSTEM METRICS:
  • Tokens per attempt: ~2,000
  • Time per attempt: 15-30 seconds  
  • Max attempts: 1-3
  • Worst case total: 6,000 tokens, 90 seconds
  • Success rate: Limited by attempt count
```

---

## Proposed System: Diff-Based Targeted Fixes

```
┌──────────────────────────────────────────────────────────────┐
│ Step 1: Error Occurs                                         │
├──────────────────────────────────────────────────────────────┤
│ Manim rendering fails with error:                            │
│ "NameError: name 'BOTTOM' is not defined"                    │
│ at line 45                                                    │
└──────────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────────┐
│ Step 2: Parse Error & Extract Context                        │
├──────────────────────────────────────────────────────────────┤
│ Error Analyzer extracts:                                      │
│ • Error type: NameError                                       │
│ • Line number: 45                                             │
│ • Message: "BOTTOM is not defined"                            │
│ • Code context (lines 40-50):                                 │
│                                                               │
│   40:     title = Text("Introduction", font_size=72)         │
│   41:     self.play(Write(title))                             │
│   42:     self.wait(1)                                        │
│   43:                                                         │
│   44:     text = Text("Welcome", font_size=48)                │
│   45:     text.to_edge(BOTTOM)  # ← ERROR HERE               │
│   46:     self.play(FadeIn(text))                             │
│   47:     self.wait(2)                                        │
│   48:     self.play(FadeOut(text))                            │
│   49:                                                         │
│   50:     # Continue animation...                             │
└──────────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────────┐
│ Step 3: Send ONLY Context to LLM (Not Full Code!)            │
├──────────────────────────────────────────────────────────────┤
│ Input Tokens: ~150-250 tokens                                │
│                                                               │
│ Prompt:                                                       │
│ "Fix this Manim error with minimal targeted changes.         │
│                                                               │
│ ERROR: NameError - name 'BOTTOM' is not defined              │
│ LINE: 45                                                      │
│                                                               │
│ CODE CONTEXT (lines 40-50):                                   │
│ [... 11 lines of context shown above ...]                    │
│                                                               │
│ Return JSON with search-replace pairs to fix the error.      │
│ COMMON FIX: BOTTOM → DOWN (BOTTOM doesn't exist in Manim)"   │
└──────────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────────┐
│ Step 4: LLM Returns Targeted Fix (JSON)                      │
├──────────────────────────────────────────────────────────────┤
│ Output Tokens: ~80-150 tokens                                │
│                                                               │
│ {                                                             │
│   "analysis": "The constant BOTTOM doesn't exist in Manim.   │
│                Use DOWN instead for bottom edge positioning.",│
│   "fixes": [                                                  │
│     {                                                         │
│       "search": "        text.to_edge(BOTTOM)",               │
│       "replace": "        text.to_edge(DOWN)",                │
│       "line_hint": 45,                                        │
│       "reason": "BOTTOM constant undefined, use DOWN",        │
│       "confidence": 0.99                                      │
│     }                                                         │
│   ],                                                          │
│   "requires_full_rewrite": false                              │
│ }                                                             │
│                                                               │
│ Time: 2-5 seconds                                             │
│ Cost: ~250 tokens total                                       │
└──────────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────────┐
│ Step 5: Apply Fix Surgically                                 │
├──────────────────────────────────────────────────────────────┤
│ Fix Applicator:                                               │
│ 1. Find: "        text.to_edge(BOTTOM)"                      │
│ 2. Replace with: "        text.to_edge(DOWN)"                │
│ 3. Validate syntax (compile check)                            │
│ 4. If valid → Done! ✓                                         │
│    If invalid → Try next fix or fallback                      │
│                                                               │
│ Only line 45 changed. Rest of file untouched.                │
└──────────────────────────────────────────────────────────────┘
                           ↓
┌──────────────────────────────────────────────────────────────┐
│ Step 6: Re-render & Iterate If Needed                        │
├──────────────────────────────────────────────────────────────┤
│ - Re-render with fixed code                                   │
│ - If still fails: Repeat with new error                       │
│                                                               │
│ Can afford 5-10 attempts (cheap & fast!)                      │
│ If 5 diff attempts fail → Fallback to full regeneration      │
└──────────────────────────────────────────────────────────────┘

📊 PROPOSED SYSTEM METRICS:
  • Tokens per attempt: ~250 (8x reduction!)
  • Time per attempt: 2-5 seconds (6x faster!)
  • Max attempts: 5-10 (5x more attempts!)
  • Worst case total: 2,500 tokens, 50 seconds
  • Success rate: Higher (more attempts available)
  • Fallback: Can still do full regen if needed
```

---

## Side-by-Side Example

### Scenario: Fix 3 common errors in one section

#### Current System (Full Regeneration)
```
Attempt 1: BOTTOM → DOWN error
  ├─ Input: 1,000 tokens (full code + error)
  ├─ Output: 1,000 tokens (full regenerated code)
  ├─ Time: 20 seconds
  └─ Result: Fixed, but introduced new error (typo in color)

Attempt 2: Color typo "blue" → "BLUE"
  ├─ Input: 1,000 tokens (full code + error)
  ├─ Output: 1,000 tokens (full regenerated code)
  ├─ Time: 20 seconds
  └─ Result: Fixed, but now indentation error

Attempt 3: LIMIT REACHED - Use fallback scene
  └─ Result: ❌ Placeholder video (no real content)

TOTAL: 6,000 tokens, 40 seconds, FAILED ❌
```

#### Proposed System (Diff-Based)
```
Attempt 1: BOTTOM → DOWN error
  ├─ Input: 200 tokens (context + error)
  ├─ Output: 80 tokens (JSON fix)
  ├─ Time: 3 seconds
  └─ Result: ✓ Fixed

Attempt 2: Color typo "blue" → "BLUE"
  ├─ Input: 200 tokens (context + error)
  ├─ Output: 80 tokens (JSON fix)
  ├─ Time: 3 seconds
  └─ Result: ✓ Fixed

Attempt 3: Indentation error (hypothetical)
  ├─ Input: 200 tokens (context + error)
  ├─ Output: 80 tokens (JSON fix)
  ├─ Time: 3 seconds
  └─ Result: ✓ Fixed

Success! ✓ Video rendered correctly

TOTAL: 840 tokens, 9 seconds, SUCCESS ✓
Savings: 5,160 tokens (86%), 31 seconds (77%)
```

---

## Cost Comparison (Real Numbers)

Assuming Gemini Flash pricing:
- Input: $0.075 per 1M tokens
- Output: $0.30 per 1M tokens

### Current System (3 attempts, all fail)
```
Input:  3 × 1,000 tokens × $0.075/1M = $0.000225
Output: 3 × 1,000 tokens × $0.30/1M  = $0.000900
TOTAL: $0.001125 per failed section
Result: Fallback placeholder video
```

### Proposed System (3 attempts, all succeed)
```
Input:  3 × 200 tokens × $0.075/1M = $0.000045
Output: 3 × 80 tokens × $0.30/1M   = $0.000072
TOTAL: $0.000117 per successful section
Result: Proper rendered video
Savings: $0.001008 (90% cost reduction!)
```

### Scale Impact (100 sections with errors)
```
Current:  100 × $0.001125 = $0.1125 (many fallback videos)
Proposed: 100 × $0.000117 = $0.0117 (most render correctly)
SAVINGS: $0.1008 per 100 sections

For 10,000 videos/month: ~$10/month savings
For 100,000 videos/month: ~$100/month savings
```

**Plus**: Better video quality (fewer placeholders) = Happy users!

---

## Key Insights

### Why This Works for Manim Errors

1. **Errors are localized** 📍
   - Most errors affect 1-3 lines
   - Error messages include line numbers
   - Context (±5 lines) is sufficient

2. **Errors are repetitive** 🔁
   - BOTTOM/TOP → DOWN/UP (very common)
   - Color case errors (blue → BLUE)
   - MathTex backslash issues
   - Indentation problems

3. **LLMs are good at diffs** 🎯
   - Proven pattern (Cursor, Copilot, GitHub Copilot)
   - Structured output (JSON) is reliable
   - Can validate fixes before applying

4. **Safe fallback exists** 🛡️
   - If diff fails → use current full regen
   - No worse than current system
   - Progressive enhancement

### Why Current System Struggles

1. **Wasteful regeneration** 💸
   - Regenerates 99% unchanged code
   - LLM must "remember" entire structure
   - High token cost for tiny fixes

2. **Limited attempts** 🚫
   - Only 1-3 attempts affordable
   - Complex errors need iteration
   - Often gives up too early

3. **Slow iteration** ⏱️
   - 15-30 seconds per attempt
   - Blocks pipeline progress
   - User waits longer

---

## Conclusion

✅ **Diff-based correction is clearly superior for this use case**

The math is compelling:
- **8-10x cheaper** per fix
- **5-6x faster** per fix  
- **5x more** retry attempts
- **Higher success** rate overall
- **Better UX** (fewer placeholder videos)

**Recommendation**: Implement hybrid system (diff-first, full-regen fallback)
**Timeline**: 3-4 weeks for full implementation
**Risk**: Low (has fallback to current system)
**ROI**: High (pays for itself in 2-3 weeks)
