# Visual Quality Control - Implementation Summary

## Overview

Added an automatic visual quality control system that analyzes generated Manim videos at the section level using a local vision-capable LLM. The system detects visual issues (overlaps, off-screen elements, readability problems) and automatically generates fixed Manim code, then re-renders the section.

## What Was Added

### 1. New Service: `visual_qc.py`

**Location**: `backend/app/services/visual_qc.py`

**Main Components**:
- `VisualQualityController` class - Core QC engine
- `check_section_video()` function - Convenience wrapper
- Frame extraction using FFmpeg
- Vision LLM analysis using Ollama
- Fix generation for detected issues

**Key Methods**:
```python
- extract_keyframes() - Extract frames from video
- analyze_frames() - Analyze frames for issues
- generate_fix() - Generate fixed Manim code
- check_video_quality() - Complete workflow
```

**Supported Models** (via Ollama):
- `moondream` - Fastest (~2GB)
- `llama3.2-vision` - Balanced (recommended, ~8GB)
- `llava:13b` - More capable (~8GB)
- `minicpm-v` - Best quality (~16GB)

### 2. Integration into `manim_generator.py`

**Changes Made**:

1. **Imports**: Added visual QC import with availability check
2. **Class Variables**: Added QC configuration
3. **`__init__`**: Initialize QC controller
4. **`_render_scene`**: Added QC workflow after successful render

**QC Workflow** (integrated into rendering):
```
Render Manim Code
      ↓
Rendering Success?
      ↓ Yes
Extract Keyframes (5 frames)
      ↓
Analyze with Vision LLM
      ↓
Critical Issues Found?
      ↓ Yes
Generate Fixed Code
      ↓
Re-render Section
      ↓
Repeat (max 2 iterations)
```

**Configuration Options**:
```python
ENABLE_VISUAL_QC = True      # Enable/disable
QC_MODEL = "balanced"        # Model tier
MAX_QC_ITERATIONS = 2        # Max retries
```

### 3. Dependencies Added

**File**: `backend/requirements.txt`

Added:
```
ollama>=0.1.0  # Local LLM client
```

