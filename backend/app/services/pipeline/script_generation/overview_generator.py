"""
Overview script generator

Generates a short, informative overview video script (~5 minutes) in a single prompt.
Unlike the comprehensive mode which uses a two-phase approach (outline + sections),
overview mode generates everything at once for efficiency.
"""

import asyncio
from typing import Dict, Any, List

from app.services.infrastructure.parsing import parse_json_response
from .base import BaseScriptGenerator


class OverviewGenerator:
    """Generates concise overview video scripts in a single prompt."""

    TARGET_DURATION_MINUTES = 5  # Target ~5 minute videos
    MAX_SECTIONS = 5  # Keep it short and focused

    def __init__(self, base: BaseScriptGenerator):
        self.base = base

    async def generate_overview_script(
        self,
        content: str,
        topic: Dict[str, Any],
        language_name: str,
        language_instruction: str,
    ) -> Dict[str, Any]:
        """Generate a complete overview script in a single prompt.
        
        Args:
            content: The source document content
            topic: Topic metadata (title, description, subject_area)
            language_name: Output language name (e.g., "English")
            language_instruction: Language handling instructions
            
        Returns:
            Complete script dict with title, overview, sections, etc.
        """
        # Limit content for overview - we don't need everything
        content_excerpt = content[:15000] if len(content) > 15000 else content
        
        prompt = self._build_overview_prompt(
            content=content_excerpt,
            topic=topic,
            language_name=language_name,
            language_instruction=language_instruction,
        )
        
        response_schema = self._get_response_schema()
        
        try:
            print("[OverviewGen] Generating complete overview script...")
            
            from app.services.infrastructure.llm import PromptConfig
            config = PromptConfig(
                temperature=0.7,
                max_output_tokens=8192,
                timeout=120,
                response_format="json"
            )
            
            response_text = await self.base.generate_with_engine(
                prompt=prompt,
                config=config,
                response_schema=response_schema
            )
            
            if not response_text:
                print("[OverviewGen] ERROR: Empty response from API")
                return self._fallback_script(topic)
            
            print(f"[OverviewGen] Received response: {len(response_text)} chars")
            script = parse_json_response(response_text)
            
            if not script:
                print("[OverviewGen] ERROR: Failed to parse JSON response")
                return self._fallback_script(topic)
            
            # Validate and fix sections
            script = self._validate_script(script, topic)
            
            print(f"[OverviewGen] Successfully generated script with {len(script.get('sections', []))} sections")
            return script
            
        except asyncio.TimeoutError:
            print("[OverviewGen] ERROR: Request timed out after 120 seconds")
            return self._fallback_script(topic)
        except Exception as e:
            print(f"[OverviewGen] ERROR: {type(e).__name__}: {e}")
            return self._fallback_script(topic)

    def _build_overview_prompt(
        self,
        content: str,
        topic: Dict[str, Any],
        language_name: str,
        language_instruction: str,
    ) -> str:
        """Build the single prompt for overview script generation."""
        title = topic.get("title", "Educational Content")
        description = topic.get("description", "")
        subject_area = topic.get("subject_area", "general")
        
        return f"""You are an expert educator creating a SHORT, ENGAGING overview video script.
{language_instruction}

═══════════════════════════════════════════════════════════════════════════════
                         OVERVIEW VIDEO REQUIREMENTS
═══════════════════════════════════════════════════════════════════════════════

GOAL: Create a ~5 MINUTE overview video that introduces the key concepts.
- This is NOT a comprehensive lecture - it's a quick, engaging introduction
- Focus on the BIG PICTURE and most important ideas
- Make viewers EXCITED to learn more about this topic
- Keep language clear, accessible, and engaging

STRUCTURE GUIDELINES:
- 3-5 sections total (no more!)
- Each section: 45-90 seconds of narration (roughly 70-140 words)
- Total video: approximately 5 minutes (300 seconds)

CONTENT GUIDELINES:
- Start with a hook: Why does this topic matter?
- Identify 2-4 KEY concepts from the material
- Explain each concept briefly but clearly
- Skip proofs and detailed derivations - just give the main ideas
- End with what viewers learned and what they could explore next

═══════════════════════════════════════════════════════════════════════════════

TOPIC: {title}
DESCRIPTION: {description}
SUBJECT AREA: {subject_area}
OUTPUT LANGUAGE: {language_name}

═══════════════════════════════════════════════════════════════════════════════

SOURCE MATERIAL (extract the key concepts from this):
{content}

═══════════════════════════════════════════════════════════════════════════════

Generate a COMPLETE video script with 3-5 sections. For each section, include:
- A clear title
- Engaging narration (spoken text for the video)
- TTS-ready narration (spell out math symbols, format for text-to-speech)

Respond with ONLY valid JSON matching the required schema."""

    def _get_response_schema(self) -> Dict[str, Any]:
        """Get the JSON schema for structured response."""
        return {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Engaging video title"
                },
                "subject_area": {
                    "type": "string", 
                    "description": "Subject area (math, cs, physics, etc.)"
                },
                "overview": {
                    "type": "string",
                    "description": "2-3 sentence description of what viewers will learn"
                },
                "learning_objectives": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "2-4 key learning objectives"
                },
                "sections": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {
                                "type": "string",
                                "description": "Unique section identifier (e.g., intro, concept_1, conclusion)"
                            },
                            "title": {
                                "type": "string",
                                "description": "Section title"
                            },
                            "narration": {
                                "type": "string",
                                "description": "Complete spoken narration for this section (70-140 words)"
                            },
                            "tts_narration": {
                                "type": "string",
                                "description": "TTS-ready narration with math spelled out"
                            },
                            "key_points": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "2-3 key points covered in this section"
                            },
                            "visual_type": {
                                "type": "string",
                                "description": "Type of visual (animated, static, diagram, graph)"
                            }
                        },
                        "required": ["id", "title", "narration", "tts_narration"]
                    },
                    "description": "3-5 sections for the video"
                }
            },
            "required": ["title", "overview", "sections"]
        }

    def _validate_script(self, script: Dict[str, Any], topic: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and fix the generated script."""
        # Ensure title
        if not script.get("title"):
            script["title"] = topic.get("title", "Overview")
        
        # Ensure overview
        if not script.get("overview"):
            script["overview"] = topic.get("description", "An overview of the topic.")
        
        # Ensure subject_area
        if not script.get("subject_area"):
            script["subject_area"] = topic.get("subject_area", "general")
        
        # Ensure learning_objectives
        if not script.get("learning_objectives"):
            script["learning_objectives"] = ["Understand the key concepts"]
        
        # Validate sections
        sections = script.get("sections", [])
        if not sections:
            sections = self._fallback_sections()
        
        for i, section in enumerate(sections):
            # Ensure required fields
            section["id"] = section.get("id", f"section_{i + 1}")
            section["title"] = section.get("title", f"Part {i + 1}")
            
            if not section.get("narration"):
                section["narration"] = f"This section covers {section['title']}."
            
            if not section.get("tts_narration"):
                section["tts_narration"] = section["narration"]
            
            if not section.get("key_points"):
                section["key_points"] = [section["title"]]
            
            if not section.get("visual_type"):
                section["visual_type"] = "animated"
        
        script["sections"] = sections
        return script

    def _fallback_sections(self) -> List[Dict[str, Any]]:
        """Generate fallback sections if parsing fails."""
        return [
            {
                "id": "intro",
                "title": "Introduction",
                "narration": "Welcome to this overview. Let's explore the key concepts.",
                "tts_narration": "Welcome to this overview. Let's explore the key concepts.",
                "key_points": ["Introduction to the topic"],
                "visual_type": "animated"
            },
            {
                "id": "main",
                "title": "Key Concepts",
                "narration": "The main ideas from this material include several important concepts.",
                "tts_narration": "The main ideas from this material include several important concepts.",
                "key_points": ["Core concepts"],
                "visual_type": "animated"
            },
            {
                "id": "conclusion",
                "title": "Summary",
                "narration": "In summary, we've covered the essential ideas. There's much more to explore.",
                "tts_narration": "In summary, we've covered the essential ideas. There's much more to explore.",
                "key_points": ["Summary of key points"],
                "visual_type": "static"
            }
        ]

    def _fallback_script(self, topic: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a complete fallback script if generation fails."""
        return {
            "title": topic.get("title", "Overview"),
            "subject_area": topic.get("subject_area", "general"),
            "overview": topic.get("description", "An overview of the topic."),
            "learning_objectives": ["Understand the key concepts"],
            "sections": self._fallback_sections(),
            "document_analysis": {
                "content_type": "overview",
                "complexity_level": "introductory"
            }
        }
