"""
Translation prompts.

Used by: translation_service.py
"""

from .base import PromptTemplate


TRANSLATE_NARRATION = PromptTemplate(
    template="""Translate this educational narration from {source_language} to {target_language}.

Text: {text}

Rules:
- Keep meaning natural, not word-for-word
- Preserve [pause] markers
- Convert math to spoken form in target language
- Keep variable names: {{x}}, {{n}}, etc.

Translation:""",
    description="Translate single narration text"
)


TRANSLATE_NARRATION_BULK = PromptTemplate(
    template="""Translate educational narration from {source_name} to {target_name}.

CONTEXT: {section_context}

CRITICAL RULES:
1. Translate the MEANING naturally, not word-by-word
2. These texts may contain code-like patterns - DO NOT translate:
   - Variable names in curly braces: {{{{variable}}}}, {{{{x}}}}, {{{{n}}}}
   - Python f-string patterns: f"text {{{{var}}}}" - translate "text" but keep {{{{var}}}}
   - Technical identifiers: function_name, ClassName, method_name
3. Convert LaTeX math to SPOKEN form in {target_name}:
   - "$x^2$" → say "x squared" in {target_name}
   - "$\\frac{{{{a}}}}{{{{b}}}}$" → say "a over b" in {target_name}
   - Remove $ and LaTeX commands, keep only speakable words
4. Preserve markers exactly: [pause], [PAUSE], ...
5. Keep consistent terminology within this section
6. Output ONLY translations, no commentary

TEXTS:
{texts_block}

OUTPUT (same format, translated):""",
    description="Translate multiple narration segments"
)


TRANSLATE_DISPLAY_TEXT = PromptTemplate(
    template="""Translate this display text for animation from {source_language} to {target_language}.

Text: {text}

Rules:
- Keep it SHORT (for on-screen display)
- Preserve markup: **bold**, {{variables}}
- Keep math notation readable

Translation:""",
    description="Translate display text"
)


TRANSLATE_DISPLAY_TEXT_BATCH = PromptTemplate(
    template="""Translate display text for an educational animation from {source_name} to {target_name}.

CRITICAL RULES:
1. These are SHORT labels/headings for animation - keep them CONCISE
2. Do NOT translate:
   - Variable names: x, y, n, i, func
   - Python-like syntax: f"text {{{{var}}}}" - translate "text", keep {{{{var}}}}
   - Code identifiers: function_name, ClassName
3. Convert LaTeX to DISPLAY form (not spoken):
   - Keep mathematical notation clear
   - "$x^2$" → appropriate display in {target_name}
4. Preserve markup: **bold**, {{{{variables}}}}, [markers]
5. Keep it SHORT - these appear on screen

TEXTS:
{texts_block}

OUTPUT (same format, translated):""",
    description="Translate display text segments in batch"
)


TRANSLATE_TTS = PromptTemplate(
    template="""Convert for text-to-speech in {target_language}.

Text: {text}

Rules:
- All math becomes spoken words
- Numbers 0-20 spelled out
- No special characters
- Natural spoken form

Speakable version:""",
    description="Convert for TTS"
)


TRANSLATE_TTS_SPEAKABLE = PromptTemplate(
    template="""You are converting educational text for text-to-speech. Translate from {source_name} to {target_name} and convert ALL math to spoken words.

RULES:
1. Translate naturally to {target_name}
2. Convert ALL LaTeX/math to SPOKEN form:
   - "$x^2 + 3x$" → say "x squared plus three x" in {target_name}
   - "$\\frac{{{{a}}}}{{{{b}}}}$" → say "a divided by b" or "a over b"
   - Remove ALL $ symbols and LaTeX commands
3. Numbers: spell out 0-20, use digits for larger
4. NO variable preservation - translate everything
5. NO special characters - pure speakable text

INPUT TEXT:
{text}

SPOKEN {target_name_upper} VERSION:""",
    description="Translate for TTS with math converted to speech"
)


TRANSLATE_BATCH = PromptTemplate(
    template="""Translate each line from {source_language} to {target_language}.
Keep same structure.

Lines:
{lines}

Translations:""",
    description="Batch translate lines"
)


TRANSLATE_ITEMS_BATCH = PromptTemplate(
    template="""Translate each item from {source_name} to {target_name}.
Keep the items separated by "---ITEM---".
Preserve formatting and technical terms.

ITEMS:
{combined}

TRANSLATIONS:""",
    description="Translate list of items"
)
