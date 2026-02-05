"""
Base utilities for script generation

Provides shared configuration and utilities.
ALL Gemini calls go through PromptingEngine.
"""

import os
from pathlib import Path
from typing import Optional, TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.services.infrastructure.llm import PromptConfig

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

from app.config.models import get_model_config, get_thinking_config
from app.services.infrastructure.llm import CostTracker
from app.services.infrastructure.parsing import parse_json_response
from app.core import get_logger

logger = get_logger(__name__, component="script_generation_base")


class BaseScriptGenerator:
    """Shared utilities and configuration for script generation."""

    TARGET_SEGMENT_DURATION = 12  # seconds
    CHARS_PER_SECOND = 12.5       # ~150 wpm

    def __init__(self, cost_tracker: Optional[CostTracker] = None, pipeline_name: Optional[str] = None):
        # Model configuration (pipeline-aware)
        self._script_config = get_model_config("script_generation")
        self._lang_detect_config = get_model_config("language_detection")

        self.MODEL = self._script_config.model_name
        self.LANGUAGE_DETECTION_MODEL = self._lang_detect_config.model_name
        self.cost_tracker = cost_tracker or CostTracker()

        # Use centralized prompting engine - NO direct client!
        from app.services.infrastructure.llm import PromptingEngine, PromptConfig
        self.engine = PromptingEngine("script_generation", self.cost_tracker, pipeline_name=pipeline_name)
        self.lang_engine = PromptingEngine("language_detection", self.cost_tracker, pipeline_name=pipeline_name)
        
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
            from app.services.infrastructure.llm import format_prompt, PromptConfig
            
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

    def get_pdf_page_count(self, file_path: str) -> Optional[int]:
        """Return total pages in a PDF, or None if unavailable."""
        if not fitz:
            return None
        try:
            doc = fitz.open(file_path)
            total_pages = len(doc)
            doc.close()
            return total_pages
        except Exception:
            return None

    def read_pdf_bytes(self, file_path: str) -> Optional[bytes]:
        """Read PDF bytes from disk safely."""
        try:
            with open(file_path, "rb") as f:
                return f.read()
        except Exception:
            logger.warning("Failed to read PDF bytes", extra={"file_path": file_path})
            return None

    def build_pdf_part(self, file_path: str):
        """Build a Gemini-compatible PDF Part attachment."""
        pdf_bytes = self.read_pdf_bytes(file_path)
        if not pdf_bytes:
            return None
        try:
            logger.info("Building PDF Part for attachment", extra={
                "file_path": file_path,
                "byte_count": len(pdf_bytes)
            })
            return self.engine.types.Part.from_data(
                data=pdf_bytes,
                mime_type="application/pdf"
            )
        except AttributeError:
            try:
                logger.info("Falling back to Part.from_bytes for PDF attachment", extra={
                    "file_path": file_path,
                    "byte_count": len(pdf_bytes)
                })
                return self.engine.types.Part.from_bytes(
                    data=pdf_bytes,
                    mime_type="application/pdf"
                )
            except Exception:
                logger.warning("Failed to build PDF Part via from_bytes", extra={
                    "file_path": file_path
                })
                return None
        except Exception:
            logger.warning("Failed to build PDF Part via from_data", extra={
                "file_path": file_path
            })
            return None

    def build_prompt_contents(self, prompt: str, attachment_part: Any):
        """Build contents payload with a text prompt and an attachment part."""
        if not attachment_part:
            return None
        # Gemini document processing expects the PDF part first, then the text prompt.
        logger.info("Built list payload for prompt + attachment", extra={
            "parts": 2,
            "ordering": "attachment_then_prompt"
        })
        return [attachment_part, prompt]

    def slice_pdf_pages(
        self,
        source_path: str,
        start_page: Optional[int],
        end_page: Optional[int],
        output_path: str
    ) -> Optional[str]:
        """Slice a PDF to a specific page range (1-based, inclusive)."""
        if not fitz:
            return None
        if start_page is None or end_page is None:
            return None
        try:
            start = int(start_page)
            end = int(end_page)
        except Exception:
            return None
        if start < 1 or end < 1 or end < start:
            return None
        try:
            doc = fitz.open(source_path)
            total = len(doc)
            start = max(1, min(start, total))
            end = max(1, min(end, total))
            if start > end:
                doc.close()
                return None
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            new_doc = fitz.open()
            new_doc.insert_pdf(doc, from_page=start - 1, to_page=end - 1)
            new_doc.save(str(output_file))
            new_doc.close()
            doc.close()
            return str(output_file)
        except Exception:
            return None

    def parse_json(self, text: str):
        """Parse JSON using shared utilities, returning dict or {}."""
        return parse_json_response(text) or {}

    async def generate_with_engine(
        self,
        prompt: str,
        config: Optional["PromptConfig"] = None,
        response_schema: Optional[dict] = None,
        contents: Optional[Any] = None
    ) -> Optional[str]:
        """
        Unified generation method using PromptingEngine.
        
        Args:
            prompt: The prompt text
            config: Optional PromptConfig override
            response_schema: Optional JSON schema for structured output
            
        Returns:
            Response text if successful, else None
        """
        from app.services.infrastructure.llm import PromptConfig
        
        config = config or PromptConfig(
            enable_thinking=self.prompt_config.enable_thinking,
            temperature=self.prompt_config.temperature,
            timeout=self.prompt_config.timeout,
            response_format="json"
        )
        if response_schema is not None:
            config.response_schema = response_schema
        
        if contents is not None:
            try:
                logger.info(
                    "LLM contents payload prepared",
                    extra={
                        "contents_type": type(contents).__name__,
                        "contents_len": len(contents) if hasattr(contents, "__len__") else None,
                    },
                )
            except Exception:
                pass

        result = await self.engine.generate(
            prompt=prompt,
            config=config,
            contents=contents
        )
        if result.get("success"):
            return result.get("response", "")

        response_text = result.get("response", "")
        if response_text:
            logger.warning(
                "LLM call returned non-success but has response; attempting to parse",
                extra={
                    "error": result.get("error"),
                    "error_reason": result.get("error_reason"),
                    "response_preview": response_text[:500],
                },
            )
            return response_text

        logger.warning(
            "LLM call failed with empty response",
            extra={
                "error": result.get("error"),
                "error_reason": result.get("error_reason"),
            },
        )
        return None
