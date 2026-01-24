# LLM Provider Configuration

## Overview

MathViz supports multiple LLM (Large Language Model) providers for generating video content. You can switch between providers based on your needs:

- **Ollama** (default): Local models - free, private, no API key needed
- **Gemini**: Google's cloud-based AI models with advanced features

## Quick Start

### Local Mode (Ollama) - Recommended for Development

1. Install Ollama from [ollama.com](https://ollama.com/)
2. Pull the required models:
   ```bash
   # DeepSeek R1 for general tasks
   ollama pull deepseek-r1:8b
   
   # Qwen 3 for code generation (Manim)
   ollama pull qwen3:8b
   ```
3. Start Ollama:
   ```bash
   ollama serve
   ```
4. Run the backend - it will auto-detect Ollama

### Cloud Mode (Gemini)

1. Get an API key from [Google AI Studio](https://aistudio.google.com/)
2. Set environment variables:
   ```bash
   export GEMINI_API_KEY="your-api-key-here"
   export LLM_PROVIDER="gemini"
   ```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | Provider to use: `gemini` or `ollama` | Auto-detect (Ollama if no Gemini key) |
| `GEMINI_API_KEY` | API key for Google Gemini | Required for Gemini |
| `OLLAMA_HOST` | Ollama server URL | `http://localhost:11434` |
| `ENABLE_VISUAL_QC` | Enable visual QC (Gemini only) | `false` |
| `ENABLE_TRANSLATION` | Enable translation features | `false` |

### Auto-Detection Priority

If `LLM_PROVIDER` is not explicitly set:
1. Use **Gemini** if `GEMINI_API_KEY` is set
2. Otherwise use **Ollama** (local models)

## Local Models (Ollama)

### Default Model Configuration

The local pipeline uses optimized smaller models:

| Task | Model | Description |
|------|-------|-------------|
| Analysis | `deepseek-r1:8b` | Document analysis and extraction |
| Script Generation | `deepseek-r1:8b` | Video script creation |
| Language Detection | `deepseek-r1:8b` | Quick language detection |
| **Manim Generation** | `qwen3:8b` | Animation code generation |
| Code Correction | `qwen3:8b` | Fix errors in Manim code |
| Manual Code Fix | `qwen3:8b` | User-requested fixes |

### Why These Models?

- **deepseek-r1:8b**: Great reasoning capabilities, efficient for general tasks
- **qwen3:8b**: Optimized for code generation, excellent for Manim/Python

### Hardware Requirements

- **Minimum**: 16GB RAM, CPU-only (slow but works)
- **Recommended**: 16GB+ VRAM GPU for faster inference
- **Optimal**: RTX 3090/4090 or equivalent

### Using Larger Models

For better quality output (if you have the hardware):

```bash
# Higher quality models
ollama pull deepseek-r1:14b
ollama pull qwen3:14b

# Highest quality (requires 32GB+ VRAM)
ollama pull deepseek-r1:32b
ollama pull qwen3:32b
```

Then update `backend/app/config/models.py` to use these models.

For video generation, we recommend:

- **gemma3:12b** - Best balance of speed and quality for most tasks
- **deepseek-r1:14b** - Excellent for code generation (Manim)
- **deepseek-r1:32b** - Highest quality, requires 32GB+ VRAM
- **qwen2.5-coder:14b** - Alternative for code-heavy tasks

## Gemini (Cloud)

### When to Use Gemini

- Production deployments requiring reliability
- Advanced features (thinking mode, video analysis)
- Multimodal capabilities (image understanding)

### Gemini Models

| Task | Model | Features |
|------|-------|----------|
| Analysis | `gemini-flash-lite-latest` | Fast, cheap |
| Script Generation | `gemini-3-flash-preview` | Thinking mode |
| Manim Generation | `gemini-3-pro-preview` | High quality + thinking |
| Code Correction | `gemini-flash-lite-latest` | Fast fixes |

## Deprecated Features

### Visual QC (DEPRECATED)

Visual Quality Control is **disabled by default** and considered deprecated.

**Reason**: Requires Gemini video analysis which is expensive and slow.
The QC loop added significant time to video generation without providing
consistent value.

**Status**: Code is maintained but not recommended for use.

To enable (not recommended):
```bash
export ENABLE_VISUAL_QC=true
export LLM_PROVIDER=gemini  # Required - Ollama cannot do video analysis
```

### Translation (NOT IN USE)

Translation features are **not currently used** in the pipeline.

**Reason**: The current pipeline does not include translation steps.
The translation service code is maintained for potential future use.

**Status**: Code exists but is not called by the main pipeline.

To enable for development:
```bash
export ENABLE_TRANSLATION=true
```

## Custom Configuration

### Modifying Models

Edit `backend/app/config/models.py` to customize models:

```python
# In OLLAMA_PIPELINE, change the manim_generation model:
manim_generation=ModelConfig(
    model_name="gemini-3-pro-preview",
    ollama_model="qwen3:14b",  # Use larger model
    thinking_level=ThinkingLevel.HIGH,
    description="Higher quality Manim generation"
),
```

### Using the LLM Service Directly

```python
from app.services.llm import get_llm_provider, LLMConfig

llm = get_llm_provider()
config = LLMConfig(model="qwen3:8b", temperature=0.7, max_tokens=4096)

response = await llm.generate("Your prompt here", config=config)
print(response.text)
```

## Troubleshooting

### Ollama Issues

| Issue | Solution |
|-------|----------|
| "Connection refused" | Run `ollama serve` |
| "Model not found" | Run `ollama pull <model>` |
| Slow responses | Use smaller model or enable GPU |
| Out of memory | Use smaller model (8b instead of 14b) |

### Gemini Issues

| Issue | Solution |
|-------|----------|
| "API key not configured" | Set `GEMINI_API_KEY` env var |
| Rate limiting | Switch to Ollama for dev |
| Quota exceeded | Wait or upgrade plan |

## Performance Tips

1. **Use GPU acceleration** for Ollama - 10x faster
2. **Smaller models first** - iterate faster during development
3. **Cache results** - avoid regenerating unchanged sections
4. **Batch requests** - when possible, combine prompts
