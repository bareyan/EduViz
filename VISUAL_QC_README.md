# Visual Quality Control (QC) System

## Overview

The Visual QC system uses a local vision-capable LLM (Large Language Model) to automatically analyze generated Manim videos and detect visual issues such as:

- **Text overlaps** - Text overlapping with other text or equations
- **Off-screen elements** - Content cut off or outside the frame
- **Unreadable text** - Text too small, poor contrast, or blurry
- **Crowded layouts** - Too many elements squeezed together
- **Element collisions** - Shapes/diagrams overlapping inappropriately
- **Poor positioning** - Awkward placement or misalignment

When issues are detected, the system automatically generates fixed Manim code and re-renders the section.

## How It Works

1. **Video Generation** - Manim generates a video for a section
2. **Frame Extraction** - System extracts 5 keyframes from the video
3. **Visual Analysis** - Local LLM analyzes frames for visual issues
4. **Issue Detection** - Identifies critical and moderate issues
5. **Code Fixing** - If critical issues found, generates fixed Manim code
6. **Re-rendering** - Re-renders the video with fixes (up to 2 QC iterations)

## Setup

### 1. Install Ollama

Ollama is required to run local LLMs. Install it from https://ollama.ai

**Linux:**
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

**macOS:**
```bash
brew install ollama
```

**Windows:**
Download from https://ollama.ai/download

### 2. Install a Vision Model

Pull one of the supported vision models:

```bash
# Recommended: Balanced speed and capability
ollama pull llama3.2-vision

# Alternatives:
ollama pull moondream        # Fastest (~2GB)
ollama pull llava:13b        # More capable
ollama pull minicpm-v        # Best quality (~16GB)
```

### 3. Install Python Dependencies

```bash
pip install ollama
```

### 4. Enable Visual QC

Visual QC is **enabled by default** in the ManimGenerator. To configure:

Edit `backend/app/services/manim_generator.py`:

```python
class ManimGenerator:
    # Visual QC settings
    ENABLE_VISUAL_QC = True  # Set to False to disable
    QC_MODEL = "balanced"    # Options: fastest, balanced, capable, best
    MAX_QC_ITERATIONS = 2    # How many times to retry fixing
```

### 5. Start Ollama Service

Ensure Ollama is running:

```bash
# Check if running
ollama list

# If not running, start it (it usually auto-starts)
# On Linux/macOS:
systemctl start ollama  # or
# ollama serve
```

## Model Options

| Tier | Model | Size | Speed | Quality | Use Case |
|------|-------|------|-------|---------|----------|
| `fastest` | moondream | ~2GB | Very Fast | Good | Quick checks, limited VRAM |
| `balanced` | llama3.2-vision | ~8GB | Fast | Very Good | **Recommended** - Best balance |
| `capable` | llava:13b | ~8GB | Medium | Excellent | More detailed analysis |
| `best` | minicpm-v | ~16GB | Slower | Best | Highest quality, needs GPU |

## Configuration

### Changing the Model

In `manim_generator.py`:
```python
QC_MODEL = "fastest"  # Use fastest model
```

Or specify directly when initializing:
```python
from visual_qc import VisualQualityController
qc = VisualQualityController(model="llava:13b")
```

### Adjusting QC Iterations

```python
MAX_QC_ITERATIONS = 2  # 0-3 recommended
# 0 = No visual QC
# 1 = Check once, fix if needed
# 2 = Check twice (recommended)
# 3 = Check 3 times (may be overkill)
```

### Disabling Visual QC

```python
ENABLE_VISUAL_QC = False
```

Or uninstall ollama:
```bash
pip uninstall ollama
```

## Performance Impact

- **Frame Extraction**: ~1-2 seconds per video
- **Visual Analysis**: ~5-15 seconds depending on model
- **Code Fix Generation**: ~5-10 seconds
- **Re-rendering**: ~30-120 seconds if fixes needed

**Total overhead**: ~5-20 seconds per section (if no issues found)
**With fixes**: +45-150 seconds per section (only when critical issues detected)

