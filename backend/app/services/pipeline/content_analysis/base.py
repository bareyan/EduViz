"""
Base analyzer class with shared logic for all analysis types
"""

from typing import Dict, Any
from typing import Optional

from app.config.models import get_model_config
from app.services.infrastructure.llm import PromptingEngine
from app.services.infrastructure.parsing import parse_json_response


class BaseAnalyzer:
    """Base class with shared analysis functionality"""

    def __init__(self, pipeline_name: Optional[str] = None):
        # Resolve model config per-instance to respect pipeline selection
        self._config = get_model_config("analysis")
        self.model = self._config.model_name

        # Use PromptingEngine for all LLM interactions
        self.engine = PromptingEngine("analysis", pipeline_name=pipeline_name)

    def _get_representative_sample(self, text: str, max_chars: int = 15000) -> str:
        """Extract a representative sample from the document for analysis.
        
        OPTIMIZATION: For analysis, we don't need the full document. We sample:
        - Beginning (intro/abstract): 40% of budget
        - Middle (core content): 40% of budget
        - End (conclusions): 20% of budget
        
        This reduces token costs while maintaining analysis quality.
        """
        if len(text) <= max_chars:
            return text

        # Calculate section sizes
        intro_size = int(max_chars * 0.4)
        middle_size = int(max_chars * 0.4)
        ending_size = max_chars - intro_size - middle_size

        # Get beginning
        intro = text[:intro_size]

        # Get middle section (center of document)
        middle_start = max(intro_size, (len(text) - middle_size) // 2)
        middle = text[middle_start:middle_start + middle_size]

        # Get ending
        ending = text[-ending_size:]

        # Combine with markers
        sample = f"{intro}\n\n[...content continues...]\n\n{middle}\n\n[...content continues...]\n\n{ending}"

        return sample

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """Parse JSON from Gemini response using shared utilities"""
        result = parse_json_response(text)
        if not result:
            # Return a default structure
            return {
                "summary": "Failed to parse analysis",
                "main_subject": "Unknown",
                "difficulty_level": "intermediate",
                "key_concepts": [],
                "detected_math_elements": 0,
                "suggested_topics": [{
                    "index": 0,
                    "title": "Introduction to the Topic",
                    "description": "An overview of the mathematical concepts",
                    "estimated_duration": 10,
                    "complexity": "intermediate",
                    "subtopics": ["Overview"],
                    "prerequisites": [],
                    "visual_ideas": ["Basic animations"]
                }],
                "estimated_total_videos": 1
            }
        return result
