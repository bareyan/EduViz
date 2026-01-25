# Pipeline Optimization Recommendations

## Executive Summary

After analyzing the complete video generation pipeline, I've identified **7 major optimization opportunities** that can reduce LLM costs by **40-60%** without significantly impacting quality. The key insight is that **full documents are being passed multiple times** when only relevant excerpts are needed.

---

## Current Pipeline Analysis

### Token Usage Flow (per video generation)

| Stage | Model | Content Passed | Est. Tokens | Cost Impact |
|-------|-------|----------------|-------------|-------------|
| Analysis | gemini-3-flash | Full document (up to 20K chars) | ~5K input | Low |
| **Phase 1: Outline** | gemini-3-flash | Full document (up to 60K chars) | **~15K input** | **HIGH** |
| **Phase 2: Sections (×N)** | gemini-3-flash | Document excerpt (25-35K chars) + outline + previous sections | **~8K × N input** | **VERY HIGH** |
| Visual Script (×N) | gemini-3-flash | Section narration + timing | ~2K × N | Medium |
| Visual Analysis (×N) | gemini-flash-lite | Visual script | ~1K × N | Low |
| Manim Code (×N) | gemini-3-flash | Visual script + narration | ~3K × N | Medium |
| Corrections | gemini-flash-lite | Code + error | ~1K per correction | Low |

**Problem:** For a 10-section video from a 20-page document:
- Phase 1: 15K tokens
- Phase 2: 80K tokens (8K × 10 sections, each getting 25-35K chars of document)
- Visual generation: 60K tokens (6K × 10 sections)
- **Total: ~155K input tokens = ~$0.08 just for input**

---

## Optimization Recommendations

### 1. 📄 **Document Chunking for Section Generation** (HIGH IMPACT - 50% reduction in Phase 2)

**Current State:**
```python
# script_generator.py line 536
content_limit = 25000  # Reduced from 40000
content_excerpt = content[:content_limit]
```

Every section gets the same 25K character excerpt from the START of the document, regardless of which part of the outline that section covers.

**Proposed Solution:** Extract **only the relevant portion** of the document for each section based on the outline's `content_to_cover` field.

```python
async def _get_relevant_content_for_section(
    self, 
    content: str, 
    section_outline: Dict[str, Any],
    full_outline: Dict[str, Any]
) -> str:
    """Extract only the portion of the document relevant to this section.
    
    Uses semantic matching or keyword extraction to find relevant content.
    Falls back to proportional slicing if no matches found.
    """
    section_idx = section_outline.get('id', '')
    content_to_cover = section_outline.get('content_to_cover', '')
    key_points = section_outline.get('key_points', [])
    
    # Extract keywords from section description
    keywords = self._extract_keywords(content_to_cover, key_points)
    
    # Find paragraphs containing these keywords
    relevant_chunks = self._find_relevant_chunks(content, keywords, max_chars=8000)
    
    if relevant_chunks:
        return relevant_chunks
    
    # Fallback: Use proportional slicing based on section position
    total_sections = len(full_outline.get('sections_outline', []))
    section_num = int(section_idx.split('_')[-1]) if '_' in section_idx else 0
    
    # Divide document into chunks per section
    chunk_size = len(content) // max(1, total_sections)
    start = max(0, (section_num - 1) * chunk_size)  # Include some overlap
    end = min(len(content), (section_num + 2) * chunk_size)
    
    return content[start:end][:10000]  # Max 10K chars per section
```

**Estimated Savings:** 50% reduction in Phase 2 tokens (8K → 4K per section)

---

### 2. 🔄 **Cache Document Analysis Results** (MEDIUM IMPACT)

**Current State:** Document is re-read and re-analyzed even when generating multiple videos from the same source.

**Proposed Solution:** Cache the Phase 1 outline based on document hash.

```python
import hashlib
from pathlib import Path

class ScriptGenerator:
    CACHE_DIR = Path("./cache/outlines")
    
    def _get_outline_cache_key(self, content: str, video_mode: str, language: str) -> str:
        """Generate cache key from content hash and parameters."""
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        return f"{content_hash}_{video_mode}_{language}"
    
    async def _get_or_generate_outline(self, content: str, topic: Dict, ...):
        cache_key = self._get_outline_cache_key(content, video_mode, language)
        cache_file = self.CACHE_DIR / f"{cache_key}.json"
        
        if cache_file.exists():
            with open(cache_file) as f:
                return json.load(f)
        
        # Generate outline as usual
        outline = await self._generate_outline(content, topic, ...)
        
        # Cache it
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        with open(cache_file, 'w') as f:
            json.dump(outline, f)
        
        return outline
```

**Estimated Savings:** 100% reduction for regenerated videos, ~15K tokens saved per re-run

---

