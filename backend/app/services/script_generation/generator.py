"""
Script generation coordinator

Combines outline generation (Phase 1) and section generation (Phase 2).
Maintains the public ScriptGenerator interface used elsewhere.
"""

from typing import Dict, Any, Optional

from app.services.parsing import parse_json_response
from .base import BaseScriptGenerator
from .outline_builder import OutlineBuilder
from .section_generator import SectionGenerator


class ScriptGenerator:
    """Generates detailed video scripts using a two-phase approach."""

    LANGUAGE_NAMES = {
        "en": "English",
        "fr": "French",
        "es": "Spanish",
        "de": "German",
        "it": "Italian",
        "pt": "Portuguese",
        "zh": "Chinese",
        "ja": "Japanese",
        "ko": "Korean",
        "ar": "Arabic",
        "ru": "Russian",
        "hy": "Armenian",
    }

    def __init__(self, cost_tracker: Optional[object] = None):
        self.base = BaseScriptGenerator(cost_tracker)
        self.outline_builder = OutlineBuilder(self.base)
        self.section_generator = SectionGenerator(self.base)

    async def generate_script(
        self,
        file_path: str,
        topic: Dict[str, Any],
        max_duration_minutes: int = 20,
        video_mode: str = "comprehensive",
        language: str = "en",
        content_focus: str = "as_document",
        document_context: str = "auto",
    ) -> Dict[str, Any]:
        # Extract content and detect language
        content = await self.base.extract_content(file_path)
        detected_language = await self.base.detect_language(content[:5000])

        output_language = self._determine_output_language(language, detected_language)
        language_name = self.LANGUAGE_NAMES.get(output_language, "English")
        detected_language_name = self.LANGUAGE_NAMES.get(detected_language, "English")
        language_instruction = self._build_language_instruction(output_language, detected_language, detected_language_name, language_name)
        context_instructions = self._build_context_instructions(document_context)

        # Phase 1: Outline
        outline = await self.outline_builder.build_outline(
            content=content,
            topic=topic,
            video_mode=video_mode,
            language_instruction=language_instruction,
            language_name=language_name,
            content_focus=content_focus,
            context_instructions=context_instructions,
        )

        # Phase 2: Sections
        generated_sections = await self.section_generator.generate_sections(
            outline=outline,
            content=content,
            video_mode=video_mode,
            language_name=language_name,
            language_instruction=language_instruction,
        )

        # Assemble script
        learning_objectives = outline.get("learning_objectives", [])
        script = {
            "title": outline.get("title", topic.get("title", "Educational Content")),
            "subject_area": outline.get("subject_area", "general"),
            "overview": outline.get("overview", ""),
            "learning_objectives": learning_objectives,
            "sections": generated_sections,
        }

        script = self.section_generator.validate_script(script, topic)

        # Duration estimation from narration length (prior to segmentation)
        for section in script.get("sections", []):
            narration_len = len(section.get("narration", ""))
            section["duration_seconds"] = max(30, int(narration_len / self.base.chars_per_second))

        script["total_duration_seconds"] = sum(s.get("duration_seconds", 0) for s in script.get("sections", []))

        # Segment narration for TTS
        script = self.section_generator.segment_narrations(script)

        # Metadata
        script["document_analysis"] = outline.get("document_analysis", {})
        script["output_language"] = output_language
        script["source_language"] = detected_language
        script["video_mode"] = video_mode
        script["cost_summary"] = self.base.cost_tracker.get_summary()

        return script

    def _determine_output_language(self, language: str, detected_language: str) -> str:
        if language == "auto" or language == detected_language:
            return detected_language
        return language

    def _build_language_instruction(
        self,
        output_language: str,
        detected_language: str,
        detected_language_name: str,
        language_name: str,
    ) -> str:
        if output_language != detected_language:
            return (
                f"\n\nIMPORTANT: The source material is in {detected_language_name}. "
                f"Generate ALL narration text in {language_name}. Translate content accurately while maintaining educational clarity."
            )
        return f"\n\nGenerate all narration in {language_name} (the document's original language)."

    def _build_context_instructions(self, document_context: str) -> str:
        if document_context == "standalone":
            return (
                """
DOCUMENT CONTEXT: STANDALONE CONTENT
- Explain ALL referenced methods/concepts that aren't common knowledge
- Don't assume viewers know specialized techniques
- Make the video self-contained and accessible
"""
            )
        if document_context == "series":
            return (
                """
DOCUMENT CONTEXT: PART OF A SERIES
- You CAN assume prior chapters/lectures have been covered
- Brief reminders of prior concepts are sufficient ("recall that...")
- Focus on NEW material introduced in this part
"""
            )
        return (
            """
DOCUMENT CONTEXT: AUTO-DETECT
Analyze if this is standalone content or part of a series, and adjust accordingly.
"""
        )
