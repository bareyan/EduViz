"""
Text file analysis

Handles .txt and .tex file analysis for educational content.
"""

import asyncio
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
        
        prompt = f"""You are an expert educator preparing comprehensive educational video content.

Analyze this text content and suggest video topics.
IMPORTANT: Detect the SUBJECT AREA (math, computer science, physics, economics, biology, engineering, general).

DOCUMENT INFO:
- Estimated pages: {total_pages}

CONTENT:
{content_sample}

Create ONE comprehensive video that covers ALL the material:
- The video should be thorough enough to REPLACE reading the document
- Include all key concepts and examples
- Target duration: 15-25 minutes

Respond with ONLY valid JSON (no markdown, no code blocks):
{{
    "summary": "Comprehensive summary of the material",
    "main_subject": "The primary topic",
    "subject_area": "math|cs|physics|economics|biology|engineering|general",
    "key_concepts": ["all", "major", "concepts"],
    "detected_math_elements": 3,
    "suggested_topics": [
        {{
            "index": 0,
            "title": "[Descriptive Topic Name]",
            "description": "Comprehensive video covering all material",
            "estimated_duration": 20,
            "complexity": "intermediate",
            "subtopics": ["all", "major", "sections"],
            "prerequisites": ["required background"]
        }}
    ],
    "estimated_total_videos": 1
}}"""

        response = await asyncio.to_thread(
            self.client.models.generate_content,
            model=self.MODEL,
            contents=prompt
        )
        
        return self._parse_json_response(response.text)
