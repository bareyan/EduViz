"""
Text file analysis

Handles .txt and .tex file analysis for educational content.
"""

from typing import Dict, Any
from .base import BaseAnalyzer


class TextAnalyzer(BaseAnalyzer):
    """Analyzes text files (.txt, .tex) for educational content"""

    async def analyze(self, file_path: str, file_id: str) -> Dict[str, Any]:
        """Analyze a text file"""
        # Read the text file
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            full_text = f.read()

        # Estimate "pages" based on content length (roughly 3000 chars per page)
        estimated_pages = max(1, len(full_text) // 3000)

        # Use Gemini to analyze the content
        analysis = await self._gemini_analyze(full_text, estimated_pages)

        return {
            "analysis_id": f"analysis_{file_id}",
            "file_id": file_id,
            "material_type": "text",
            "total_content_pages": estimated_pages,
            **analysis
        }

    async def _gemini_analyze(self, text: str, total_pages: int) -> Dict[str, Any]:
        """Use Gemini to analyze text content and suggest video topics"""
        # Use representative sample for long texts
        content_sample = self._get_representative_sample(text, max_chars=15000)

        from app.services.infrastructure.llm import format_prompt
        prompt = format_prompt(
            "ANALYZE_TEXT_CONTENT",
            total_pages=total_pages,
            content_sample=content_sample
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
                            "subtopics": {"type": "array", "items": {"type": "string"}},
                            "prerequisites": {"type": "array", "items": {"type": "string"}}
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

        result = await self.engine.generate(
            prompt=prompt,
            config=config,
            response_schema=response_schema
        )

        response_text = result.get("response", "") if result.get("success") else ""
        return self._parse_json_response(response_text)
