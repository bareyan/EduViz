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

CRITICAL: Convert mathematical expressions to how a teacher would SAY them aloud in {target_name}:

Examples of math-to-speech conversion:
- "$x$" → "x" (just say the letter)
- "$x^2$" → "x squared" (English) / "x au carré" (French)
- "$\\frac{{{{a}}}}{{{{b}}}}$" → "a over b" (English) / "a sur b" (French)
- "$\\sqrt{{{{x}}}}$" → "square root of x" (English) / "racine carrée de x" (French)
- "$\\alpha$" → "alpha"
- "$f(x)$" → "f of x" (English) / "f de x" (French)

RULES:
1. Remove ALL $ signs, backslashes, and LaTeX commands
2. Output ONLY speakable text - a person must be able to read it aloud naturally
3. Keep the educational, explanatory tone
4. Preserve [pause] markers if present
5. Output ONLY the translated text, nothing else

INPUT TEXT:
{text}

SPOKEN {target_name_upper} VERSION:""",
    description="Translate for TTS with math converted to speech"
)

TRANSLATE_MANIM_TEXTS = PromptTemplate(
    template="""Translate display text for an educational animation from {source_name} to {target_name}.

These texts appear ON SCREEN in a video. Keep them concise and natural.

RULES:
1. Translate the meaning naturally, keep similar length
2. These are Python strings - preserve any escape sequences: \\n, \\t, etc.
3. DO NOT translate:
   - Variable placeholders: {{{{x}}}}, {{{{n}}}}, {{{{value}}}}
   - Mathematical symbols that should stay as-is
4. Keep bullet points (•, -, *) and formatting
5. Output ONLY the translations

TEXTS:
{texts_block}

TRANSLATIONS (same format):
""",
    description="Translate display text for Manim code with preservation of Python string patterns"
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
