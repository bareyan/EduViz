"""
Centralized Prompt Registry

ALL prompts in one place. Organized by domain.
Edit prompts HERE - they're used throughout the app.

Structure:
- SCRIPT_GENERATION: Script/outline generation prompts
- MANIM_GENERATION: Manim code generation prompts  
- CODE_CORRECTION: Error fixing prompts
- TRANSLATION: Translation prompts
- ANALYSIS: Content analysis prompts
- VISUAL_QC: Visual quality control prompts
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass


# =============================================================================
# PROMPT TEMPLATES
# =============================================================================

@dataclass
class PromptTemplate:
    """A prompt template with placeholders"""
    template: str
    description: str = ""
    
    def format(self, **kwargs) -> str:
        """Format the template with provided values"""
        return self.template.format(**kwargs)


# =============================================================================
# LANGUAGE DETECTION
# =============================================================================

LANGUAGE_DETECTION = PromptTemplate(
    template="""Detect the primary language of this text. Respond with ONLY the ISO 639-1 code (e.g., "en", "fr", "es").

Text:
{content}

Language code:""",
    description="Detect language from text content"
)


# =============================================================================
# SCRIPT GENERATION PROMPTS
# =============================================================================

SCRIPT_OVERVIEW = PromptTemplate(
    template="""You are an expert educator creating a video script.

Topic: {topic_title}
{topic_description}

Language: {language_name}
{language_instruction}

Content to cover:
{content}

Create a clear, engaging video script with sections.
Each section needs:
- title: Section title
- narration: What the narrator says (conversational, clear)
- visual_description: What viewers see on screen
- key_points: Main concepts covered

Output as JSON with "sections" array.""",
    description="Generate overview script from content"
)

SCRIPT_OUTLINE = PromptTemplate(
    template="""Analyze this educational content and create a detailed outline.

Topic: {topic_title}
Content: {content}

Language: {language_name}
{language_instruction}

Duration target: {duration_minutes} minutes

{focus_instructions}
{context_instructions}

Create an outline with:
1. Document analysis (content type, complexity, gaps)
2. Learning objectives
3. Prerequisites
4. Sections outline with timing

Output as JSON.""",
    description="Generate detailed outline for comprehensive mode"
)

SCRIPT_SECTION = PromptTemplate(
    template="""Generate the full narration for this section.

Section: {section_title}
Type: {section_type}
Content to cover: {content_to_cover}

Language: {language_name}
{language_instruction}

Duration target: {duration_seconds} seconds (~{word_count} words)

Write engaging, clear narration that explains the concepts.
Include natural transitions and emphasis on key points.""",
    description="Generate narration for a single section"
)


# =============================================================================
# MANIM GENERATION PROMPTS
# =============================================================================

VISUAL_SCRIPT = PromptTemplate(
    template="""Create a visual storyboard for this animation section.

Section: {section_title}
Narration: {narration}
Duration: {duration} seconds

For each moment, describe:
- Timestamp (e.g., 0:00-0:05)
- What appears on screen
- Animations/transitions
- Text/equations to show
- Colors and positioning

