# Visual QC Quick Start Guide

## 🚀 Get Started in 5 Minutes

### Step 1: Install Ollama

Choose your platform:

#### Linux
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

#### macOS
```bash
brew install ollama
```

#### Windows
Download from: https://ollama.ai/download

### Step 2: Install Python Package

```bash
cd /path/to/manimagain/backend
pip install ollama
```

### Step 3: Pull a Vision Model

```bash
# Recommended: Balanced speed and quality
ollama pull llama3.2-vision
```

**Done!** Visual QC is now active.

---

## 🧪 Test It

```bash
cd /path/to/manimagain
python test_visual_qc.py
```

Expected output:
```
✓ Model llama3.2-vision:latest is available
✓ Extracted 3 frames
✓ Analysis complete
```

---

## 🎬 Use It

Just generate a video normally - QC runs automatically!

```bash
# Start your backend
cd backend
uvicorn app.main:app --reload
```

Watch the logs for:
```
[ManimGenerator] Running Visual QC...
[VisualQC] Analysis complete: ok
```

---

## ⚙️ Configure (Optional)

Edit `backend/app/services/manim_generator.py`:

```python
class ManimGenerator:
    # Visual QC settings
    ENABLE_VISUAL_QC = True      # Set to False to disable
    QC_MODEL = "balanced"        # fastest/balanced/capable/best
    MAX_QC_ITERATIONS = 2        # 0-3
```

---

## 📊 Model Options

| Choose | If you have | Model to pull |
|--------|-------------|---------------|
| Fastest | CPU or < 4GB RAM | `ollama pull moondream` |
| Balanced ⭐ | 8GB+ VRAM | `ollama pull llama3.2-vision` |
| Best Quality | 16GB+ VRAM | `ollama pull minicpm-v` |

---

## 🔧 Troubleshooting

### "Model not available"
```bash
# Check what's installed
ollama list

# Pull the model
ollama pull llama3.2-vision
```

### "Ollama connection refused"
```bash
# Start Ollama service
ollama serve
```

### Out of Memory
```python
# Switch to smaller model
QC_MODEL = "fastest"  # Uses moondream (~2GB)
```

### Too Slow
```python
# Reduce iterations
MAX_QC_ITERATIONS = 1

# Or disable QC
ENABLE_VISUAL_QC = False
```

---

## 📚 Learn More

- Full guide: [`VISUAL_QC_README.md`](VISUAL_QC_README.md)
- Examples: [`VISUAL_QC_CONFIG_EXAMPLES.md`](VISUAL_QC_CONFIG_EXAMPLES.md)
- Architecture: [`VISUAL_QC_ARCHITECTURE.md`](VISUAL_QC_ARCHITECTURE.md)

---

## ✨ What You Get

✅ Automatic quality checks  
✅ Detects overlaps, off-screen content, readability issues  
✅ Auto-fixes and re-renders when needed  
✅ Local processing (no API calls)  
✅ Privacy-preserving  
✅ Cost-free  

---

## 💡 Tips

1. **First time?** Start with `balanced` model
2. **Limited resources?** Use `fastest` model
3. **Production?** Use `capable` or `best` model
4. **Testing?** Temporarily set `ENABLE_VISUAL_QC = False`
5. **GPU?** Makes everything much faster!

---

## 🎯 Example Session

```bash
# Install
curl -fsSL https://ollama.ai/install.sh | sh
pip install ollama
ollama pull llama3.2-vision

# Test
python test_visual_qc.py

# Generate video (QC runs automatically)
# ... normal video generation ...

# Check logs
[ManimGenerator] Running Visual QC (iteration 1/2)...
[VisualQC] Found 1 critical issue(s)
[ManimGenerator] Applying visual QC fixes...
[VisualQC] Analysis complete: ok
✓ Video approved
```

---

That's it! You're ready to generate high-quality videos with automatic visual QC.
