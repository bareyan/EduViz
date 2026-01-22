# Gemini API Cost Tracking

## Overview

The video generation system now tracks Gemini API token usage and calculates costs automatically.

## Features

- **Automatic tracking**: All Gemini API calls are tracked automatically
- **Per-model breakdown**: Shows costs for each model used (flash vs pro)
- **Real-time calculation**: Costs calculated based on current pricing
- **Console output**: Prints formatted summary at end of video generation

## Cost Summary Output

At the end of video generation, you'll see:

```
============================================================
💰 GEMINI API COST SUMMARY
============================================================
Total Input Tokens:  45,234
Total Output Tokens: 12,567
Total Tokens:        57,801

💵 Total Cost:        $0.0163

Breakdown by Model:
------------------------------------------------------------

gemini-3-flash-preview:
  Input:  42,000 tokens
  Output: 11,500 tokens
  Cost:   $0.0143

gemini-3-pro-preview:
  Input:  3,234 tokens
  Output: 1,067 tokens
  Cost:   $0.0020
============================================================
```

## Pricing (as of Jan 2026)

### Gemini Flash (gemini-3-flash-preview)
- Input: $0.075 per 1M tokens
- Output: $0.30 per 1M tokens
- **Used for**: Main code generation, corrections, visual fixes

### Gemini Pro (gemini-3-pro-preview)
- Input: $1.25 per 1M tokens
- Output: $5.00 per 1M tokens
- **Used for**: Final fix attempt when corrections fail

## Accessing Cost Data

### In Code

```python
from services.video_generator_v2 import VideoGenerator

generator = VideoGenerator(output_dir)
result = await generator.generate_video(...)

# Cost summary in result
cost_summary = result.get("cost_summary", {})
print(f"Total cost: ${cost_summary['total_cost_usd']}")
```

### Console Output

Cost summary is automatically printed at the end of video generation.

## Example Costs

**Short video (5 sections, ~5 min)**
- Input: ~30,000 tokens
- Output: ~8,000 tokens
- Cost: ~$0.01

**Medium video (15 sections, ~15 min)**
- Input: ~90,000 tokens
- Output: ~24,000 tokens
- Cost: ~$0.03

**Long video (30 sections, ~30 min with corrections)**
- Input: ~200,000 tokens
- Output: ~50,000 tokens
- Cost: ~$0.06-0.10

## Notes

- Costs are calculated using official Gemini API pricing
- Visual QC uses local Ollama (moondream) - **free, no API costs**
- Token counts include prompts and generated code
- Corrections and retries add to token usage
- Update pricing constants in `manim_generator.py` if rates change