Be specific about:
- Object positions (use "upper left", "center", etc.)
- Animation timing (Write, FadeIn, Transform, etc.)
- Visual hierarchy (what's most important)

{timing_context}""",
    description="Generate visual script/storyboard for Manim"
)

VISUAL_SCRIPT_ANALYSIS = PromptTemplate(
    template="""Check this visual script for spatial layout issues.

Visual Script:
{visual_script}

Duration: {duration} seconds

Check for:
1. Overlapping elements at same timestamp
2. Too many objects on screen at once (max 4-5)
3. Text too small or too large
4. Poor positioning (off-screen, cramped)
5. Missing cleanup (objects staying too long)

Respond with JSON:
{{
    "status": "ok" or "issues_found",
    "issues_found": <count>,
    "fixes": [
        {{"issue": "...", "fix": "..."}}
    ]
}}""",
    description="Analyze visual script for layout problems"
)

MANIM_CODE_FROM_SCRIPT = PromptTemplate(
    template="""Generate Manim code for this visual script.

Visual Script:
{visual_script}

Duration: {duration} seconds
Style: {style}

{language_instructions}
{color_instructions}
{type_guidance}

{spatial_fixes}

Generate ONLY the construct() method body.
Use proper Manim CE syntax.
Match timing to narration segments.

Important:
- Clean up objects before adding new ones
- Use self.wait() for timing
- Keep animations smooth
- Position text clearly""",
    description="Generate Manim code from visual script"
)

MANIM_SINGLE_SHOT = PromptTemplate(
    template="""Generate Manim animation code for this section.

Title: {section_title}
Narration: {narration}
Visual Description: {visual_description}
Duration: {duration} seconds

{timing_context}

{language_instructions}
{color_instructions}
{type_guidance}

Generate ONLY the construct() method body.
Match animation timing to narration.
Use clean, working Manim CE code.""",
    description="Single-shot Manim code generation"
)


# =============================================================================
# CODE CORRECTION PROMPTS
# =============================================================================

CODE_FIX_SIMPLE = PromptTemplate(
    template="""FIX THIS MANIM ERROR:

Error: {error_message}

Code:
```python
{code}
```

Provide fix as SEARCH/REPLACE block:
<<<<<<< SEARCH
exact text to find
=======
replacement text
>>>>>>> REPLACE""",
    description="Simple code fix with search/replace"
)

CODE_FIX_ANALYSIS = PromptTemplate(
    template="""Analyze this Manim error and provide fixes.

Error: {error_message}
Error type: {error_type}

Code context:
```python
{code_context}
```

Full code:
```python
{full_code}
```

Provide detailed analysis and SEARCH/REPLACE fixes.""",
    description="Detailed code fix with analysis"
)

CODE_FIX_MULTIPLE = PromptTemplate(
    template="""Fix ALL these Manim errors using SEARCH/REPLACE blocks:

Errors:
{errors}

Code:
```python
{code}
```

Provide one SEARCH/REPLACE block per fix.
Order fixes from most to least critical.""",
    description="Fix multiple errors at once"
)

VISUAL_FIX = PromptTemplate(
    template="""FIX THESE VISUAL LAYOUT ERRORS in Manim code:

Issues found:
{issues}

Current code:
```python
{code}
```

Fix positioning, overlaps, and timing issues.
Use SEARCH/REPLACE blocks.""",
    description="Fix visual/layout issues in Manim code"
)


# =============================================================================
# TRANSLATION PROMPTS
# =============================================================================

TRANSLATE_NARRATION = PromptTemplate(
    template="""Translate educational narration from {source_language} to {target_language}.

Original text:
{text}

Requirements:
- Maintain educational tone
- Keep technical terms accurate  
- Preserve emphasis and pacing
- Natural, conversational flow

Translated text:""",
    description="Translate narration text"
)

TRANSLATE_DISPLAY_TEXT = PromptTemplate(
    template="""Translate display text for an educational animation from {source_language} to {target_language}.

Text to translate:
{text}

Requirements:
- Keep math notation intact (LaTeX)
- Maintain text length (similar character count)
- Clear, readable translation

Translated text:""",
    description="Translate on-screen display text"
)

TRANSLATE_TTS = PromptTemplate(
    template="""Translate for text-to-speech from {source_language} to {target_language}. Convert ALL math to spoken words.

Text:
{text}

Requirements:
- Convert equations to spoken form (e.g., "x squared" not "x²")
- Natural speech rhythm
- Clear pronunciation

Spoken version:""",
    description="Translate and convert for TTS"
)

TRANSLATE_BATCH = PromptTemplate(
    template="""Translate each item from {source_language} to {target_language}.

Items:
{items}

Return JSON array with translations in same order.""",
    description="Batch translate multiple items"
)


# =============================================================================
# CONTENT ANALYSIS PROMPTS
# =============================================================================

ANALYZE_TEXT = PromptTemplate(
    template="""You are an expert educator preparing comprehensive educational video content.

Analyze this text and extract:
1. Main topic and subject area
2. Key concepts and definitions
3. Important examples
4. Suggested video structure

Content:
{content}

Output as structured JSON.""",
    description="Analyze text content for video creation"
)

ANALYZE_PDF = PromptTemplate(
    template="""You are an expert educator preparing comprehensive educational video content with animated visuals.

Analyze this PDF content:
{content}

Page count: {page_count}
Has images: {has_images}

Extract:
1. Document type (lecture notes, textbook, paper, etc.)
2. Main topics covered
3. Mathematical content level
4. Suggested animations
5. Key takeaways

Output as structured JSON.""",
    description="Analyze PDF content"
)

ANALYZE_IMAGE = PromptTemplate(
    template="""You are an expert educator preparing COMPREHENSIVE educational video content.

Analyze this image and describe:
1. What is shown
2. Educational value
3. Key concepts illustrated
4. How to explain this in a video

Be detailed and educational.""",
    description="Analyze image content"
)


# =============================================================================
# VISUAL QC PROMPTS
# =============================================================================

VISUAL_QC_ANALYSIS = PromptTemplate(
    template="""Analyze this Manim educational animation video for PERSISTENT VISUAL ERRORS.

Frame analysis context:
- Video duration: {duration} seconds
- Frame count: {frame_count}
- Resolution: {resolution}

Look for:
1. Text overlapping or cut off
2. Objects positioned off-screen
3. Animations that don't complete
4. Visual glitches persisting across frames
5. Timing issues (too fast/slow)

Report only PERSISTENT issues (appearing in multiple frames).

Expected content:
{expected_content}

Respond with JSON:
{{
    "quality_score": 1-10,
    "issues": [
        {{"type": "...", "description": "...", "severity": "high/medium/low", "timestamp": "..."}}
    ],
    "pass": true/false
}}""",
    description="Analyze rendered video for visual quality issues"
)


# =============================================================================
# PROMPT REGISTRY
# =============================================================================

class PromptRegistry:
    """
    Central access point for all prompts.
    
    Usage:
        from app.services.prompting_engine.prompts import prompts
        
        prompt = prompts.get("VISUAL_SCRIPT").format(
            section_title="Intro",
            narration="Welcome...",
            duration=30
        )
    """
    
    _prompts: Dict[str, PromptTemplate] = {
        # Language
        "LANGUAGE_DETECTION": LANGUAGE_DETECTION,
        
        # Script generation
        "SCRIPT_OVERVIEW": SCRIPT_OVERVIEW,
        "SCRIPT_OUTLINE": SCRIPT_OUTLINE,
        "SCRIPT_SECTION": SCRIPT_SECTION,
        
        # Manim generation
        "VISUAL_SCRIPT": VISUAL_SCRIPT,
        "VISUAL_SCRIPT_ANALYSIS": VISUAL_SCRIPT_ANALYSIS,
        "MANIM_CODE_FROM_SCRIPT": MANIM_CODE_FROM_SCRIPT,
        "MANIM_SINGLE_SHOT": MANIM_SINGLE_SHOT,
        
        # Code correction
        "CODE_FIX_SIMPLE": CODE_FIX_SIMPLE,
        "CODE_FIX_ANALYSIS": CODE_FIX_ANALYSIS,
        "CODE_FIX_MULTIPLE": CODE_FIX_MULTIPLE,
        "VISUAL_FIX": VISUAL_FIX,
        
        # Translation
        "TRANSLATE_NARRATION": TRANSLATE_NARRATION,
        "TRANSLATE_DISPLAY_TEXT": TRANSLATE_DISPLAY_TEXT,
        "TRANSLATE_TTS": TRANSLATE_TTS,
        "TRANSLATE_BATCH": TRANSLATE_BATCH,
        
        # Analysis
        "ANALYZE_TEXT": ANALYZE_TEXT,
        "ANALYZE_PDF": ANALYZE_PDF,
        "ANALYZE_IMAGE": ANALYZE_IMAGE,
        
        # Visual QC
        "VISUAL_QC_ANALYSIS": VISUAL_QC_ANALYSIS,
    }
    
    def get(self, name: str) -> PromptTemplate:
        """Get a prompt template by name"""
        if name not in self._prompts:
            raise KeyError(f"Unknown prompt: {name}. Available: {list(self._prompts.keys())}")
        return self._prompts[name]
    
    def format(self, name: str, **kwargs) -> str:
        """Get and format a prompt in one call"""
        return self.get(name).format(**kwargs)
    
    def list_prompts(self) -> list:
        """List all available prompt names"""
        return list(self._prompts.keys())
    
    def register(self, name: str, template: PromptTemplate):
        """Register a new prompt template"""
        self._prompts[name] = template


# Global instance
prompts = PromptRegistry()


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_prompt(name: str) -> PromptTemplate:
    """Get a prompt template"""
    return prompts.get(name)


def format_prompt(name: str, **kwargs) -> str:
    """Get and format a prompt"""
    return prompts.format(name, **kwargs)


def list_prompts() -> list:
    """List all available prompts"""
    return prompts.list_prompts()