### 3. 📝 **Compress Previous Sections Context** (HIGH IMPACT - 30% reduction)

**Current State:**
```python
# script_generator.py line 532-540
if i >= len(previous_sections) - 2:
    # Recent sections: include narration ending for continuity
    narration = prev.get('narration', '')
    narration_excerpt = narration[-500:] if len(narration) > 500 else narration
```

For later sections, we're passing 500 chars × number of previous sections, which adds up.

**Proposed Solution:** Use a **sliding window** + **summary approach**:

```python
def _build_previous_context(self, previous_sections: List[Dict], current_idx: int) -> str:
    """Build compressed context from previous sections.
    
    Strategy:
    - Last section: Full narration ending (300 chars)
    - Second-to-last: Key concepts only
    - Older sections: Just titles
    - Include a one-line "story so far" summary
    """
    if not previous_sections:
        return "(First section)"
    
    context_parts = []
    
    # One-line summary of progression
    titles = [s.get('title', '') for s in previous_sections]
    context_parts.append(f"Progress: {' → '.join(titles)}")
    
    # Last section: more detail for continuity
    if previous_sections:
        last = previous_sections[-1]
        narration = last.get('narration', '')[-200:]  # Reduced from 500
        context_parts.append(f"Previous ended: ...{narration}")
    
    return "\n".join(context_parts)
```

**Estimated Savings:** 30% reduction in context tokens per section

---

### 4. 🎬 **Batch Visual Script Generation** (MEDIUM IMPACT - 25% reduction)

**Current State:** Visual scripts are generated one section at a time, each with full prompt overhead.

**Proposed Solution:** For overview mode and short videos (≤5 sections), generate all visual scripts in one call:

```python
async def _generate_batch_visual_scripts(
    self, 
    sections: List[Dict],
    total_duration: float
) -> List[str]:
    """Generate visual scripts for multiple sections in one API call.
    
    More efficient than individual calls for short videos.
    """
    if len(sections) > 5:
        # Too many sections, use individual generation
        return None
    
    batch_prompt = self._build_batch_visual_script_prompt(sections, total_duration)
    
    response = await self.client.models.generate_content(
        model=self.VISUAL_SCRIPT_MODEL,
        contents=batch_prompt,
        config=self.visual_script_generation_config
    )
    
    # Parse response to extract individual scripts
    return self._parse_batch_visual_scripts(response.text)
```

**Estimated Savings:** 25% reduction for videos with ≤5 sections

---

### 5. 📊 **Skip Visual Analysis for Simple Sections** (LOW IMPACT - 10% reduction)

**Current State:** Every section goes through visual script analysis, even simple text-only sections.

**Proposed Solution:** Skip analysis for sections with low complexity:

```python
def _should_skip_visual_analysis(self, section: Dict, visual_script: str) -> bool:
    """Determine if section is simple enough to skip spatial analysis."""
    
    # Simple text-only sections
    if section.get('animation_type') == 'static':
        return True
    
    # Short visual scripts (fewer elements to analyze)
    if len(visual_script) < 1500:
        return True
    
    # No complex elements detected
    complex_indicators = ['Axes', 'Graph', 'plot', 'Circle', 'Arrow', 'Diagram']
    if not any(ind in visual_script for ind in complex_indicators):
        return True
    
    return False
```

**Estimated Savings:** 10% reduction in analysis API calls

---

### 6. 🔧 **Use Lighter Model for Overview Mode** (HIGH IMPACT - 40% cost reduction for overview)

**Current State:** Both comprehensive and overview modes use the same model.

**Proposed Solution:** Use `gemini-flash-lite` for overview mode (simpler, shorter content):

```python
# In config/models.py or directly in script_generator.py

def get_model_for_mode(video_mode: str) -> str:
    """Select appropriate model based on video complexity."""
    if video_mode == "overview":
        return "gemini-flash-lite-latest"  # $0.075/1M input vs $0.50/1M
    return "gemini-3-flash-preview"  # Full quality for comprehensive
```

**Estimated Savings:** 85% cost reduction for overview mode videos

---

### 7. 📋 **Streamline Prompts** (MEDIUM IMPACT - 20% reduction)

**Current State:** Prompts include extensive documentation and examples in every call.

**Proposed Solution:** Extract static documentation to a cached system prompt, include only dynamic content in user prompts:

```python
# Create a system prompt that's reused
VISUAL_SCRIPT_SYSTEM_PROMPT = """You are an expert educational video storyboard designer...
[All the static rules, examples, and guidelines - ~3000 tokens]
"""

# User prompt contains only dynamic content
def build_visual_script_user_prompt(section: Dict, audio_duration: float) -> str:
    """Minimal user prompt with just the section-specific data."""
    return f"""
Title: {section.get('title')}
Duration: {audio_duration:.1f}s
Narration: {section.get('narration')}
Key Concepts: {section.get('key_concepts')}
"""
```

