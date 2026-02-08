"""
PDF document analysis

Handles PDF extraction and analysis for educational content.
"""

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

import os
import tempfile
from typing import Dict, Any, Optional, Tuple, List

from app.core import get_logger

logger = get_logger(__name__, component="pdf_analyzer")
from .base import BaseAnalyzer


class PDFAnalyzer(BaseAnalyzer):
    """Analyzes PDF documents for educational content"""

    # Threshold for "massive" documents that warrant multiple videos
    MASSIVE_DOC_PAGES = 15

    async def analyze(self, file_path: str, file_id: str) -> Dict[str, Any]:
        """Analyze a PDF document using direct attachment (no text extraction)."""
        total_pages = None
        if fitz:
            try:
                doc = fitz.open(file_path)
                total_pages = len(doc)
                doc.close()
            except Exception:
                total_pages = None

        pdf_part = None
        content_sample = "PDF attached. Analyze the document directly from the file."

        coverage_part, coverage_note = self._build_coverage_pdf_part(file_path, total_pages)
        if coverage_part:
            pdf_part = coverage_part
            content_sample = coverage_note
            logger.info("Using coverage PDF slice for analysis", extra={
                "total_pages": total_pages,
                "file_path": file_path
            })
        else:
            pdf_part = self._build_pdf_part(file_path)
            logger.info("Using full PDF for analysis", extra={
                "total_pages": total_pages,
                "file_path": file_path
            })

        # Use Gemini to analyze the content
        analysis = await self._gemini_analyze(pdf_part, total_pages, content_sample)

        return {
            "analysis_id": f"analysis_{file_id}",
            "file_id": file_id,
            "material_type": "pdf",
            "total_content_pages": total_pages if total_pages is not None else 0,
            **analysis
        }

    def _build_pdf_part(self, file_path: str):
        """Build a Gemini-compatible PDF Part attachment."""
        try:
            with open(file_path, "rb") as f:
                pdf_bytes = f.read()
        except Exception:
            logger.warning("Failed to read PDF bytes for analysis", extra={"file_path": file_path})
            return None
        logger.info("Read PDF bytes for analysis", extra={
            "file_path": file_path,
            "byte_count": len(pdf_bytes)
        })
        return self._build_pdf_part_from_bytes(pdf_bytes)

    def _build_pdf_part_from_bytes(self, pdf_bytes: bytes):
        try:
            return self.engine.types.Part.from_data(
                data=pdf_bytes,
                mime_type="application/pdf"
            )
        except AttributeError:
            try:
                return self.engine.types.Part.from_bytes(
                    data=pdf_bytes,
                    mime_type="application/pdf"
                )
            except Exception:
                return None
        except Exception:
            return None

    def _build_prompt_contents(self, prompt: str, pdf_part):
        if not pdf_part:
            return None
        logger.info("Built list payload for PDF analysis", extra={
            "parts": 2,
            "ordering": "attachment_then_prompt"
        })
        return [pdf_part, prompt]

    def _build_coverage_pdf_part(
        self, file_path: str, total_pages: Optional[int]
    ) -> Tuple[Optional[Any], Optional[str]]:
        """Build a representative PDF slice covering start/middle/end pages."""
        if not fitz or not total_pages or total_pages < 8:
            return None, None

        indices = self._sample_page_indices(total_pages)
        if not indices:
            return None, None

        tmp_path = None
        try:
            doc = fitz.open(file_path)
            new_doc = fitz.open()
            for idx in indices:
                new_doc.insert_pdf(doc, from_page=idx, to_page=idx)

            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
                tmp_path = tmp_file.name
            new_doc.save(tmp_path)
            new_doc.close()
            doc.close()

            with open(tmp_path, "rb") as f:
                pdf_bytes = f.read()
            part = self._build_pdf_part_from_bytes(pdf_bytes)

            pages_note = ", ".join(str(i + 1) for i in indices)
            note = (
                "PDF attached contains representative pages across the document "
                f"(pages: {pages_note}). Analyze overall structure and topics."
            )
            return part, note
        except Exception:
            return None, None
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

    def _sample_page_indices(self, total_pages: int) -> List[int]:
        """Select representative page indices (0-based) across the document."""
        if total_pages <= 0:
            return []
        if total_pages <= 6:
            return list(range(total_pages))

        mid = total_pages // 2
        candidates = {0, 1, mid, min(mid + 1, total_pages - 1), total_pages - 2, total_pages - 1}
        return sorted(i for i in candidates if 0 <= i < total_pages)

    async def _gemini_analyze(
        self,
        pdf_part,
        total_pages: Optional[int],
        content_sample: str,
    ) -> Dict[str, Any]:
        """Use Gemini to analyze PDF content and suggest video topics"""

        # Determine if document is massive (warrants multiple videos)
        total_pages_safe = total_pages or 0
        is_massive = total_pages_safe >= self.MASSIVE_DOC_PAGES

        content_sample = content_sample or "PDF attached. Analyze the document directly from the file."

        size_note = (
            "This is a LARGE document - consider splitting into logical chapter-based videos"
            if is_massive else
            "This is a standard-sized document - create ONE comprehensive video"
        )
        if total_pages is None:
            size_note = "Page count unavailable - infer structure from the PDF content."
        instructions = (
            "LARGE DOCUMENT INSTRUCTIONS:\n"
            "Since this is a large document with multiple distinct chapters/sections:\n"
            "- Create separate video topics ONLY if there are clearly distinct chapters\n"
            "- Each video should cover ONE complete chapter thoroughly\n"
            "- Maximum 3-4 videos even for large documents\n"
            "- Each video should be 15-25 minutes (comprehensive)"
            if is_massive else
            "STANDARD DOCUMENT INSTRUCTIONS:\n"
            "Create ONE comprehensive video that covers ALL the material:\n"
            "- The video should be thorough enough to REPLACE reading the document\n"
            "- Include all key concepts, proofs/algorithms, and examples\n"
            "- Target duration: 15-25 minutes for complete coverage\n"
            "- Show step-by-step explanations visually"
        )
        closing_instruction = (
            "If the document has 5+ clearly distinct chapters, you may suggest up to 3 separate videos. "
            "Otherwise, create ONE comprehensive video."
            if is_massive else
            "Create exactly ONE comprehensive video covering everything."
        )

        from app.services.infrastructure.llm import format_prompt
        prompt = format_prompt(
            "ANALYZE_PDF_CONTENT",
            total_pages=total_pages_safe,
            size_note=size_note,
            content_sample=content_sample,
            instructions=instructions,
            detected_math_elements=total_pages_safe * 3,
            closing_instruction=closing_instruction
        )

        # Define response schema for structured JSON output
        response_schema = {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "main_subject": {"type": "string"},
                "subject_area": {"type": "string", "enum": ["math", "cs", "physics", "economics", "biology", "engineering", "general"]},
                "key_concepts": {"type": "array", "items": {"type": "string"}},
                "detected_math_elements": {"type": "integer"},
                "document_structure": {"type": "string"},
                "suggested_topics": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "index": {"type": "integer"},
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "estimated_duration": {"type": "integer"},
                            "complexity": {"type": "string"},
                            "subject_area": {"type": "string"},
                            "subtopics": {"type": "array", "items": {"type": "string"}},
                            "prerequisites": {"type": "array", "items": {"type": "string"}},
                            "visual_ideas": {"type": "array", "items": {"type": "string"}}
                        },
                        "required": ["index", "title", "description", "estimated_duration", "complexity"]
                    }
                },
                "estimated_total_videos": {"type": "integer"}
            },
            "required": ["summary", "main_subject", "subject_area", "key_concepts", "suggested_topics", "estimated_total_videos"]
        }

        from app.services.infrastructure.llm import PromptConfig
        config = PromptConfig(
            temperature=0.7,
            max_output_tokens=4096,
            timeout=90,
            response_format="json"
        )

        contents = self._build_prompt_contents(prompt, pdf_part)
        if contents is None:
            logger.warning("PDF analysis has no attachment content; prompt-only request")
        result = await self.engine.generate(
            prompt=prompt,
            config=config,
            response_schema=response_schema,
            contents=contents
        )

        response_text = result.get("response", "")
        if not result.get("success"):
            logger.warning(
                "PDF analysis LLM call did not return valid JSON",
                extra={
                    "error": result.get("error"),
                    "error_reason": result.get("error_reason"),
                    "response_preview": response_text[:500],
                },
            )
        else:
            logger.info(
                "PDF analysis LLM call succeeded",
                extra={"response_length": len(response_text)},
            )
        return self._parse_json_response(response_text)