**External Requirements** (not in pip):
- Ollama (https://ollama.ai) - Runtime for local LLMs
- Vision model (e.g., `ollama pull llama3.2-vision`)

### 4. Documentation

Created three documentation files:

1. **`VISUAL_QC_README.md`** - Complete user guide
   - Setup instructions
   - Model options and comparison
   - Configuration guide
   - Troubleshooting
   - Architecture diagram

2. **`VISUAL_QC_CONFIG_EXAMPLES.md`** - Configuration cookbook
   - Example configurations for different use cases
   - Performance comparisons
   - Dynamic configuration patterns
   - Per-section configuration

3. **Updated `README.md`** - Added Visual QC to feature list and prerequisites

### 5. Test Script

**File**: `test_visual_qc.py`

Test suite with 4 tests:
1. Model availability check
2. Frame extraction test
3. Full QC workflow test
4. Fix generation test

**Usage**:
```bash
python test_visual_qc.py
```

## How It Works

### Section-Level Processing

Visual QC operates at the **section level**, not the entire video:

```
For each section:
  1. Generate Manim code (Gemini)
  2. Render video (Manim)
  3. ✨ Visual QC Check ✨
     - Extract 5 keyframes
     - Analyze with vision LLM
     - If critical issues found:
       → Generate fixed code
       → Re-render section
       → Check again (max 2 iterations)
  4. Continue to next section
```

### Visual Issues Detected

**Critical** (auto-fix triggered):
- Text overlapping with other elements
- Important content off-screen
- Unreadable text (too small, poor contrast)
- Crowded layouts with collision
- Severe positioning problems

**Moderate** (logged but not fixed):
- Minor timing issues
- Suboptimal colors
- Layout imbalance
- Visual clutter

### Fix Generation Process

When issues are detected:

1. **Analysis**: Vision LLM identifies specific problems
2. **Context**: Includes section info, original code, and issue descriptions
3. **Fix Prompt**: Detailed prompt with Manim best practices
4. **Code Generation**: LLM generates fixed code
5. **Validation**: Check code structure is valid
6. **Re-render**: Replace original code and render again

## Configuration

### Default Settings (Recommended)

```python
ENABLE_VISUAL_QC = True
QC_MODEL = "balanced"        # llama3.2-vision
MAX_QC_ITERATIONS = 2
```

### To Disable

```python
ENABLE_VISUAL_QC = False
```

Or uninstall Ollama, or don't pull a vision model.

### Model Selection

Based on your resources:

| Resources | Recommended Model |
|-----------|------------------|
| CPU only, limited RAM | `fastest` (moondream) |
| 8GB VRAM, balanced | `balanced` (llama3.2-vision) |
| 8GB+ VRAM, accuracy priority | `capable` (llava:13b) |
| 16GB+ VRAM, production | `best` (minicpm-v) |

## Performance Impact

### Overhead per Section

**No issues detected**:
- Frame extraction: ~1-2s
- Analysis: ~5-15s (model dependent)
- **Total**: ~6-17s per section

**Issues detected and fixed**:
- Fix generation: ~5-10s
- Re-render: ~30-120s
- QC again: ~6-17s
- **Total**: +45-150s per section

### When to Disable

- Running on very limited hardware (< 4GB RAM)
- Doing rapid iteration/testing
- Videos will be manually reviewed anyway
- Experiencing slowdowns

## Error Handling

The system is designed to **fail gracefully**:

- If Ollama not installed → QC disabled automatically
- If model not available → Skip QC, log warning
- If frame extraction fails → Skip QC for that section
- If analysis fails → Continue with original video
- If fix generation fails → Keep original video

**The pipeline never breaks due to QC failures**.

## Integration Points

### Where QC Runs

```
video_generator_v2.py
  → process_section()
    → manim_generator.generate_section_video()
      → _generate_manim_code()
      → _render_scene()  ← ✨ QC HAPPENS HERE ✨
        → [Manim renders video]
        → [QC checks video]
        → [Fix & re-render if needed]
      → return video_path
```

### Data Flow

```
Section Info → Manim Code → Rendered Video
                                  ↓
                            Extract Frames
                                  ↓
                          Analyze with LLM
                                  ↓
                         Issues Detected?
                           ↙         ↘
                        Yes           No
                         ↓             ↓
                   Generate Fix     Return Video
                         ↓
                   Update Code
                         ↓
                   Re-render
                         ↓
                   QC Again (max 2 total)
```

## Files Modified

1. `backend/app/services/manim_generator.py`
   - Added Visual QC import
   - Added QC configuration constants
   - Added QC initialization in `__init__`
   - Modified `_render_scene` to include QC workflow

2. `backend/requirements.txt`
   - Added `ollama>=0.1.0`

3. `README.md`
   - Added Visual QC to features list
   - Updated tech stack
   - Added Ollama to prerequisites
   - Updated project structure

## Files Created

1. `backend/app/services/visual_qc.py` - Core QC implementation
2. `VISUAL_QC_README.md` - User documentation
3. `VISUAL_QC_CONFIG_EXAMPLES.md` - Configuration cookbook
4. `test_visual_qc.py` - Test suite
5. `VISUAL_QC_IMPLEMENTATION.md` - This file

## Usage Example

### Basic Usage (Automatic)

Visual QC runs automatically during video generation if enabled:

```python
# In main.py or wherever videos are generated
result = await video_generator.generate_video(
    file_path=file_path,
    file_id=file_id,
    topic=topic,
    voice=voice,
    # QC runs automatically on each section
)
```

### Manual Testing

```python
from app.services.visual_qc import check_section_video

# Check a specific video
result = await check_section_video(
    video_path="outputs/job_123/sections/intro/section_0.mp4",
    section_info={
        "title": "Introduction",
        "narration": "This introduces the topic...",
        "visual_description": "Title and main equation"
    },
    model="balanced"
)

print(f"Status: {result['status']}")
if result['issues']:
    for issue in result['issues']:
        print(f"- {issue['type']}: {issue['description']}")
```

## Future Enhancements

Potential improvements for future versions:

1. **Temporal Analysis** - Analyze multiple frames for timing issues
2. **Custom Rules** - User-defined quality rules
3. **QC Reports** - Generate detailed reports with screenshots
4. **A/B Comparison** - Show before/after fixes
5. **Batch Processing** - Optimize for multiple sections
6. **GPU Optimization** - Better utilize GPU resources
7. **Fine-tuning** - Train on domain-specific issues
8. **Feedback Loop** - Learn from user corrections

## Testing

### Run the Test Suite

```bash
cd /path/to/manimagain
python test_visual_qc.py
```

### Manual Testing

1. Generate a video with intentional issues
2. Check logs for QC activity
3. Compare original vs fixed videos
4. Verify issues were addressed

### Expected Log Output

```
[ManimGenerator] Running Visual QC (iteration 1/2)...
[VisualQC] Checking quality of: section_0.mp4
[VisualQC] Extracted 5 frames
[VisualQC] Analysis complete: issues
[VisualQC] Found 2 issue(s)
[ManimGenerator] Found 1 critical visual issue(s)
[ManimGenerator] QC Description: Text overlapping with equation
[ManimGenerator] Applying visual QC fixes...
[ManimGenerator] Running Visual QC (iteration 2/2)...
[VisualQC] Analysis complete: ok
[ManimGenerator] Visual QC passed: Visuals are clear and well-organized
```

## Deployment Considerations

### Development

- Use `fastest` model for quick iterations
- Set `MAX_QC_ITERATIONS = 1`
- Consider disabling for draft videos

### Production

- Use `balanced` or better model
- Set `MAX_QC_ITERATIONS = 2`
- Ensure Ollama service is running
- Monitor QC logs for patterns
- Have fallback to manual review

### Docker

Add to `Dockerfile`:

```dockerfile
# Install Ollama (if using in container)
RUN curl -fsSL https://ollama.ai/install.sh | sh

# Pull vision model during build (optional)
RUN ollama pull llama3.2-vision
```

Or run Ollama as separate service:

```yaml
# docker-compose.yml
services:
  ollama:
    image: ollama/ollama
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
  
  backend:
    # ...
    environment:
      - OLLAMA_HOST=http://ollama:11434
```

## Conclusion

The Visual QC system provides automatic quality assurance for generated videos, operating at the section level to detect and fix visual issues before the final video is assembled. It uses local AI models for privacy and cost efficiency, with graceful degradation if unavailable.

**Key Benefits**:
- ✅ Automatic quality checks
- ✅ Self-healing (auto-fixes issues)
- ✅ Privacy-preserving (local processing)
- ✅ Cost-free (no API fees)
- ✅ Section-level granularity
- ✅ Fail-safe (never breaks pipeline)

**Trade-offs**:
- ⚠️ Adds processing time (5-150s per section)
- ⚠️ Requires additional resources (2-16GB)
- ⚠️ May have false positives/negatives
- ⚠️ Depends on local model quality
