"""
Visual quality control prompts.

Used by: visual_qc.py
"""

from .base import PromptTemplate


VISUAL_QC_ANALYSIS = PromptTemplate(
    template="""Analyze this Manim animation for visual issues.

Section: {section_title}
Duration: {duration} seconds

Check for:
1. Overlapping text/elements
2. Off-screen content
3. Unclear animations
4. Timing issues

Report issues with timestamps and descriptions.""",
    description="Basic visual QC analysis"
)


VISUAL_QC_VIDEO_ANALYSIS = PromptTemplate(
    template="""Analyze this Manim educational animation video for PERSISTENT VISUAL ERRORS.

VIDEO CONTEXT:
- Section Title: "{section_title}"
- Total Duration: {duration:.1f} seconds
- Expected Content: {visual_description}

NARRATION TIMELINE (what should be shown when):
{segment_context}

## CRITICAL: ANIMATION-AWARE ANALYSIS

This is an ANIMATED video. Objects constantly fade in/out, move, transform, and transition.

**ONLY REPORT ERRORS THAT:**
1. Persist for AT LEAST 2 SECONDS in a STATIC state (not during animation)
2. Remain visible AFTER the animation/transition completes
3. Represent a final rendered state that is broken

**DO NOT REPORT:**
- Issues visible for only 1 frame during a transition
- Temporary overlaps that resolve as animation continues
- Brief edge proximity during movement
- Any issue that disappears when the animation settles

## ANALYSIS INSTRUCTIONS:
1. Watch the ENTIRE video carefully
2. When you see a potential issue, WAIT to see if it persists
3. If the issue resolves within 1-2 seconds (during animation), IGNORE IT
4. If the issue remains for 2+ seconds in a STATIC state, REPORT IT
5. Note BOTH the start_second AND end_second for each error
6. Set is_during_animation=true for any issue that only appears during transitions (these should NOT be in your final list)

## EXAMPLES:
- Text overlaps another element during FadeIn but separates when animation ends → IGNORE (transient)
- Text overlaps another element and stays overlapped for 5 seconds → REPORT (persistent)
- Equation briefly touches screen edge during Transform animation → IGNORE (transient)  
- Equation is cut off at screen edge for the rest of the video → REPORT (persistent)

REMEMBER: When in doubt, check if the issue persists in a "settled" state. Only report PERSISTENT issues.""",
    description="Analyze video for visual quality issues"
)
