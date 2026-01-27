"""
Base utilities for script generation

Provides shared configuration and utilities.
ALL Gemini calls go through PromptingEngine.
"""

import os
from typing import Optional

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

from app.config.models import get_model_config, get_thinking_config
from app.services.cost_tracker import CostTracker
from app.services.parsing import parse_json_response


class BaseScriptGenerator:
    """Shared utilities and configuration for script generation."""

    TARGET_SEGMENT_DURATION = 12  # seconds
    CHARS_PER_SECOND = 12.5       # ~150 wpm

    def __init__(self, cost_tracker: Optional[CostTracker] = None):
        # Model configuration
        self._script_config = get_model_config("script_generation")
        self._lang_detect_config = get_model_config("language_detection")

        self.MODEL = self._script_config.model_name
        self.LANGUAGE_DETECTION_MODEL = self._lang_detect_config.model_name
        self.cost_tracker = cost_tracker or CostTracker()

        # Use centralized prompting engine - NO direct client!
        from app.services.prompting_engine import PromptingEngine, PromptConfig
        self.engine = PromptingEngine("script_generation", self.cost_tracker)
        self.lang_engine = PromptingEngine("language_detection", self.cost_tracker)
        
        # Config for prompting
        thinking_config = get_thinking_config(self._script_config)
        self.prompt_config = PromptConfig(
            enable_thinking=bool(thinking_config),
            temperature=1.0,
            timeout=180.0
        )

    @property
    def chars_per_second(self) -> float:
        return self.CHARS_PER_SECOND

    @property
    def target_segment_duration(self) -> int:
        return self.TARGET_SEGMENT_DURATION

    async def detect_language(self, text_sample: str) -> str:
        """Detect language using PromptingEngine."""
        if not text_sample.strip():
            return "en"

        try:
            from app.services.prompting_engine import format_prompt, PromptConfig
            
            prompt = format_prompt('LANGUAGE_DETECTION', content=text_sample[:2000])
            config = PromptConfig(temperature=0.1, timeout=30.0)
            
            result = await self.lang_engine.generate(prompt, config)
            
            if result["success"]:
                detected = result["response"].strip().lower()[:2]
                valid_codes = {"en", "fr", "es", "de", "it", "pt", "zh", "ja", "ko", "ar", "ru", "hy"}
                return detected if detected in valid_codes else "en"
            
            return "en"
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

    async def generate_with_engine(
        self,
        prompt: str,
        response_format: str = "json",
        response_schema: Optional[dict] = None,
        timeout: float = 120.0
    ) -> dict:
        """
        Unified generation method using PromptingEngine.
        
        Args:
            prompt: The prompt text
            response_format: "text" or "json"
            response_schema: Optional JSON schema for structured output
            timeout: Timeout in seconds
            
        Returns:
            Result dict from engine
        """
        from app.services.prompting_engine import PromptConfig
        
        config = PromptConfig(
            enable_thinking=self.prompt_config.enable_thinking,
            temperature=self.prompt_config.temperature,
            response_format=response_format,
            timeout=timeout
        )
        
        return await self.engine.generate(prompt, config)
