"""
PDF document analysis

Handles PDF extraction and analysis for educational content.
"""

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

from typing import Dict, Any
from .base import BaseAnalyzer


class PDFAnalyzer(BaseAnalyzer):
    """Analyzes PDF documents for educational content"""

    # Threshold for "massive" documents that warrant multiple videos
    MASSIVE_DOC_PAGES = 15

    async def analyze(self, file_path: str, file_id: str) -> Dict[str, Any]:
        """Analyze a PDF document"""
        if not fitz:
            raise ImportError("PyMuPDF (fitz) is required for PDF analysis")

        # Extract text from PDF
        doc = fitz.open(file_path)
        total_pages = len(doc)

        all_text = []
        for page_num in range(total_pages):
            page = doc[page_num]
            text = page.get_text()
            all_text.append(f"=== Page {page_num + 1} ===\n{text}")

        doc.close()
        full_text = "\n\n".join(all_text)

        # Use Gemini to analyze the content
        analysis = await self._gemini_analyze(full_text, total_pages)

        return {
            "analysis_id": f"analysis_{file_id}",
            "file_id": file_id,
            "material_type": "pdf",
            "total_content_pages": total_pages,
            **analysis
        }

    async def _gemini_analyze(self, text: str, total_pages: int) -> Dict[str, Any]:
        """Use Gemini to analyze text content and suggest video topics"""
        import asyncio

        # Determine if document is massive (warrants multiple videos)
        is_massive = total_pages >= self.MASSIVE_DOC_PAGES

        # OPTIMIZED: Use adaptive content sampling for analysis
        # - For short docs: use all content
        # - For long docs: use beginning (intro/abstract), middle (core content), and end (conclusions)
        content_sample = self._get_representative_sample(text, max_chars=15000)

        size_note = (
            "This is a LARGE document - consider splitting into logical chapter-based videos"
            if is_massive else
            "This is a standard-sized document - create ONE comprehensive video"
        )
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

        from app.services.prompting_engine import format_prompt
        prompt = format_prompt(
            "ANALYZE_PDF_CONTENT",
            total_pages=total_pages,
            size_note=size_note,
            content_sample=content_sample,
            instructions=instructions,
            detected_math_elements=total_pages * 3,
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

        from app.services.prompting_engine import PromptConfig
        config = PromptConfig(
            temperature=0.7,
            max_output_tokens=4096,
            timeout=90,
            response_format="json"
        )

        result = await self.engine.generate(
            prompt=prompt,
            config=config,
            response_schema=response_schema
        )

        response_text = result.get("response", "") if result.get("success") else ""
        return self._parse_json_response(response_text)
