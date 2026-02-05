"""
Unified Script Generator - Uses PromptingEngine

Refactored to use the centralized prompting engine instead of direct client calls.
"""

from typing import Dict, Any, Optional

from app.core import get_logger
from app.services.infrastructure.llm import PromptingEngine, PromptConfig, CostTracker

from .base import BaseScriptGenerator
from .outline_builder import OutlineBuilder
from .section_generator import SectionGenerator
from .overview_generator import OverviewGenerator

logger = get_logger(__name__, component="script_generator")


class ScriptGenerator:
    """Generates video scripts using unified prompting engine."""

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

    def __init__(self, cost_tracker: Optional[CostTracker] = None, pipeline_name: Optional[str] = None):
        self.cost_tracker = cost_tracker or CostTracker()
        
        # Initialize prompting engine
        self.engine = PromptingEngine("script_generation", self.cost_tracker, pipeline_name=pipeline_name)
        self.lang_engine = PromptingEngine("language_detection", self.cost_tracker, pipeline_name=pipeline_name)
        
        # Keep base for utility functions (will be updated to use engine)
        self.base = BaseScriptGenerator(self.cost_tracker, pipeline_name=pipeline_name)
        
        # Initialize sub-generators (they'll use base's client for now)
        self.outline_builder = OutlineBuilder(self.base)
        self.section_generator = SectionGenerator(self.base)
        self.overview_generator = OverviewGenerator(self.base)

    async def generate_script(
        self,
        file_path: str,
        topic: Dict[str, Any],
        video_mode: str = "comprehensive",
        language: str = "en",
        content_focus: str = "as_document",
        document_context: str = "auto",
    ) -> Dict[str, Any]:
        """Generate script using unified prompting engine"""
        
        # Extract content
        content = await self.base.extract_content(file_path)
        
        # Detect language using engine
        detected_language = await self._detect_language(content[:5000])

        output_language = self._determine_output_language(language, detected_language)
        language_name = self.LANGUAGE_NAMES.get(output_language, "English")
        detected_language_name = self.LANGUAGE_NAMES.get(detected_language, "English")
        language_instruction = self._build_language_instruction(
            output_language, detected_language,
            detected_language_name, language_name
        )

        # OVERVIEW MODE
        if video_mode == "overview":
            logger.info("Using OVERVIEW mode", extra={"video_mode": video_mode})
            script = await self.overview_generator.generate_overview_script(
                content=content,
                topic=topic,
                language_name=language_name,
                language_instruction=language_instruction,
            )
            
            # Duration estimation
            for section in script.get("sections", []):
                narration_len = len(section.get("narration", ""))
                section["duration_seconds"] = max(30, int(narration_len / self.base.chars_per_second))
            
            script["total_duration_seconds"] = sum(
                s.get("duration_seconds", 0) for s in script.get("sections", [])
            )
            
            # Segment narration
            script = self.section_generator.segment_narrations(script)
            
            return {
                "script": script,
                "mode": "overview",
                "output_language": output_language,
                "detected_language": detected_language,
            }

        # COMPREHENSIVE MODE
        logger.info("Using COMPREHENSIVE mode", extra={"video_mode": video_mode})
        
        # Phase 1: Generate outline
        outline = await self.outline_builder.build_outline(
            content=content,
            topic=topic,
            # max_duration_minutes=max_duration_minutes,
            language_name=language_name,
            language_instruction=language_instruction,
            content_focus=content_focus,
            document_context=document_context,
        )

        # Phase 2: Generate sections (returns a list of section dicts)
        sections = await self.section_generator.generate_sections(
            outline=outline,
            content=content,
            topic=topic,
            language_name=language_name,
            language_instruction=language_instruction,
        )

        # Add duration estimation for each section
        for section in sections:
            if "duration_seconds" not in section:
                narration_len = len(section.get("narration", ""))
                section["duration_seconds"] = max(30, int(narration_len / self.base.chars_per_second))

        # Build proper script structure (matching overview mode format)
        script = {
            "title": outline.get("title", topic.get("title", "Educational Content")),
            "subject_area": outline.get("subject_area", topic.get("subject_area", "general")),
            "overview": outline.get("overview", ""),
            "learning_objectives": outline.get("learning_objectives", []),
            "sections": sections,
            "total_duration_seconds": sum(s.get("duration_seconds", 0) for s in sections),
        }
        
        # Segment narrations for proper subtitle/audio chunking
        script = self.section_generator.segment_narrations(script)

        return {
            "script": script,
            "outline": outline,
            "mode": "comprehensive",
            "output_language": output_language,
            "detected_language": detected_language,
        }

    async def _detect_language(self, content_sample: str) -> str:
        """Detect language using prompting engine"""
        from app.services.infrastructure.llm import format_prompt
        prompt = format_prompt(
            "LANGUAGE_DETECTION",
            content=content_sample
        )
        
        config = PromptConfig(temperature=0.1, timeout=30.0)
        result = await self.lang_engine.generate(prompt, config)
        
        if result["success"]:
            lang = result["response"].strip().lower()
            # Validate it's a 2-letter code
            if len(lang) == 2 and lang.isalpha():
                return lang
        
        # Default fallback
        return "en"

    def _determine_output_language(self, requested: str, detected: str) -> str:
        """Determine output language"""
        if requested and requested != "auto":
            return requested
        return detected

    def _build_language_instruction(
        self,
        output_lang: str,
        detected_lang: str,
        detected_name: str,
        output_name: str
    ) -> str:
        """Build language instruction for prompts"""
        if output_lang == detected_lang:
            return f"Generate ALL content in {output_name}."
        else:
            return f"The source document is in {detected_name}, but generate ALL content in {output_name}."

    def get_cost_summary(self) -> Dict[str, Any]:
        """Get cost summary"""
        return self.cost_tracker.get_summary()

    def print_cost_summary(self):
        """Log cost summary using structured logging"""
        summary = self.get_cost_summary()
        logger.info("Script generation cost summary", extra={"cost_summary": summary})
