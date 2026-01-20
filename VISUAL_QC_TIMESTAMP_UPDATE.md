# Visual QC Timestamp Enhancement

## Summary
Updated the Visual QC system to include timestamp information for detected issues and simplified the "OK" response format.

## Changes Made

### 1. Frame Extraction with Timestamps
**File**: `backend/app/services/visual_qc.py`

- Modified `extract_keyframes()` to return both frame paths and timestamps
- Return type changed from `List[str]` to `tuple[List[str], List[float]]`
- Timestamps are rounded to 2 decimal places for readability

```python
# Before
frame_paths = qc.extract_keyframes(video_path, num_frames=5)

# After
frame_paths, timestamps = qc.extract_keyframes(video_path, num_frames=5)
```

### 2. Timestamp-Aware Analysis
**File**: `backend/app/services/visual_qc.py`

- Updated `analyze_frames()` to accept timestamps parameter
- Prompt now includes frame information with timestamps:
  ```
  Frame 0: 1.5s into the video
  Frame 1: 3.2s into the video
  Frame 2: 5.8s into the video
  ```
- Issues now include `timestamps` field instead of `frame_indices`
- Model reports specific seconds where problems occur

### 3. Simplified "OK" Response
**File**: `backend/app/services/visual_qc.py`

When no issues are detected, the analyzer now returns:
```json
{
  "status": "ok",
  "issues": []
}
```

No description is included for OK status - just a clean, minimal response.

### 4. Enhanced Console Output
**File**: `backend/app/services/visual_qc.py`

Console output now shows timestamps:
```
[VisualQC] ✓ Extracted 5 frames at: 1.5s, 3.2s, 5.8s, 8.1s, 10.5s
[VisualQC] ✅ Visual QC passed - no issues detected

OR if issues:

[VisualQC] ⚠️ Found 2 issue(s):
  ❌ [overlap] at 1.5s, 3.2s: Title text overlaps with equation
  ⚠️ [positioning] at 5.8s: Diagram partially off-screen
```

### 5. Updated Fix Generation
**Files**: 
- `backend/app/services/visual_qc.py` (generate_fix method)
- `backend/app/services/manim_generator.py` (_generate_visual_fix method)

Issue descriptions passed to Gemini now include timestamps:
```
- [CRITICAL] overlap at 1.5s, 3.2s: Title text overlaps with equation
  Suggestion: Use .next_to() with proper buffer
```

This helps Gemini understand WHEN in the animation the problem occurs.

### 6. Updated Tests
**File**: `test_visual_qc.py`

Frame extraction test now displays timestamps:
```python
frame_paths, timestamps = qc.extract_keyframes(test_video, num_frames=3)
for i, (frame, ts) in enumerate(zip(frame_paths, timestamps)):
    print(f"  Frame {i} at {ts}s: {frame}")
```

## Benefits

✅ **Precise Error Location**: Know exactly when in the video issues occur  
✅ **Better Debugging**: Developers can jump to specific timestamps  
✅ **Cleaner OK Response**: No unnecessary description when everything is fine  
✅ **Improved Fix Generation**: Gemini gets temporal context for better fixes  
✅ **User-Friendly Output**: Clear console messages with timestamps

## Example Usage

```python
# Run QC on a video
qc = VisualQualityController(model="fastest")
result = await qc.check_video_quality(
    video_path="/path/to/video.mp4",
    section_info={"title": "Introduction", ...}
)

# Check results
if result["status"] == "ok":
    print("All good!")  # No description included
else:
    for issue in result["issues"]:
        timestamps = issue["timestamps"]  # e.g., [1.5, 3.2]
        print(f"Issue at {timestamps}s: {issue['description']}")
```

## Testing

Run the test suite to verify:
```bash
micromamba run -n manim python test_visual_qc.py
```

Expected output will include timestamp information in frame extraction test.
