"""
Section generation (Phase 2 for Comprehensive mode)

Handles generating sections sequentially with context from previous sections.
For overview mode, see overview_generator.py which uses single-prompt generation.

Also handles narration segmentation and script validation (shared by all modes).
"""

import asyncio
import json
from typing import Dict, Any, List

from app.services.parsing import parse_json_array_response
from .base import BaseScriptGenerator


class SectionGenerator:
    """Generates script sections and post-processes narration."""

    def __init__(self, base: BaseScriptGenerator):
        self.base = base

    async def generate_sections(
        self,
        outline: Dict[str, Any],
        content: str,
        video_mode: str,
        language_name: str,
        language_instruction: str,
    ) -> List[Dict[str, Any]]:
        """Generate sections from an outline (comprehensive mode only).
        
        Note: Overview mode now uses OverviewGenerator for single-prompt generation.
        This method is only called for comprehensive mode.
        """
        sections_outline = outline.get("sections_outline", [])
        gaps_to_fill = outline.get("document_analysis", {}).get("gaps_to_fill", [])

        return await self._generate_sections_sequentially(
            sections_outline=sections_outline,
            full_outline=outline,
            content=content,
            language_name=language_name,
            language_instruction=language_instruction,
            gaps_to_fill=gaps_to_fill,
        )

    async def _generate_sections_sequentially(
        self,
        sections_outline: List[Dict[str, Any]],
        full_outline: Dict[str, Any],
        content: str,
        language_name: str,
        language_instruction: str,
        gaps_to_fill: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Generate sections one by one using individual generate_content calls.
        Each call includes context from previous sections to maintain coherence.
        """
        generated_sections: List[Dict[str, Any]] = []
        total_sections = len(sections_outline)
        
        print(f"[SectionGen] Starting sequential generation for {total_sections} sections...")

        # Prepare full outline summary
        outline_text = "\n".join(
            f"{i+1}. {sec.get('title', 'Untitled')}" 
            for i, sec in enumerate(sections_outline)
        )

        # For comprehensive mode, use more content initially
        initial_content_limit = min(25000, max(15000, len(content) // 2))
        initial_content_excerpt = content[:initial_content_limit]

        for section_idx, section_outline in enumerate(sections_outline):
            # Determine section position and context
            if section_idx == 0:
                position_note = "FIRST SECTION: Start with engaging hook, may greet viewer."
                previous_context = ""
            elif section_idx == total_sections - 1:
                position_note = "FINAL SECTION: Summarize key insights, provide memorable conclusion."
                previous_context = self._build_compressed_previous_context(generated_sections)
            else:
                position_note = f"MIDDLE SECTION {section_idx + 1}/{total_sections}: Continue naturally, no greetings, reference earlier content."
                previous_context = self._build_compressed_previous_context(generated_sections)

            # Get relevant content excerpt for this section
            supplemental_content = ""
            if len(content) > initial_content_limit:
                section_excerpt = self._get_relevant_content_for_section(
                    content=content,
                    section_outline=section_outline,
                    section_idx=section_idx,
                    total_sections=total_sections,
                )
                if section_excerpt and section_excerpt[:500] not in initial_content_excerpt[:5000]:
                    supplemental_content = f"\n\nRELEVANT SOURCE MATERIAL FOR THIS SECTION:\n{section_excerpt[:5000]}"

            # Build prompt for this section
            prompt = self._build_sequential_prompt(
                section_idx=section_idx,
                section_outline=section_outline,
                outline_text=outline_text,
                initial_content_excerpt=initial_content_excerpt if section_idx == 0 else "",
                previous_context=previous_context,
                position_note=position_note,
                supplemental_content=supplemental_content,
                language_instruction=language_instruction,
            )

            # Generate this section with retries
            max_retries = 3
            success = False
            
            for attempt in range(max_retries):
                try:
                    print(f"[SectionGen] Generating section {section_idx + 1}/{total_sections} (attempt {attempt + 1}/{max_retries})...")
                    
                    # Define response schema for single section
                    response_schema = {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "title": {"type": "string"},
                            "narration": {"type": "string"},
                            "tts_narration": {"type": "string"}
                        },
                        "required": ["id", "title", "narration", "tts_narration"]
                    }
                    
                    # Try with thinking_config first
                    try:
                        from app.services.prompting_engine import PromptConfig
                        
                        # Try with thinking config first
                        config = PromptConfig(
                            temperature=0.7,
                            max_output_tokens=8192,
                            timeout=120,
                            response_format="json",
                            enable_thinking=True
                        )
                        response_text = await self.base.generate_with_engine(
                            prompt=prompt,
                            config=config,
                            response_schema=response_schema
                        )
                    except Exception as e:
                        error_msg = str(e)
                        if "thinking_level is not supported" in error_msg or "thinking_config" in error_msg.lower():
                            print(f"[SectionGen] Model doesn't support thinking_config, retrying without it...")
                            config = PromptConfig(
                                temperature=0.7,
                                max_output_tokens=8192,
                                timeout=120,
                                response_format="json",
                                enable_thinking=False
                            )
                            response_text = await self.base.generate_with_engine(
                                prompt=prompt,
                                config=config,
                                response_schema=response_schema
                            )
                        else:
                            raise
                    
                    if response_text:
                        section = self.base.parse_json(response_text)
                        if not section or (section.get("title") == "Mathematical Exploration" and "narration" not in section):
                            print(f"[SectionGen] WARNING: Invalid section data received (attempt {attempt + 1})")
                            raise ValueError("JSON parse failed")

                        section["id"] = section.get("id", section_outline.get("id", f"section_{section_idx}"))
                        section["title"] = section.get("title", section_outline.get("title", f"Part {section_idx + 1}"))
                        
                        # Ensure tts_narration exists
                        if not section.get("tts_narration"):
                            section["tts_narration"] = section.get("narration", "")
                        
                        generated_sections.append(section)
                        print(f"[SectionGen] OK Section {section_idx + 1} generated successfully")
                        success = True
                        break
                        
                    print(f"[SectionGen] WARNING: Empty response (attempt {attempt + 1})")
                    raise ValueError("Empty response")
                    
                except Exception as e:
                    print(f"[SectionGen] ERROR on attempt {attempt + 1}: {type(e).__name__}: {str(e)}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2)

            if not success:
                print(f"[SectionGen] ERROR: Section {section_idx + 1} failed after {max_retries} attempts")
                generated_sections.append(
                    {
                        "id": section_outline.get("id", f"section_{section_idx}"),
                        "title": section_outline.get("title", f"Part {section_idx + 1}"),
                        "narration": f"Let's explore {section_outline.get('title', 'this topic')}. (Generation failed)",
                        "tts_narration": f"Let's explore {section_outline.get('title', 'this topic')}. (Generation failed)",
                        "error": "Failed after max retries",
                    }
                )

        return generated_sections

    def _build_sequential_prompt(
        self,
        section_idx: int,
        section_outline: Dict[str, Any],
        outline_text: str,
        initial_content_excerpt: str,
        previous_context: str,
        position_note: str,
        supplemental_content: str,
        language_instruction: str,
    ) -> str:
        """Build a comprehensive prompt for sequential section generation."""
        
        if section_idx == 0:
            # First section: Include full context
            return f"""You are an expert university professor creating a COMPREHENSIVE lecture video script.
{language_instruction}

Your goal is to generate the narration for ONE section at a time. This is section {section_idx + 1}.

CONTEXT & INSTRUCTIONS:
- Explain the WHY, not just the WHAT
- For definitions: motivation → intuition → formal statement → example
- For theorems: importance → statement → proof strategy → steps → reinforcement  
- Be thorough - no length limits for comprehensive mode
- Make content engaging and educational

LECTURE OUTLINE:
{outline_text}

SOURCE MATERIAL:
{initial_content_excerpt}

═══════════════════════════════════════════════════════════════════════════════
REQUEST: Generate narration for SECTION {section_idx + 1}
═══════════════════════════════════════════════════════════════════════════════
SECTION: {section_outline.get('title', 'Untitled')}
TYPE: {section_outline.get('section_type', 'content')}
CONTENT TO COVER: {section_outline.get('content_to_cover', '')}
KEY POINTS: {json.dumps(section_outline.get('key_points', []))}

{position_note}

OUTPUT: Valid JSON only, no markdown. Generate complete narration:
{{"id": "{section_outline.get('id', f'section_{section_idx}')}",
"title": "{section_outline.get('title', f'Part {section_idx + 1}')}",
"narration": "Complete spoken narration for this section...",
"tts_narration": "TTS-ready narration: spell out math symbols (e.g., 'theta' not 'θ', 'x squared' not 'x²') AND write letter names as phonetic transcriptions for correct TTS pronunciation in the target language (e.g., in French: 'igrec' instead of 'y', 'double-ve' instead of 'w')..."}}"""
        else:
            # Subsequent sections: Include previous context
            return f"""Continue generating the lecture video script.
{language_instruction}

LECTURE OUTLINE:
{outline_text}

PREVIOUS SECTIONS CONTEXT:
{previous_context}

═══════════════════════════════════════════════════════════════════════════════
REQUEST: Generate narration for SECTION {section_idx + 1}
═══════════════════════════════════════════════════════════════════════════════
SECTION: {section_outline.get('title', 'Untitled')}
TYPE: {section_outline.get('section_type', 'content')}
CONTENT TO COVER: {section_outline.get('content_to_cover', '')}
KEY POINTS: {json.dumps(section_outline.get('key_points', []))}

{position_note}{supplemental_content}

OUTPUT: Valid JSON only.
{{"id": "{section_outline.get('id', f'section_{section_idx}')}",
"title": "{section_outline.get('title', f'Part {section_idx + 1}')}",
"narration": "Complete spoken narration...",
"tts_narration": "TTS-ready: math symbols spelled out, letter names as phonetic transcriptions for correct pronunciation..."}}"""

    def _build_compressed_previous_context(self, previous_sections: List[Dict[str, Any]]) -> str:
        if not previous_sections:
            return "(First section)"

        context_parts = []
        titles = [s.get("title", "Untitled") for s in previous_sections]
        context_parts.append(f"Progress: {' -> '.join(titles)}")

        last = previous_sections[-1]
        narration = last.get("narration", "")
        narration_excerpt = narration[-200:] if len(narration) > 200 else narration
        context_parts.append(f"Previous ended: ...{narration_excerpt}")

        if len(previous_sections) >= 2:
            second_last = previous_sections[-2]
            context_parts.append(f"Before that: {second_last.get('title', 'Untitled')}")

        return "\n".join(context_parts)

    def _get_relevant_content_for_section(
        self,
        content: str,
        section_outline: Dict[str, Any],
        section_idx: int,
        total_sections: int,
    ) -> str:

        MAX_CONTENT_PER_SECTION = 12000
        if len(content) <= MAX_CONTENT_PER_SECTION:
            return content

        content_to_cover = section_outline.get("content_to_cover", "")
        key_points = section_outline.get("key_points", [])
        section_title = section_outline.get("title", "")

        keywords = self._extract_keywords(content_to_cover, key_points, section_title)
        if keywords:
            relevant_chunks = self._find_relevant_chunks(content, keywords, max_chars=MAX_CONTENT_PER_SECTION)
            if relevant_chunks and len(relevant_chunks) >= 500:
                return relevant_chunks

        overlap = 0.3
        section_size = len(content) / max(1, total_sections)
        effective_size = section_size * (1 + overlap * 2)
        center = (section_idx + 0.5) * section_size
        start = max(0, int(center - effective_size / 2))
        end = min(len(content), int(center + effective_size / 2))

        start = self._find_paragraph_start(content, start)
        end = self._find_paragraph_end(content, end)

        excerpt = content[start:end]
        if len(excerpt) > MAX_CONTENT_PER_SECTION:
            excerpt = excerpt[:MAX_CONTENT_PER_SECTION]
        return excerpt

    def _extract_keywords(self, content_to_cover: str, key_points: List[str], title: str) -> List[str]:
        import re

        all_text = f"{title} {content_to_cover} {' '.join(key_points) if key_points else ''}"
        stop_words = {
            "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "must", "shall", "can", "need", "dare",
            "ought", "used", "to", "of", "in", "for", "on", "with", "at", "by",
            "from", "as", "into", "through", "during", "before", "after", "above",
            "below", "between", "under", "again", "further", "then", "once", "here",
            "there", "when", "where", "why", "how", "all", "each", "every", "both",
            "few", "more", "most", "other", "some", "such", "no", "nor", "not",
            "only", "own", "same", "so", "than", "too", "very", "just", "and", "or",
            "but", "if", "this", "that", "these", "those", "what", "which", "who",
            "section", "part", "chapter", "introduction", "conclusion", "summary",
            "discuss", "explain", "describe", "cover", "include", "present",
        }

        words = re.findall(r"\b[a-zA-Z]{3,}\b", all_text.lower())
        keywords = list({w for w in words if w not in stop_words})

        phrases = re.findall(r"\b[A-Z][a-z]+(?:\s+[A-Z]?[a-z]+){1,2}\b", all_text)
        keywords.extend([p.lower() for p in phrases])
        return keywords[:20]

    def _find_relevant_chunks(self, content: str, keywords: List[str], max_chars: int) -> str:
        import re

        paragraphs = re.split(r"\n\s*\n", content)
        scored_paragraphs = []
        for i, para in enumerate(paragraphs):
            if len(para.strip()) < 50:
                continue
            para_lower = para.lower()
            score = sum(1 for kw in keywords if kw in para_lower)
            if score > 0:
                scored_paragraphs.append((score, i, para))

        scored_paragraphs.sort(key=lambda x: (-x[0], x[1]))

        selected = []
        total_chars = 0
        for score, idx, para in scored_paragraphs:
            if total_chars + len(para) > max_chars:
                break
            selected.append((idx, para))
            total_chars += len(para)

        selected.sort(key=lambda x: x[0])
        return "\n\n".join(para for _, para in selected)

    def _find_paragraph_start(self, content: str, pos: int) -> int:
        search_start = max(0, pos - 500)
        chunk = content[search_start:pos]
        last_break = chunk.rfind("\n\n")
        if last_break != -1:
            return search_start + last_break + 2
        return search_start

    def _find_paragraph_end(self, content: str, pos: int) -> int:
        search_end = min(len(content), pos + 500)
        chunk = content[pos:search_end]
        next_break = chunk.find("\n\n")
        if next_break != -1:
            return pos + next_break
        return search_end

    def segment_narrations(self, script: Dict[str, Any]) -> Dict[str, Any]:
        for section in script.get("sections", []):
            narration = section.get("tts_narration") or section.get("narration", "")
            if not narration:
                narration = "This section explores the topic."
                section["narration"] = narration
                section["tts_narration"] = narration

            segments = self._split_narration_into_segments(narration)
            if not segments:
                segments = [
                    {
                        "text": narration,
                        "estimated_duration": max(3.0, len(narration) / self.base.chars_per_second),
                        "segment_index": 0,
                    }
                ]

            section["narration_segments"] = segments
            total_estimated = sum(seg["estimated_duration"] for seg in segments)
            section["duration_seconds"] = max(section.get("duration_seconds", 30), total_estimated)

        script["total_duration_seconds"] = sum(s.get("duration_seconds", 0) for s in script.get("sections", []))
        return script

    def _split_narration_into_segments(self, narration: str) -> List[Dict[str, Any]]:
        import re

        if not narration or len(narration) < 50:
            estimated = len(narration) / self.base.chars_per_second
            return [
                {
                    "text": narration,
                    "estimated_duration": max(3.0, estimated),
                    "segment_index": 0,
                }
            ]

        target_chars = self.base.target_segment_duration * self.base.chars_per_second
        max_chars = target_chars * 1.5

        pause_parts = re.split(r"\[PAUSE\]", narration)

        segments = []
        current_text: List[str] = []
        current_chars = 0

        for part_idx, part in enumerate(pause_parts):
            sentences = re.split(r"(?<=[.!?])\s+", part.strip())
            sentences = [s.strip() for s in sentences if s.strip()]

            for sentence in sentences:
                sentence_len = len(sentence)
                if current_chars + sentence_len > max_chars and current_text:
                    segment_text = " ".join(current_text)
                    estimated = len(segment_text) / self.base.chars_per_second
                    segments.append(
                        {
                            "text": segment_text,
                            "estimated_duration": estimated,
                            "segment_index": len(segments),
                        }
                    )
                    current_text = [sentence]
                    current_chars = sentence_len
                elif current_chars + sentence_len > target_chars and current_text:
                    segment_text = " ".join(current_text)
                    estimated = len(segment_text) / self.base.chars_per_second
                    segments.append(
                        {
                            "text": segment_text,
                            "estimated_duration": estimated,
                            "segment_index": len(segments),
                        }
                    )
                    current_text = [sentence]
                    current_chars = sentence_len
                else:
                    current_text.append(sentence)
                    current_chars += sentence_len + 1

            if part_idx < len(pause_parts) - 1 and current_text:
                segment_text = " ".join(current_text)
                estimated = len(segment_text) / self.base.chars_per_second
                segments.append(
                    {
                        "text": segment_text,
                        "estimated_duration": estimated,
                        "segment_index": len(segments),
                    }
                )
                current_text = []
                current_chars = 0

        if current_text:
            segment_text = " ".join(current_text)
            estimated = len(segment_text) / self.base.chars_per_second
            segments.append(
                {
                    "text": segment_text,
                    "estimated_duration": estimated,
                    "segment_index": len(segments),
                }
            )

        merged_segments: List[Dict[str, Any]] = []
        for seg in segments:
            if seg["estimated_duration"] < 3.0 and merged_segments:
                prev = merged_segments[-1]
                prev["text"] += " " + seg["text"]
                prev["estimated_duration"] = len(prev["text"]) / self.base.chars_per_second
            else:
                merged_segments.append(seg)

        for i, seg in enumerate(merged_segments):
            seg["segment_index"] = i

        return merged_segments

    def validate_script(self, script: Dict[str, Any], topic: Dict[str, Any]) -> Dict[str, Any]:
        if "title" not in script:
            script["title"] = topic.get("title", "Educational Content")

        if "sections" not in script or not script["sections"]:
            script["sections"] = self._default_script()["sections"]

        for i, section in enumerate(script["sections"]):
            if "id" not in section:
                section["id"] = f"section_{i}"
            if "title" not in section:
                section["title"] = f"Part {i + 1}"
            if "duration_seconds" not in section:
                section["duration_seconds"] = 60
            if "narration" not in section:
                section["narration"] = "Let's explore this concept..."
            if "tts_narration" not in section:
                section["tts_narration"] = section["narration"]

        script["total_duration_seconds"] = sum(s.get("duration_seconds", 0) for s in script.get("sections", []))
        return script

    def _default_script(self) -> Dict[str, Any]:
        return {
            "title": "Mathematical Exploration",
            "total_duration_seconds": 300,
            "sections": [
                {
                    "id": "intro",
                    "title": "Introduction",
                    "duration_seconds": 30,
                    "narration": "Welcome! Today we're going to explore a fascinating mathematical concept.",
                    "tts_narration": "Welcome! Today we're going to explore a fascinating mathematical concept.",
                },
                {
                    "id": "main",
                    "title": "Main Concept",
                    "duration_seconds": 180,
                    "narration": "Let's dive into the core idea and build our intuition step by step.",
                    "tts_narration": "Let's dive into the core idea and build our intuition step by step.",
                },
                {
                    "id": "conclusion",
                    "title": "Conclusion",
                    "duration_seconds": 30,
                    "narration": "And that's the beautiful idea at the heart of this topic. Thanks for watching!",
                    "tts_narration": "And that's the beautiful idea at the heart of this topic. Thanks for watching!",
                },
            ],
        }

    def _fallback_sections(self, sections_outline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {
                "id": sec.get("id", f"section_{i}"),
                "title": sec.get("title", f"Part {i + 1}"),
                "narration": f"Let's explore {sec.get('title', 'this topic')}.",
                "tts_narration": f"Let's explore {sec.get('title', 'this topic')}.",
            }
            for i, sec in enumerate(sections_outline)
        ]
