# 🚀 ManimagAin Quick Reference - Micromamba Setup

## Start the Server

```bash
# From the project root
./start_server.sh

# OR manually
cd backend
micromamba run -n manim uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Visual QC Status

✅ **Ollama**: Installed and running  
✅ **Python Package**: `ollama` installed in manim environment  
✅ **Vision Model**: `moondream` (~1.7GB) - fastest model  
✅ **Configuration**: Set to use `fastest` model in `manim_generator.py`  

## Test Visual QC

```bash
# From project root
python test_visual_qc.py
```

## Visual QC Configuration

Located in: `backend/app/services/manim_generator.py`

```python
class ManimGenerator:
    ENABLE_VISUAL_QC = True      # ✅ Enabled
    QC_MODEL = "fastest"         # Using moondream
    MAX_QC_ITERATIONS = 2        # Will retry twice if issues found
```

## Change Visual QC Model

If you want to use a different model later:

```bash
# Pull a different model
ollama pull llama3.2-vision    # Balanced (~8GB)
ollama pull llava:13b          # More capable (~8GB)
```

Then update `manim_generator.py`:
```python
QC_MODEL = "balanced"  # or "capable"
```

## Disable Visual QC

Edit `backend/app/services/manim_generator.py`:
```python
ENABLE_VISUAL_QC = False
```

## Server Access

- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Frontend**: http://localhost:3000 (if running)

## Useful Commands

```bash
# Check Ollama status
systemctl status ollama

# List installed models
ollama list

# Check micromamba environment
micromamba env list

# Install packages in manim env
micromamba run -n manim pip install <package>
```

## Visual QC in Action

When generating videos, you'll see logs like:

```
[ManimGenerator] Running Visual QC (iteration 1/2)...
[VisualQC] Checking quality of: section_0.mp4
[VisualQC] Extracted 5 frames
[VisualQC] Analysis complete: ok
[ManimGenerator] Visual QC passed
```

If issues are found:
```
[VisualQC] Found 1 critical issue(s)
[ManimGenerator] Applying visual QC fixes...
[ManimGenerator] Re-rendering section...
```

## Performance

- **Moondream (fastest)**: +5-10s per section (no issues)
- **With fixes**: +45-90s per section (when issues detected)
- **CPU mode**: May be slower (no GPU detected)

## Troubleshooting

### Ollama not running
```bash
sudo systemctl start ollama
```

### Model not found
```bash
ollama pull moondream
```

### Python package missing
```bash
micromamba run -n manim pip install ollama
```

### Disable for faster testing
```python
# In manim_generator.py
ENABLE_VISUAL_QC = False
```

## Documentation

- **Setup Guide**: `VISUAL_QC_README.md`
- **Quick Start**: `VISUAL_QC_QUICKSTART.md`
- **Config Examples**: `VISUAL_QC_CONFIG_EXAMPLES.md`
- **Full Index**: `VISUAL_QC_INDEX.md`

---

**Ready to use!** Visual QC will automatically check each generated video section.
