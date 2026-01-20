# Visual Quality Control Configuration Examples

## Example 1: Default Configuration (Balanced)

```python
# backend/app/services/manim_generator.py

class ManimGenerator:
    # ... other settings ...
    
    # Visual QC settings
    ENABLE_VISUAL_QC = True      # Enable QC
    QC_MODEL = "balanced"        # Use balanced model (llama3.2-vision)
    MAX_QC_ITERATIONS = 2        # Check twice if needed
```

**Use case**: Recommended for most users. Good balance of speed and accuracy.

## Example 2: Fast Mode (Minimal Overhead)

```python
class ManimGenerator:
    ENABLE_VISUAL_QC = True
    QC_MODEL = "fastest"         # Use moondream (~2GB, very fast)
    MAX_QC_ITERATIONS = 1        # Only check once
```

**Use case**: Limited resources, need fast generation, or running on CPU only.

## Example 3: High Quality (Maximum Accuracy)

```python
class ManimGenerator:
    ENABLE_VISUAL_QC = True
    QC_MODEL = "best"            # Use minicpm-v (~16GB, best quality)
    MAX_QC_ITERATIONS = 3        # Check up to 3 times
```

**Use case**: Production videos, have powerful GPU, accuracy is critical.

## Example 4: Disabled (Fastest Generation)

```python
class ManimGenerator:
    ENABLE_VISUAL_QC = False     # Skip all visual QC
    QC_MODEL = "balanced"
    MAX_QC_ITERATIONS = 0
```

**Use case**: Testing, development, or when visual issues are manually reviewed.

## Example 5: Custom Model

```python
class ManimGenerator:
    ENABLE_VISUAL_QC = True
    QC_MODEL = "llava:13b"       # Specific model name
    MAX_QC_ITERATIONS = 2
```

**Use case**: You've tested different models and prefer a specific one.

## Environment Variables Alternative

Instead of editing the code, you can use environment variables:

```bash
# .env file
ENABLE_VISUAL_QC=true
VISUAL_QC_MODEL=balanced
VISUAL_QC_MAX_ITERATIONS=2
```

Then in `manim_generator.py`:

```python
import os

class ManimGenerator:
    ENABLE_VISUAL_QC = os.getenv("ENABLE_VISUAL_QC", "true").lower() == "true"
    QC_MODEL = os.getenv("VISUAL_QC_MODEL", "balanced")
    MAX_QC_ITERATIONS = int(os.getenv("VISUAL_QC_MAX_ITERATIONS", "2"))
```

## Dynamic Configuration (Advanced)

Configure QC per video generation request:

```python
# In video_generator_v2.py

async def generate_video(
    self,
    file_path: str,
    file_id: str,
    topic: Dict[str, Any],
    voice: str = "en-US-GuyNeural",
    progress_callback: Optional[callable] = None,
    job_id: Optional[str] = None,
    video_mode: str = "comprehensive",
    style: str = "3b1b",
    language: str = "en",
    # NEW: Visual QC options
    enable_qc: bool = True,
    qc_model: str = "balanced",
    qc_max_iterations: int = 2
) -> Dict[str, Any]:
    """Generate video with configurable QC"""
    
    # Pass QC config to manim generator
    self.manim_generator.ENABLE_VISUAL_QC = enable_qc
    self.manim_generator.QC_MODEL = qc_model
    self.manim_generator.MAX_QC_ITERATIONS = qc_max_iterations
    
    # ... rest of generation ...
```

Then from API:

```python
# backend/app/main.py

@app.post("/generate")
async def generate_video(
    file_id: str = Form(...),
    topic_index: int = Form(...),
    voice: str = Form("en-US-GuyNeural"),
    enable_qc: bool = Form(True),          # NEW
    qc_model: str = Form("balanced"),      # NEW
    qc_iterations: int = Form(2)           # NEW
):
    # ...
    result = await video_generator.generate_video(
        file_path=file_path,
        file_id=file_id,
        topic=topic,
        voice=voice,
        enable_qc=enable_qc,
        qc_model=qc_model,
        qc_max_iterations=qc_iterations
    )
```

## Performance Comparison

| Configuration | Time/Section | Memory | Accuracy | Best For |
|--------------|--------------|--------|----------|----------|
| Disabled | +0s | 0 MB | - | Testing, drafts |
| Fastest (moondream) | +5-10s | 2 GB | Good | CPU, limited VRAM |
| Balanced (llama3.2) | +10-20s | 8 GB | Very Good | **Recommended** |
| Capable (llava:13b) | +15-30s | 8 GB | Excellent | High quality |
| Best (minicpm-v) | +20-40s | 16 GB | Best | Production |

*Times assume no issues found. Add +60-150s if fixes needed.*

## Troubleshooting Config

### Model Not Loading

```python
# Check which models are available
import subprocess
result = subprocess.run(["ollama", "list"], capture_output=True, text=True)
print(result.stdout)
```

### Out of Memory

```python
# Switch to smaller model
QC_MODEL = "fastest"  # Only 2GB
```

### False Positives

```python
# Increase to better model
QC_MODEL = "capable"  # More accurate

# Or disable for specific sections
# In section metadata:
section["skip_qc"] = True
```

Then in `manim_generator.py`:

```python
if section.get("skip_qc", False):
    print("[ManimGenerator] Skipping Visual QC for this section")
else:
    # Run normal QC
    ...
```

## Tips for Best Results

1. **Start with balanced**: Best for most use cases
2. **Use fastest for testing**: Speed up development iterations
3. **Enable QC for production**: Catch issues automatically
4. **Monitor logs**: Check what issues are detected
5. **Adjust iterations**: 2 is usually enough, 3+ may be overkill
6. **GPU recommended**: Makes all models much faster
7. **Fallback gracefully**: QC should never break the pipeline

## Per-Section Configuration

```python
# In script_generator_v2.py, add QC hints to sections

section = {
    "id": "intro",
    "title": "Introduction",
    "narration": "...",
    "visual_description": "...",
    # QC hints
    "qc_priority": "high",        # "low", "medium", "high"
    "qc_focus": ["overlap", "positioning"],  # Specific issues to check
    "skip_qc": False              # Override to skip this section
}
```

Then in visual QC analysis, prioritize accordingly.