For models that support system prompts efficiently, this can reduce per-call token usage significantly.

**Estimated Savings:** 20% reduction in prompt tokens

---

## Implementation Priority

| Priority | Optimization | Effort | Impact | Savings |
|----------|-------------|--------|--------|---------|
| 🔴 1 | Document Chunking | Medium | High | 50% Phase 2 |
| 🔴 2 | Lighter Model for Overview | Low | High | 85% overview |
| 🟡 3 | Compress Previous Context | Low | Medium | 30% context |
| 🟡 4 | Streamline Prompts | Medium | Medium | 20% prompts |
| 🟡 5 | Batch Visual Scripts | Medium | Medium | 25% short videos |
| 🟢 6 | Cache Outlines | Low | Medium | 100% re-runs |
| 🟢 7 | Skip Simple Analysis | Low | Low | 10% analysis |

---

## Estimated Total Savings

**Before Optimization (10-section comprehensive video):**
- Input tokens: ~155K
- Output tokens: ~40K
- Cost: ~$0.12

**After Full Optimization:**
- Input tokens: ~70K (55% reduction)
- Output tokens: ~40K (unchanged - quality maintained)
- Cost: ~$0.055

**For Overview Mode:**
- Input tokens: ~25K (80% reduction)
- Cost: ~$0.01

---

## Implementation Notes

### Phase 1: Quick Wins (1-2 days)
1. Implement document chunking (recommendation #1)
2. Add model selection for overview mode (#6)
3. Compress previous context (#3)

### Phase 2: Optimizations (3-5 days)
4. Implement outline caching (#2)
5. Streamline prompts with system prompts (#7)
6. Add complexity-based analysis skipping (#5)

### Phase 3: Advanced (5-7 days)
7. Batch visual script generation (#4)
8. Implement semantic chunking (vs. simple keyword matching)
9. Add telemetry to measure actual savings

---

## Monitoring & Validation

After implementing optimizations:

1. **Track token usage per stage** - Already implemented in `CostTracker`
2. **Compare quality metrics** - Sample videos before/after
3. **A/B test on real documents** - Ensure chunking doesn't miss critical content
4. **Monitor error rates** - Ensure optimizations don't increase failures

```python
# Add to cost_tracker.py
def track_optimization_metrics(self, stage: str, full_content_length: int, used_content_length: int):
    """Track how much content was used vs available."""
    reduction_pct = (1 - used_content_length / full_content_length) * 100
    print(f"[Optimization] {stage}: Used {used_content_length}/{full_content_length} chars ({reduction_pct:.1f}% reduction)")
```

---

## Conclusion

The biggest cost drivers are:
1. **Passing full documents to every section** - Fixed by chunking
2. **Using expensive models for simple tasks** - Fixed by model selection
3. **Redundant context in prompts** - Fixed by compression and caching

Implementing recommendations 1-3 alone should reduce costs by **40-50%** with minimal quality impact.

---

## Implementation Status ✅

The following optimizations have been **implemented**:

### 1. Document Chunking (script_generator.py)
- `_get_relevant_content_for_section()` - Extracts only relevant portion (~12K chars max)
- `_extract_keywords()` - Extracts keywords from section description
- `_find_relevant_chunks()` - Finds paragraphs matching keywords
- Falls back to proportional slicing with 30% overlap

### 2. Compressed Previous Context (script_generator.py)
- `_build_compressed_previous_context()` - Uses sliding window + summary
- Last 200 chars from most recent section only
- One-line progression summary for all titles

### 3. Representative Sampling for Analysis (analyzer.py)
- `_get_representative_sample()` - 40% intro, 40% middle, 20% end
- Reduced from 20K to 15K chars max

### 4. Automatic Pipeline Selection (routes/generation.py)
- When `video_mode="overview"` and `pipeline="default"` → Auto-selects `overview` pipeline
- 85% cheaper for overview videos
- Can be overridden by explicitly setting `pipeline` parameter

### 5. Overview Pipeline Configuration (config/models.py)
- `OVERVIEW_OPTIMIZED_PIPELINE` - Uses cheaper models throughout
- `gemini-flash-lite-latest` for script generation
- `gemini-2.5-flash` for visual scripts and Manim code

### Frontend Usage:
```json
// For overview videos (automatically uses cheap pipeline)
{
    "video_mode": "overview",
    "pipeline": "default"  // Will auto-switch to "overview" pipeline
}

// For comprehensive videos (uses default pipeline)
{
    "video_mode": "comprehensive",
    "pipeline": "default"
}

// Force high quality for overview (override auto-selection)
{
    "video_mode": "overview",
    "pipeline": "high_quality"
}
```
