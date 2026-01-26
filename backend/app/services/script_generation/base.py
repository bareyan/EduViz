"""
Base utilities for script generation

Provides shared configuration, Gemini client setup, cost tracking, and
helpers used by outline and section generators.
"""

import os
from typing import Optional

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

from app.config.models import get_model_config, get_thinking_config
from app.services.gemini.client import create_client, get_types_module, GenerationConfig as UnifiedGenerationConfig
from app.services.manim_generator.cost_tracker import CostTracker
from app.services.parsing import parse_json_response


class BaseScriptGenerator:
    """Shared utilities and configuration for script generation."""

    TARGET_SEGMENT_DURATION = 12  # seconds
    CHARS_PER_SECOND = 12.5       # ~150 wpm

    def __init__(self, cost_tracker: Optional[CostTracker] = None):
        # Model configuration - loaded from centralized config
        self._script_config = get_model_config("script_generation")
        self._lang_detect_config = get_model_config("language_detection")

        self.MODEL = self._script_config.model_name
        self.LANGUAGE_DETECTION_MODEL = self._lang_detect_config.model_name

        # Unified client automatically detects Gemini API vs Vertex AI
        self.client = create_client()
        self.types = get_types_module()
        self.cost_tracker = cost_tracker or CostTracker()

        thinking_config = get_thinking_config(self._script_config)
        if thinking_config:
            self.generation_config = UnifiedGenerationConfig(
                thinking_config=thinking_config,
            )
        else:
            self.generation_config = None

    @property
    def chars_per_second(self) -> float:
        return self.CHARS_PER_SECOND

    @property
    def target_segment_duration(self) -> int:
        return self.TARGET_SEGMENT_DURATION

    async def detect_language(self, text_sample: str) -> str:
        """Detect the language of the document using Gemini."""
        if not self.client or not text_sample.strip():
            return "en"

        try:
            prompt = f"""Analyze this text and identify its primary language.
Respond with ONLY a 2-letter ISO 639-1 language code (e.g., en, fr, es, de, zh, ja, ko, ru, ar, hy).
If the text contains multiple languages, identify the primary/dominant one.
If unsure, respond with \"en\".

TEXT SAMPLE:
{text_sample[:2000]}

LANGUAGE CODE:"""

            response = self.client.models.generate_content(
                model=self.LANGUAGE_DETECTION_MODEL,
                contents=prompt,
                config=self.types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=10,
                ),
            )

            # Track cost for language detection
            self.cost_tracker.track_usage(response, self.LANGUAGE_DETECTION_MODEL)

            detected = response.text.strip().lower()[:2]
            valid_codes = {"en", "fr", "es", "de", "it", "pt", "zh", "ja", "ko", "ar", "ru", "hy"}
            return detected if detected in valid_codes else "en"

        except Exception:
            return "en"

    async def extract_content(self, file_path: str) -> str:
        """Extract text content from supported files."""
        ext = os.path.splitext(file_path)[1].lower()

        if ext == ".pdf" and fitz:
            doc = fitz.open(file_path)
            text = ""
            for page in doc:
                text += page.get_text() + "\n\n"
            doc.close()
            return text
        if ext in [".tex", ".txt"]:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        return ""

    def parse_json(self, text: str):
        """Parse JSON using shared utilities, returning dict or {}."""
        return parse_json_response(text) or {}
