"""
Overview script generator

Generates a short, informative overview video script (~5 minutes) in a single prompt.
Unlike the comprehensive mode which uses a two-phase approach (outline + sections),
overview mode generates everything at once for efficiency.
"""

import asyncio
import re
from typing import Dict, Any, List, Optional

from app.services.infrastructure.parsing import parse_json_response
from .base import BaseScriptGenerator
from .schema_filter import filter_section


class OverviewGenerator:
    """Generates concise overview video scripts in a single prompt."""

    TARGET_DURATION_MINUTES = 10  # Target ~5 minute videos
    MAX_SECTIONS = 7  # Keep it short and focused
    _REFERENCE_TOKEN_PATTERN = (
        r"(?:figure|fig(?:ure)?\.?|table|equation|eq\.?|appendix)\s*(?:\(|#)?\s*[A-Za-z0-9]+\s*\)?"
    )
    _REFERENCE_PATTERN = re.compile(
        r"\b(?P<kind>figure|fig(?:ure)?\.?|table|equation|eq\.?|appendix)\s*(?:\(|#)?\s*(?P<id>[A-Za-z0-9]+)\s*\)?",
        re.IGNORECASE,
    )
    _DEICTIC_REFERENCE_PATTERNS = [
        re.compile(rf"\bif you look at\s+(?:the\s+)?(?P<ref>{_REFERENCE_TOKEN_PATTERN})\s*,?\s*", re.IGNORECASE),
        re.compile(rf"\bas you can see in\s+(?:the\s+)?(?P<ref>{_REFERENCE_TOKEN_PATTERN})\s*,?\s*", re.IGNORECASE),
        re.compile(rf"\bas shown in\s+(?:the\s+)?(?P<ref>{_REFERENCE_TOKEN_PATTERN})\s*,?\s*", re.IGNORECASE),
        re.compile(rf"\blooking at\s+(?:the\s+)?(?P<ref>{_REFERENCE_TOKEN_PATTERN})\s*,?\s*", re.IGNORECASE),
    ]

    def __init__(self, base: BaseScriptGenerator):
        self.base = base

    async def generate_overview_script(
        self,
        content: str,
        topic: Dict[str, Any],
        language_name: str,
        language_instruction: str,
        pdf_path: Optional[str] = None,
        total_pages: Optional[int] = None,
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
        # Limit content for overview - we don't need everything (non-PDF only)
        content_excerpt = ""
        if content:
            content_excerpt = content
        
        prompt = self._build_overview_prompt(
            content=content_excerpt,
            topic=topic,
            language_name=language_name,
            language_instruction=language_instruction,
            pdf_attached=bool(pdf_path),
            total_pages=total_pages,
        )
        
        response_schema = self._get_response_schema()
        
        try:
            print("[OverviewGen] Generating complete overview script...")
            
            from app.services.infrastructure.llm import PromptConfig
            config = PromptConfig(
                temperature=0.7,
                max_output_tokens=int(32768*1.8),
                timeout=150,
                response_format="json"
            )
            
            contents = None
            if pdf_path:
                pdf_part = self.base.build_pdf_part(pdf_path)
                if pdf_part:
                    contents = self.base.build_prompt_contents(prompt, pdf_part)

            response_text = await self.base.generate_with_engine(
                prompt=prompt,
                config=config,
                response_schema=response_schema,
                contents=contents,
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

            # Attach PDF metadata to sections if available
            if pdf_path:
                for section in script.get("sections", []):
                    section.setdefault("source_pdf_path", pdf_path)
                    if total_pages:
                        section.setdefault("source_pages", {"start": 1, "end": total_pages})
            
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
        pdf_attached: bool,
        total_pages: Optional[int],
    ) -> str:
        """Build the single prompt for overview script generation."""
        title = topic.get("title", "Educational Content")
        description = topic.get("description", "")
        subject_area = topic.get("subject_area", "general")
        
        total_note = f"{total_pages}" if total_pages is not None else "unknown"
        pdf_note = ""
        if pdf_attached:
            pdf_note = (
                "\nPDF NOTE:\n"
                "- The source PDF is ATTACHED. Use it directly.\n"
                f"- Total pages: {total_note}\n"
            )

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
- Identify KEY concepts from the material
- Explain each concept briefly but clearly
- End with what viewers learned and what they could explore next
- References to source artifacts (Figure/Table/Equation/Appendix) are allowed ONLY when narration immediately explains what viewers are seeing.
- Never use deictic-only phrasing like "as shown in Figure X" without describing the content directly.
- Avoid document-dependent wording like "if you look at ...", "in the paper", or "from the paper".
- The narration must sound complete and understandable on its own, even without the document.

═══════════════════════════════════════════════════════════════════════════════

TOPIC: {title}
DESCRIPTION: {description}
SUBJECT AREA: {subject_area}
OUTPUT LANGUAGE: {language_name}

═══════════════════════════════════════════════════════════════════════════════

{pdf_note}
SOURCE MATERIAL (extract the key concepts from this):
{content}

═══════════════════════════════════════════════════════════════════════════════

Generate a COMPLETE video script with 3-5 sections. For each section, include:
- A clear title
- Engaging narration (spoken text for the video)
- TTS-ready narration (spell out math symbols, format for text-to-speech)
- Supporting data list (CRITICAL — be exhaustive: include full table data, matrices,
  formulas with parameters, datasets, charts/axes values, constants, thresholds,
  and any quantitative details useful for visuals)
- If narration cites Figure/Table/Equation/Appendix, include a `referenced_content`
  item with the cited label and `recreate_in_video: true`.

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
                            "supporting_data": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "type": {"type": "string"},
                                        "label": {"type": "string"},
                                        "value": {},
                                        "notes": {"type": "string"}
                                    },
                                    "required": ["type", "value"]
                                }
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

            if not section.get("supporting_data"):
                section["supporting_data"] = []

            section = self._ensure_reference_content(section)
            sections[i] = filter_section(section)
        
        script["sections"] = sections
        return script

    @classmethod
    def _normalize_reference_kind(cls, raw_kind: str) -> str:
        token = (raw_kind or "").strip().lower().rstrip(".")
        if token.startswith("fig"):
            return "Figure"
        if token.startswith("eq"):
            return "Equation"
        if token == "table":
            return "Table"
        if token == "appendix":
            return "Appendix"
        return token.title()

    @classmethod
    def _reference_key_from_text(cls, text: Any) -> Optional[str]:
        if text is None:
            return None
        raw = str(text).strip()
        if not raw:
            return None

        normalized_key = raw.lower()
        if ":" in normalized_key:
            prefix, suffix = normalized_key.split(":", 1)
            if prefix in {"figure", "table", "equation", "appendix"} and suffix:
                return f"{prefix}:{suffix}"

        match = cls._REFERENCE_PATTERN.search(raw)
        if not match:
            return None

        kind = cls._normalize_reference_kind(match.group("kind")).lower()
        ref_id = match.group("id").strip().lower()
        return f"{kind}:{ref_id}"

    @classmethod
    def _extract_reference_mentions(cls, text: str) -> List[str]:
        mentions: List[str] = []
        seen: set[str] = set()
        for match in cls._REFERENCE_PATTERN.finditer(text or ""):
            kind = cls._normalize_reference_kind(match.group("kind"))
            ref_id = match.group("id").strip()
            label = f"{kind} {ref_id}"
            key = cls._reference_key_from_text(label)
            if key and key not in seen:
                mentions.append(label)
                seen.add(key)
        return mentions

    @classmethod
    def _normalize_reference_label(cls, text: str) -> str:
        match = cls._REFERENCE_PATTERN.search(text or "")
        if not match:
            return (text or "").strip()
        return f"{cls._normalize_reference_kind(match.group('kind'))} {match.group('id').strip()}"

    @classmethod
    def _rewrite_deictic_reference_language(cls, text: str) -> tuple[str, int]:
        updated = str(text or "")
        rewrites = 0

        for pattern in cls._DEICTIC_REFERENCE_PATTERNS:
            def replace_ref(match: re.Match[str]) -> str:
                nonlocal rewrites
                rewrites += 1
                normalized = cls._normalize_reference_label(match.group("ref"))
                return f"{normalized} shows "

            updated = pattern.sub(replace_ref, updated)

        for pattern, replacement in (
            (re.compile(r"\bin the paper\b", re.IGNORECASE), "in this explanation"),
            (re.compile(r"\bfrom the paper\b", re.IGNORECASE), "from the source material"),
        ):
            updated, count = pattern.subn(replacement, updated)
            rewrites += count

        updated = re.sub(r"\s+", " ", updated).strip()
        return updated, rewrites

    @classmethod
    def _ensure_reference_content(cls, section: Dict[str, Any]) -> Dict[str, Any]:
        narration, narration_rewrites = cls._rewrite_deictic_reference_language(section.get("narration", ""))
        tts_narration, tts_rewrites = cls._rewrite_deictic_reference_language(section.get("tts_narration", ""))
        section["narration"] = narration
        section["tts_narration"] = tts_narration
        combined_text = f"{narration}\n{tts_narration}"
        mentions = cls._extract_reference_mentions(combined_text)
        if not mentions:
            return section

        supporting_data = section.get("supporting_data")
        if not isinstance(supporting_data, list):
            supporting_data = []

        existing_keys: set[str] = set()
        for item in supporting_data:
            if not isinstance(item, dict):
                continue
            for candidate in (item.get("label"), item.get("type")):
                key = cls._reference_key_from_text(candidate)
                if key:
                    existing_keys.add(key)
            value = item.get("value")
            if isinstance(value, dict):
                for field in ("reference", "binding_key"):
                    key = cls._reference_key_from_text(value.get(field))
                    if key:
                        existing_keys.add(key)

        added = 0
        for mention in mentions:
            key = cls._reference_key_from_text(mention)
            if not key or key in existing_keys:
                continue
            supporting_data.append(
                {
                    "type": "referenced_content",
                    "label": mention,
                    "value": {
                        "reference": mention,
                        "binding_key": key,
                        "recreate_in_video": True,
                    },
                    "notes": "Referenced in narration; must be visualized explicitly.",
                }
            )
            existing_keys.add(key)
            added += 1

        section["supporting_data"] = supporting_data
        print(
            f"[OverviewGen] reference_mentions={len(mentions)} "
            f"deictic_rewrites={narration_rewrites + tts_rewrites} "
            f"synthetic_reference_items_added={added} "
            f"supporting_data_count={len(supporting_data)}"
        )
        return section

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
