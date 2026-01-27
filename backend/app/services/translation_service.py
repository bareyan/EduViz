"""
Translation Service - Translates video narration and Manim text to different languages
Uses lightweight Gemini model for efficient translation
"""

import json
import asyncio
import re
from typing import Dict, Any, List, Optional

# Unified Gemini client (works with both API and Vertex AI)
from app.services.gemini import get_gemini_client, get_types_module
from app.core import LANGUAGE_NAMES
create_client = get_gemini_client

# Model configuration
from app.config.models import get_model_config


class TranslationService:
    """Translates video content to different languages"""

    def __init__(self):
        # Use centralized prompting engine
        from app.services.prompting_engine import PromptingEngine, PromptConfig
        self.engine = PromptingEngine("translation")
        self.prompt_config = PromptConfig(temperature=0.3, timeout=60.0)

    async def translate_script(
        self,
        script: Dict[str, Any],
        target_language: str,
        source_language: Optional[str] = None
    ) -> Dict[str, Any]:
        """Translate an entire script to target language.
        
        Translates section-by-section in parallel for efficiency while maintaining
        context within each section for coherent translations.
        
        Args:
            script: Original script with sections
            target_language: Target language code (e.g., 'fr', 'es')
            source_language: Source language code (auto-detected if not provided)
        
        Returns:
            Translated script with same structure
        """
        if not source_language:
            source_language = script.get("source_language", script.get("language", "en"))

        target_name = LANGUAGE_NAMES.get(target_language, target_language)
        source_name = LANGUAGE_NAMES.get(source_language, source_language)

        print(f"[TranslationService] Translating from {source_name} to {target_name}")

        # Deep copy the script
        translated_script = json.loads(json.dumps(script))

        # Translate document title first (provides context for sections)
        script.get("title", "Educational Video")
        if translated_script.get("title"):
            translated_titles = await self._translate_section_texts(
                [translated_script["title"]],
                source_language,
                target_language,
                section_context="Document title"
            )
            translated_script["title"] = translated_titles[0] if translated_titles else translated_script["title"]
            translated_script["title"]

        # Translate all sections in parallel
        sections = script.get("sections", [])
        if sections:
            print(f"[TranslationService] Translating {len(sections)} sections in parallel...")

            async def translate_one_section(idx: int, section: Dict[str, Any]) -> tuple:
                """Translate all texts in a single section."""
                translated = json.loads(json.dumps(section))  # Deep copy

                # Collect texts from this section
                texts = []
                text_keys = []  # Track where each text came from

                if section.get("title"):
                    texts.append(section["title"])
                    text_keys.append(("title",))

                # Prefer tts_narration (TTS-ready text)
                if section.get("tts_narration"):
                    texts.append(section["tts_narration"])
                    text_keys.append(("tts_narration",))
                elif section.get("narration"):
                    texts.append(section["narration"])
                    text_keys.append(("narration",))

                # Narration segments
                if section.get("narration_segments"):
                    for j, seg in enumerate(section["narration_segments"]):
                        if seg.get("text"):
                            texts.append(seg["text"])
                            text_keys.append(("narration_segments", j, "text"))

                # Key concepts
                if section.get("key_concepts"):
                    for j, concept in enumerate(section["key_concepts"]):
                        if concept:
                            texts.append(concept)
                            text_keys.append(("key_concepts", j))

                if not texts:
                    return (idx, translated)

                # Translate all texts in this section together (for context)
                section_title = section.get("title", f"Section {idx + 1}")
                translated_texts = await self._translate_section_texts(
                    texts,
                    source_language,
                    target_language,
                    section_context=f"Section: {section_title}"
                )

                # Apply translations back to the section
                for key_path, trans_text in zip(text_keys, translated_texts):
                    if len(key_path) == 1:
                        translated[key_path[0]] = trans_text
                    elif len(key_path) == 3:
                        # narration_segments, j, text
                        translated[key_path[0]][key_path[1]][key_path[2]] = trans_text
                    elif len(key_path) == 2:
                        # key_concepts, j
                        translated[key_path[0]][key_path[1]] = trans_text

                # Sync narration with tts_narration if both exist
                if section.get("tts_narration") and section.get("narration"):
                    translated["narration"] = translated.get("tts_narration", "")

                print(f"[TranslationService] Completed section {idx + 1}: {section_title[:40]}")
                return (idx, translated)

            # Run all section translations in parallel
            tasks = [translate_one_section(i, s) for i, s in enumerate(sections)]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Reconstruct sections in order
            translated_sections = [None] * len(sections)
            for result in results:
                if isinstance(result, Exception):
                    print(f"[TranslationService] Section translation error: {result}")
                else:
                    idx, translated_section = result
                    translated_sections[idx] = translated_section

            # Fill any failed sections with originals
            for i in range(len(translated_sections)):
                if translated_sections[i] is None:
                    translated_sections[i] = sections[i]

            translated_script["sections"] = translated_sections

        # Update language metadata
        translated_script["language"] = target_language
        translated_script["output_language"] = target_language
        translated_script["translated_from"] = source_language

        print("[TranslationService] Translation complete")
        return translated_script

    async def _translate_section_texts(
        self,
        texts: List[str],
        source_language: str,
        target_language: str,
        section_context: str = ""
    ) -> List[str]:
        """Translate multiple texts from a section in a single API call.
        
        Provides context and warnings about code patterns to avoid mistranslation.
        """
        if not texts:
            return []

        source_name = LANGUAGE_NAMES.get(source_language, source_language)
        target_name = LANGUAGE_NAMES.get(target_language, target_language)

        # Build numbered text blocks
        texts_block = ""
        for i, text in enumerate(texts):
            safe_text = text.replace("[TEXT_", "[TEXT\\_")
            texts_block += f"[TEXT_{i}]\n{safe_text}\n[/TEXT_{i}]\n\n"

        from app.services.prompting_engine import format_prompt
        prompt = format_prompt(
            "TRANSLATE_NARRATION_BULK",
            source_name=source_name,
            target_name=target_name,
            section_context=section_context,
            texts_block=texts_block
        )
        for i in range(len(texts)):
            prompt += f"[TEXT_{i}]\n...\n[/TEXT_{i}]\n"

        try:
            from app.services.prompting_engine import PromptConfig
            config = PromptConfig(
                temperature=0.3,
                max_output_tokens=4000,
                timeout=120
            )
            
            result_text = await self.engine.generate(
                prompt=prompt,
                config=config,
                model=self.MODEL
            )

            # Parse translations
            translated_texts = []
            for i in range(len(texts)):
                pattern = rf'\[TEXT_{i}\]\s*(.*?)\s*\[/TEXT_{i}\]'
                match = re.search(pattern, result_text, re.DOTALL)
                if match:
                    translated = match.group(1).strip()
                    translated = translated.replace("[TEXT\\_", "[TEXT_")
                    translated_texts.append(translated)
                else:
                    print(f"[TranslationService] Warning: TEXT_{i} not found, using original")
                    translated_texts.append(texts[i])

            return translated_texts

        except Exception as e:
            print(f"[TranslationService] Translation failed: {e}")
            return texts

    # Non-Latin scripts that can't mix with LaTeX in Tex()
    NON_LATIN_LANGUAGES = {
        'hy', 'ar', 'he', 'zh', 'ja', 'ko', 'ru', 'el', 'th',
        'hi', 'bn', 'ta', 'te', 'ml', 'kn', 'gu', 'pa', 'mr',
        'fa', 'ur', 'am', 'ka', 'my', 'km', 'lo', 'si', 'ne'
    }

    async def translate_manim_code(
        self,
        manim_code: str,
        target_language: str,
        source_language: str = "en"
    ) -> str:
        """Translate Text() strings in Manim code to target language.
        
        This extracts only the text content from Text("...") calls,
        translates them in batch with context, and replaces them back.
        The code structure is preserved exactly.
        
        For non-Latin languages, Tex() with mixed text/math is converted to
        separate Text() and MathTex() objects with .next_to() positioning.
        
        Args:
            manim_code: Original Manim Python code
            target_language: Target language code
            source_language: Source language code
        
        Returns:
            Manim code with translated Text() strings
        """
        print(f"[TranslationService] translate_manim_code called: source={source_language}, target={target_language}")
        print(f"[TranslationService] Code length: {len(manim_code) if manim_code else 0}")

        if not manim_code:
            print("[TranslationService] No manim_code provided, returning empty")
            return manim_code

        is_non_latin = target_language in self.NON_LATIN_LANGUAGES
        print(f"[TranslationService] is_non_latin={is_non_latin} (target={target_language}, NON_LATIN_LANGUAGES={self.NON_LATIN_LANGUAGES})")

        # For non-Latin languages, first handle Tex() with mixed content
        if is_non_latin:
            print(f"[TranslationService] Running _convert_tex_for_non_latin for {target_language}")
            manim_code = await self._convert_tex_for_non_latin(manim_code, target_language, source_language)

        # Extract all Text("...") strings with their positions
        # Match Text("string") or Text('string') with various arguments after
        text_pattern = r'(Text)\s*\(\s*(["\'])((?:(?!\2)[^\\]|\\.)*)\2'

        matches = list(re.finditer(text_pattern, manim_code))
        print(f"[TranslationService] Found {len(matches)} Text() matches")

        if not matches:
            print("[TranslationService] No Text() strings found in Manim code")
            return manim_code

        # Extract the text content (group 3 is the string content)
        texts_to_translate = []
        match_info = []  # Store (match_object, func_name, quote_char, original_text)

        for match in matches:
            func_name = match.group(1)  # Text
            quote_char = match.group(2)  # ' or "
            text_content = match.group(3)  # The actual string content

            # Skip very short strings or bullet characters
            if len(text_content.strip()) <= 2:
                continue

            texts_to_translate.append(text_content)
            match_info.append((match, func_name, quote_char, text_content))

        if not texts_to_translate:
            print("[TranslationService] No translatable Text() strings found")
            return manim_code

        print(f"[TranslationService] Found {len(texts_to_translate)} Text() strings to translate")

        # Translate all texts in one batch call
        translated_texts = await self._translate_manim_texts(
            texts_to_translate,
            source_language,
            target_language
        )

        # Replace texts in reverse order to preserve positions
        result = manim_code
        for (match, func_name, quote_char, original_text), translated_text in zip(
            reversed(match_info), reversed(translated_texts)
        ):
            # Escape quotes in translated text to match the quote style
            if quote_char == '"':
                safe_translated = translated_text.replace('\\', '\\\\').replace('"', '\\"')
            else:
                safe_translated = translated_text.replace('\\', '\\\\').replace("'", "\\'")

            # Build the replacement: Text("translated")
            new_match = f'{func_name}({quote_char}{safe_translated}{quote_char}'

            # Replace at exact position
            result = result[:match.start()] + new_match + result[match.end():]

        return result

    async def _convert_tex_for_non_latin(
        self,
        manim_code: str,
        target_language: str,
        source_language: str
    ) -> str:
        """Convert Tex() with mixed text/math to separate Text() + MathTex() for non-Latin scripts.
        
        Non-Latin scripts (Armenian, Arabic, Chinese, etc.) cannot be mixed with LaTeX
        in a single Tex() call. This function finds such cases and converts them to
        VGroup with Text() and MathTex() positioned with .arrange() or .next_to().
        """
        # Find Tex() calls that contain both text and math ($...$)
        # Pattern: Tex(r"text $math$ more text", ...)
        tex_pattern = r'(\s*)(\w+)\s*=\s*Tex\s*\(\s*r?(["\'])((?:(?!\3)[^\\]|\\.)*)\3([^)]*)\)'

        def convert_tex_match(match):
            indent = match.group(1)
            var_name = match.group(2)
            quote = match.group(3)
            content = match.group(4)
            rest_args = match.group(5)  # e.g., ", font_size=32"

            # Check if content has both text and math
            if '$' not in content:
                # No math, just convert Tex to Text
                return f'{indent}{var_name} = Text({quote}{content}{quote}{rest_args})'

            # Split content by $...$ math segments
            parts = re.split(r'(\$[^$]+\$)', content)

            if len(parts) <= 1:
                # No actual splitting happened
                return match.group(0)

            # Filter empty parts
            parts = [p for p in parts if p.strip()]

            if len(parts) == 1:
                # Only one part (all math or all text)
                if parts[0].startswith('$'):
                    math_content = parts[0][1:-1]  # Remove $ signs
                    return f'{indent}{var_name} = MathTex(r"{math_content}"{rest_args})'
                else:
                    return f'{indent}{var_name} = Text({quote}{parts[0]}{quote}{rest_args})'

            # Multiple parts - create VGroup with arranged elements
            lines = []
            element_names = []

            for i, part in enumerate(parts):
                elem_name = f'_tex_part_{i}'
                element_names.append(elem_name)

                if part.startswith('$') and part.endswith('$'):
                    # Math part
                    math_content = part[1:-1]
                    lines.append(f'{indent}{elem_name} = MathTex(r"{math_content}")')
                else:
                    # Text part - this will be translated later
                    safe_part = part.replace('"', '\\"')
                    lines.append(f'{indent}{elem_name} = Text("{safe_part}", font_size=28)')

            # Create VGroup and arrange horizontally
            elements_str = ', '.join(element_names)
            lines.append(f'{indent}{var_name} = VGroup({elements_str}).arrange(RIGHT, buff=0.15)')

            return '\n'.join(lines)

        # Apply conversion
        result = re.sub(tex_pattern, convert_tex_match, manim_code)

        return result

    async def _translate_manim_texts(
        self,
        texts: List[str],
        source_language: str,
        target_language: str
    ) -> List[str]:
        """Translate Text() string contents for Manim code.
        
        These are display texts that appear in the video, not narration.
        """
        if not texts:
            return []

        source_name = LANGUAGE_NAMES.get(source_language, source_language)
        target_name = LANGUAGE_NAMES.get(target_language, target_language)

        # Build numbered text blocks
        texts_block = ""
        for i, text in enumerate(texts):
            texts_block += f"[TEXT_{i}]\n{text}\n[/TEXT_{i}]\n\n"

        prompt = f"""Translate display text for an educational animation from {source_name} to {target_name}.

These texts appear ON SCREEN in a video. Keep them concise and natural.

RULES:
1. Translate the meaning naturally, keep similar length
2. These are Python strings - preserve any escape sequences: \\n, \\t, etc.
3. DO NOT translate:
   - Variable placeholders: {{x}}, {{n}}, {{value}}
   - Mathematical symbols that should stay as-is
4. Keep bullet points (•, -, *) and formatting
5. Output ONLY the translations

TEXTS:
{texts_block}

TRANSLATIONS (same format):
"""
        for i in range(len(texts)):
            prompt += f"[TEXT_{i}]\n...\n[/TEXT_{i}]\n"

        try:
            from app.services.prompting_engine import PromptConfig
            config = PromptConfig(
                temperature=0.2,
                max_output_tokens=4000,
                timeout=120
            )
            
            result_text = await self.engine.generate(
                prompt=prompt,
                config=config,
                model=self.MODEL
            )

            # Parse translations
            translated_texts = []
            for i in range(len(texts)):
                pattern = rf'\[TEXT_{i}\]\s*(.*?)\s*\[/TEXT_{i}\]'
                match = re.search(pattern, result_text, re.DOTALL)
                if match:
                    translated = match.group(1).strip()
                    translated_texts.append(translated)
                else:
                    print(f"[TranslationService] Warning: TEXT_{i} not found, using original")
                    translated_texts.append(texts[i])

            return translated_texts

        except Exception as e:
            print(f"[TranslationService] Manim text translation failed: {e}")
            return texts

    async def _translate_text(
        self,
        text: str,
        source_language: str,
        target_language: str
    ) -> str:
        """Translate a single text string, converting LaTeX to spoken form for TTS"""
        if not text or not text.strip():
            return text

        if source_language == target_language:
            # Even for same language, still need to clean up LaTeX for TTS
            return self._convert_latex_to_spoken(text)

        source_name = LANGUAGE_NAMES.get(source_language, source_language)
        target_name = LANGUAGE_NAMES.get(target_language, target_language)

        prompt = f"""You are converting educational text for text-to-speech. Translate from {source_name} to {target_name} and convert ALL math to spoken words.

CRITICAL: Convert mathematical expressions to how a teacher would SAY them aloud in {target_name}:

Examples of math-to-speech conversion:
- "$x$" → "x" (just say the letter)
- "$x^2$" → "x au carré" (French) / "x squared" (English) / "x hoch zwei" (German)
- "$x^n$" → "x à la puissance n" (French) / "x to the power of n" (English)
- "$\\frac{{a}}{{b}}$" → "a sur b" (French) / "a over b" (English) / "a durch b" (German)
- "$\\sqrt{{x}}$" → "racine carrée de x" (French) / "square root of x" (English)
- "$\\alpha$" → "alpha"
- "$\\sum_{{i=1}}^{{n}}$" → "la somme de i égal 1 à n" (French) / "the sum from i equals 1 to n" (English)
- "$f(x)$" → "f de x" (French) / "f of x" (English)
- "$x \\leq y$" → "x inférieur ou égal à y" (French) / "x less than or equal to y" (English)
- "$\\lim_{{x \\to 0}}$" → "la limite quand x tend vers zéro" (French) / "the limit as x approaches zero" (English)
- "$\\int_{{a}}^{{b}}$" → "l'intégrale de a à b" (French) / "the integral from a to b" (English)

RULES:
1. Remove ALL $ signs, backslashes, and LaTeX commands
2. Output ONLY speakable text - a person must be able to read it aloud naturally
3. Keep the educational, explanatory tone
4. Preserve [pause] markers if present
5. Output ONLY the translated text, nothing else

INPUT TEXT:
{text}

SPOKEN {target_name.upper()} VERSION:"""

        try:
            from app.services.prompting_engine import PromptConfig
            config = PromptConfig(
                temperature=0.3,
                max_output_tokens=2000,
                timeout=60
            )
            
            translated = await self.engine.generate(
                prompt=prompt,
                config=config,
                model=self.MODEL
            )

            # Remove any prefix if the model included it
            prefixes_to_remove = [
                f"SPOKEN {target_name.upper()} VERSION:",
                "TRANSLATION:",
                "Here is the translation:",
                "Here's the translation:",
                "Translated text:",
                "SPEAKABLE TRANSLATION:",
            ]
            for prefix in prefixes_to_remove:
                if translated.lower().startswith(prefix.lower()):
                    translated = translated[len(prefix):].strip()

            # Final cleanup - remove any remaining $ or LaTeX artifacts
            translated = self._convert_latex_to_spoken(translated)

            return translated

        except Exception as e:
            print(f"[TranslationService] Translation failed: {e}")
            return self._convert_latex_to_spoken(text)  # Return cleaned original on failure

    def _convert_latex_to_spoken(self, text: str) -> str:
        """Convert LaTeX notation to spoken form for TTS (fallback/cleanup)"""
        import re

        result = text

        # First, handle complex patterns with content inside braces
        # Fractions: \frac{a}{b} -> a over b
        result = re.sub(r'\\frac\s*\{([^}]+)\}\s*\{([^}]+)\}', r'\1 over \2', result)

        # Square root: \sqrt{x} -> square root of x
        result = re.sub(r'\\sqrt\s*\{([^}]+)\}', r'square root of \1', result)

        # Subscripts: x_{n} or x_n -> x sub n
        result = re.sub(r'([a-zA-Z])_\{([^}]+)\}', r'\1 sub \2', result)
        result = re.sub(r'([a-zA-Z])_([a-zA-Z0-9])', r'\1 sub \2', result)

        # Superscripts/powers: x^{2} or x^2 -> x to the power of 2
        result = re.sub(r'([a-zA-Z])\^\{2\}', r'\1 squared', result)
        result = re.sub(r'([a-zA-Z])\^2(?![0-9])', r'\1 squared', result)
        result = re.sub(r'([a-zA-Z])\^\{3\}', r'\1 cubed', result)
        result = re.sub(r'([a-zA-Z])\^3(?![0-9])', r'\1 cubed', result)
        result = re.sub(r'([a-zA-Z])\^\{([^}]+)\}', r'\1 to the power of \2', result)
        result = re.sub(r'([a-zA-Z])\^([a-zA-Z0-9]+)', r'\1 to the power of \2', result)

        # Greek letters (must come before removing backslashes)
        greek_letters = {
            r'\\alpha': 'alpha', r'\\beta': 'beta', r'\\gamma': 'gamma',
            r'\\delta': 'delta', r'\\epsilon': 'epsilon', r'\\zeta': 'zeta',
            r'\\eta': 'eta', r'\\theta': 'theta', r'\\iota': 'iota',
            r'\\kappa': 'kappa', r'\\lambda': 'lambda', r'\\mu': 'mu',
            r'\\nu': 'nu', r'\\xi': 'xi', r'\\pi': 'pi',
            r'\\rho': 'rho', r'\\sigma': 'sigma', r'\\tau': 'tau',
            r'\\upsilon': 'upsilon', r'\\phi': 'phi', r'\\chi': 'chi',
            r'\\psi': 'psi', r'\\omega': 'omega',
            r'\\Gamma': 'Gamma', r'\\Delta': 'Delta', r'\\Theta': 'Theta',
            r'\\Lambda': 'Lambda', r'\\Sigma': 'Sigma', r'\\Phi': 'Phi',
            r'\\Psi': 'Psi', r'\\Omega': 'Omega',
        }
        for latex, spoken in greek_letters.items():
            result = re.sub(latex, spoken, result)

        # Math operators and symbols
        operators = {
            r'\\sum': 'the sum of',
            r'\\prod': 'the product of',
            r'\\int': 'the integral of',
            r'\\lim': 'the limit of',
            r'\\infty': 'infinity',
            r'\\partial': 'partial',
            r'\\nabla': 'nabla',
            r'\\times': 'times',
            r'\\cdot': 'times',
            r'\\div': 'divided by',
            r'\\pm': 'plus or minus',
            r'\\leq': 'less than or equal to',
            r'\\geq': 'greater than or equal to',
            r'\\neq': 'not equal to',
            r'\\approx': 'approximately equal to',
            r'\\equiv': 'equivalent to',
            r'\\rightarrow': 'goes to',
            r'\\to': 'to',
            r'\\in': 'in',
            r'\\subset': 'subset of',
            r'\\cup': 'union',
            r'\\cap': 'intersection',
            r'\\forall': 'for all',
            r'\\exists': 'there exists',
            r'\\ldots': 'and so on',
            r'\\dots': 'and so on',
            r'\\cdots': 'and so on',
        }
        for latex, spoken in operators.items():
            result = re.sub(latex, spoken, result)

        # Function notation: f(x) stays as f of x
        result = re.sub(r'([a-zA-Z])\(([^)]+)\)', r'\1 of \2', result)

        # Big O notation
        result = re.sub(r'O\(([^)]+)\)', r'O of \1', result)

        # Remove remaining LaTeX commands (anything starting with \)
        result = re.sub(r'\\[a-zA-Z]+', '', result)

        # Remove $ signs
        result = re.sub(r'\$', '', result)

        # Remove curly braces
        result = re.sub(r'[{}]', '', result)

        # Clean up multiple spaces
        result = re.sub(r'\s+', ' ', result)

        return result.strip()

    async def _translate_list(
        self,
        items: List[str],
        source_language: str,
        target_language: str
    ) -> List[str]:
        """Translate a list of strings efficiently in one call"""
        if not items:
            return items

        if source_language == target_language:
            return items

        source_name = LANGUAGE_NAMES.get(source_language, source_language)
        target_name = LANGUAGE_NAMES.get(target_language, target_language)

        # Join items with special separator
        separator = "\n---ITEM---\n"
        combined = separator.join(items)

        prompt = f"""Translate each item from {source_name} to {target_name}.
Keep the items separated by "---ITEM---".
Preserve formatting and technical terms.

ITEMS:
{combined}

TRANSLATIONS:"""

        try:
            from app.services.prompting_engine import PromptConfig
            config = PromptConfig(
                temperature=0.3,
                max_output_tokens=2000,
                timeout=60
            )
            
            result = await self.engine.generate(
                prompt=prompt,
                config=config,
                model=self.MODEL
            )

            # Remove prefix if present
            if result.upper().startswith("TRANSLATIONS:"):
                result = result[13:].strip()

            # Split back into items
            translated_items = result.split("---ITEM---")
            translated_items = [item.strip() for item in translated_items if item.strip()]

            # Ensure same number of items
            if len(translated_items) == len(items):
                return translated_items
            else:
                print("[TranslationService] Item count mismatch, falling back to individual translation")
                return [await self._translate_text(item, source_language, target_language) for item in items]

        except Exception as e:
            print(f"[TranslationService] List translation failed: {e}")
            return items


# Singleton instance
_translation_service = None

def get_translation_service() -> TranslationService:
    """Get or create the translation service singleton"""
    global _translation_service
    if _translation_service is None:
        _translation_service = TranslationService()
    return _translation_service