## Example Output

```
[ManimGenerator] Running Visual QC (iteration 1/2)...
[VisualQC] Checking quality of: section_0.mp4
[VisualQC] Extracted 5 frames
[VisualQC] Analysis complete: issues
[VisualQC] Found 2 issue(s)
[ManimGenerator] Found 1 critical visual issue(s)
[ManimGenerator] QC Description: Text overlapping detected in title and equation
[ManimGenerator] Applying visual QC fixes...
[ManimGenerator] Running Visual QC (iteration 2/2)...
[VisualQC] Analysis complete: ok
[ManimGenerator] Visual QC passed: Visuals are clear and well-organized
```

## Troubleshooting

### "Model not available" Error

```bash
# Check installed models
ollama list

# Install the model
ollama pull llama3.2-vision
```

### Ollama Not Running

```bash
# Check if Ollama is accessible
curl http://localhost:11434/api/tags

# Start Ollama (if needed)
ollama serve
```

### Out of Memory (OOM) Errors

Use a smaller model:
```python
QC_MODEL = "fastest"  # Uses moondream (~2GB)
```

Or disable Visual QC:
```python
ENABLE_VISUAL_QC = False
```

### Slow Performance

- Use the `fastest` tier model
- Reduce MAX_QC_ITERATIONS to 1
- Ensure you have GPU acceleration (CUDA/Metal)

### False Positives

The model may occasionally flag non-issues. This is normal with AI systems. You can:
- Adjust the model tier (higher tier = more accurate)
- Review the video manually
- Disable QC for specific sections

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Video Generation Pipeline                                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Generate Manim Code (Gemini)                           │
│            ↓                                                │
│  2. Render Video (Manim)                                    │
│            ↓                                                │
│  3. ┌──────────────────────────────────┐                   │
│     │  VISUAL QUALITY CONTROL          │                   │
│     ├──────────────────────────────────┤                   │
│     │  • Extract keyframes (FFmpeg)    │                   │
│     │  • Analyze with Vision LLM       │                   │
│     │  • Detect visual issues          │                   │
│     │  • Generate fix if needed        │                   │
│     └──────────────────────────────────┘                   │
│            ↓                                                │
│     Issues found?                                           │
│            ├─ No → Continue                                 │
│            └─ Yes → Re-generate code and render            │
│                     (max 2 iterations)                      │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## API Usage

You can also use Visual QC programmatically:

```python
from app.services.visual_qc import check_section_video

# Quick check
result = await check_section_video(
    video_path="/path/to/video.mp4",
    section_info={
        "title": "Introduction",
        "narration": "This is the introduction...",
        "visual_description": "Show title and main equation"
    },
    model="balanced"
)

if result["status"] == "issues":
    print(f"Found {len(result['issues'])} issues")
    for issue in result["issues"]:
        print(f"- {issue['type']}: {issue['description']}")
```

## Benefits

✅ **Automatic Quality Assurance** - Catches visual issues automatically  
✅ **Fast Local Processing** - No API calls, runs on your hardware  
✅ **Privacy-Preserving** - All processing done locally  
✅ **Cost-Free** - No per-request costs unlike cloud APIs  
✅ **Self-Healing** - Automatically generates and applies fixes  
✅ **Section-Level** - Operates independently on each section  

## Limitations

⚠️ **GPU Recommended** - Faster with CUDA/Metal acceleration  
⚠️ **Model Accuracy** - May miss subtle issues or have false positives  
⚠️ **Processing Time** - Adds 5-150s per section depending on issues  
⚠️ **Memory Usage** - Requires 2-16GB depending on model  
⚠️ **Fix Success Rate** - Not all detected issues may be fixable automatically  

## Future Enhancements

- [ ] Multi-frame temporal analysis (detect timing issues)
- [ ] Custom issue detection rules
- [ ] QC report generation with screenshots
- [ ] A/B comparison before/after fixes
- [ ] User feedback loop for model improvement
- [ ] GPU optimization for batch processing
