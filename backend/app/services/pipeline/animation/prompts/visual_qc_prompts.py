"""
Prompts for post-render visual quality control.
"""

VISION_QC_USER = """You are a visual QC inspector for educational animations.

Review each frame and report ONLY real visual defects that would harm learning quality.
Look for: clipped text, unreadable text, off-screen elements, text overlap, occlusion, low contrast,
misaligned labels, missing elements, or layout collisions.

Frame context:
{frame_context}

Return JSON with this exact shape:
{{
  "issues": [
    {{
      "frame": "<frame file name>",
      "time_sec": <timestamp as number>,
      "severity": "critical|warning|info",
      "confidence": "high|medium|low",
      "message": "Short, concrete defect description",
      "fix_hint": "Brief suggestion for how to fix"
    }}
  ]
}}

If no issues are found, return: {{"issues": []}}
"""
