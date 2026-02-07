"""
Section generation (Phase 2 for Comprehensive mode)

Handles generating sections sequentially with context from previous sections.
For overview mode, see overview_generator.py which uses single-prompt generation.

Also handles narration segmentation and script validation (shared by all modes).
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Dict, Any, List, Optional

from .base import BaseScriptGenerator
from .schema_filter import filter_section


class SectionGenerator:
    """Generates script sections and post-processes narration."""

    def __init__(self, base: BaseScriptGenerator, use_pdf_page_slices: Optional[bool] = None):
        self.base = base
        self.use_pdf_page_slices = (
            use_pdf_page_slices
            if use_pdf_page_slices is not None
            else os.getenv("ENABLE_SECTION_PDF_SLICES", "").strip().lower() in {"1", "true", "yes", "on"}
        )

    async def generate_sections(
        self,
        outline: Dict[str, Any],
        content: str,
        language_name: str,
        language_instruction: str,
        topic: Dict[str, Any] = None,
        pdf_path: Optional[str] = None,
        total_pages: Optional[int] = None,
        artifacts_dir: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Generate sections from an outline (comprehensive mode only).
        
        Note: Overview mode now uses OverviewGenerator for single-prompt generation.
        This method is only called for comprehensive mode.
        """
        sections_outline = outline.get("sections_outline", [])
        gaps_to_fill = outline.get("document_analysis", {}).get("gaps_to_fill", [])

        return await self._generate_sections_sequentially(
            sections_outline=sections_outline,
            content=content,
            language_name=language_name,
            language_instruction=language_instruction,
            gaps_to_fill=gaps_to_fill,
            pdf_path=pdf_path,
            total_pages=total_pages,
            artifacts_dir=artifacts_dir,
        )

    async def _generate_sections_sequentially(
        self,
        sections_outline: List[Dict[str, Any]],
        content: str,
        language_name: str,
        language_instruction: str,
        gaps_to_fill: List[str],
        pdf_path: Optional[str],
        total_pages: Optional[int],
        artifacts_dir: Optional[str],
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

        # For comprehensive mode, use more content initially (non-PDF only)
        initial_content_limit = min(25000, max(15000, len(content) // 2)) if content else 0
        initial_content_excerpt = content[:initial_content_limit] if content else ""

        pdf_slices_dir = None
        full_pdf_part = None
        if pdf_path and not self.use_pdf_page_slices:
            full_pdf_part = self.base.build_pdf_part(pdf_path)
        if self.use_pdf_page_slices and pdf_path and artifacts_dir:
            pdf_slices_dir = Path(artifacts_dir) / "pdf_slices"
            pdf_slices_dir.mkdir(parents=True, exist_ok=True)

        for section_idx, section_outline in enumerate(sections_outline):
            # Determine section position and context
            if section_idx == 0:
                position_note = (
                    "FIRST SECTION: Hook-first (3Blue1Brown-style). "
                    "Open with a visual/puzzle or surprising question. "
                    "No greetings. No agenda listing."
                )
                previous_context = ""
            elif section_idx == total_sections - 1:
                position_note = "FINAL SECTION: Summarize key insights, provide memorable conclusion."
                previous_context = self._build_compressed_previous_context(generated_sections)
            else:
                position_note = f"MIDDLE SECTION {section_idx + 1}/{total_sections}: Continue naturally, no greetings, reference earlier content."
                previous_context = self._build_compressed_previous_context(generated_sections)
            
            target_seconds = section_outline.get("estimated_duration_seconds")
            if not target_seconds:
                if section_idx == 0:
                    target_seconds = 210
                elif section_idx == total_sections - 1:
                    target_seconds = 150
                else:
                    target_seconds = 180

            # Get relevant content excerpt for this section (non-PDF only)
            supplemental_content = ""
            if content and len(content) > initial_content_limit:
                section_excerpt = self._get_relevant_content_for_section(
                    content=content,
                    section_outline=section_outline,
                    section_idx=section_idx,
                    total_sections=total_sections,
                )
                if section_excerpt and section_excerpt[:500] not in initial_content_excerpt[:5000]:
                    supplemental_content = f"\n\nRELEVANT SOURCE MATERIAL FOR THIS SECTION:\n{section_excerpt[:5000]}"

            # Prepare PDF slice if applicable
            pdf_part = None
            source_pages = None
            source_pdf_path = None
            if pdf_path:
                page_start = self._coerce_page(section_outline.get("page_start"))
                page_end = self._coerce_page(section_outline.get("page_end"))
                if page_start and page_end:
                    source_pages = {"start": page_start, "end": page_end}
                else:
                    source_pages = {"start": 1, "end": total_pages} if total_pages else None

                slice_path = None
                if self.use_pdf_page_slices and pdf_slices_dir and page_start and page_end:
                    slice_filename = f"section_{section_idx + 1}_{page_start}-{page_end}.pdf"
                    slice_path = self.base.slice_pdf_pages(
                        source_path=pdf_path,
                        start_page=page_start,
                        end_page=page_end,
                        output_path=str(pdf_slices_dir / slice_filename)
                    )
                if slice_path:
                    source_pdf_path = slice_path
                    pdf_part = self.base.build_pdf_part(slice_path)
                else:
                    source_pdf_path = pdf_path
                    pdf_part = full_pdf_part if full_pdf_part is not None else self.base.build_pdf_part(pdf_path)

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
                target_seconds=target_seconds,
                pdf_attached=bool(pdf_part),
                page_range=source_pages,
                total_pages=total_pages,
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
                            "tts_narration": {"type": "string"},
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
                    }
                    
                    # Try with thinking_config first
                    try:
                        from app.services.infrastructure.llm import PromptConfig
                        
                        # Try with thinking config first
                        config = PromptConfig(
                            temperature=0.7,
                            max_output_tokens=32768,
                            timeout=150,
                            response_format="json",
                            enable_thinking=True
                        )
                        contents = self.base.build_prompt_contents(prompt, pdf_part)
                        response_text = await self.base.generate_with_engine(
                            prompt=prompt,
                            config=config,
                            response_schema=response_schema,
                            contents=contents,
                        )
                    except Exception as e:
                        error_msg = str(e)
                        if "thinking_level is not supported" in error_msg or "thinking_config" in error_msg.lower():
                            print("[SectionGen] Model doesn't support thinking_config, retrying without it...")
                            config = PromptConfig(
                                temperature=0.7,
                                max_output_tokens=32768,
                                timeout=120,
                                response_format="json",
                                enable_thinking=False
                            )
                            contents = self.base.build_prompt_contents(prompt, pdf_part)
                            response_text = await self.base.generate_with_engine(
                                prompt=prompt,
                                config=config,
                                response_schema=response_schema,
                                contents=contents,
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

                        # Ensure supporting_data exists
                        if not section.get("supporting_data"):
                            section["supporting_data"] = []

                        # Store source PDF metadata
                        if source_pages:
                            section["source_pages"] = source_pages
                        if source_pdf_path:
                            section["source_pdf_path"] = source_pdf_path

                        section = filter_section(section)
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
                        "supporting_data": [],
                        **({"source_pages": source_pages} if source_pages else {}),
                        **({"source_pdf_path": source_pdf_path} if source_pdf_path else {}),
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
        target_seconds: int,
        pdf_attached: bool,
        page_range: Optional[Dict[str, int]],
        total_pages: Optional[int],
    ) -> str:
        """Build a comprehensive prompt for sequential section generation."""
        target_words = max(120, int(target_seconds * 2.2))
        min_words = int(target_words * 0.85)
        max_words = int(target_words * 1.15)

        page_note = ""
        if pdf_attached:
            total_note = f"{total_pages}" if total_pages is not None else "unknown"
            if page_range:
                page_note = (
                    f"\nPDF NOTE:\n- The PDF for this section is ATTACHED.\n"
                    f"- Use pages {page_range.get('start')}–{page_range.get('end')} (1-based, inclusive) "
                    f"out of {total_note}.\n"
                )
            else:
                page_note = (
                    f"\nPDF NOTE:\n- The PDF for this section is ATTACHED.\n"
                    f"- Page range is unspecified; use relevant pages. Total pages: {total_note}.\n"
                )

        if section_idx == 0:
            # First section: Include full context
            return f"""You are an expert university professor creating a COMPREHENSIVE lecture video script.
{language_instruction}

Your goal is to generate the narration for ONE section at a time. This is section {section_idx + 1}.

CONTEXT & INSTRUCTIONS:
- Explain the WHY, not just the WHAT
- For definitions: motivation → intuition → formal statement → example
- For theorems: importance → statement → proof strategy → steps → reinforcement  
- Be thorough and lecture-level in depth (like a university lecture, not a short explainer)
- Make content engaging and educational
- Treat CONTENT TO COVER and KEY POINTS as a non-skippable checklist
- For worked examples: narrate EVERY step and include ALL intermediate values
- If you reference a table or matrix, summarize key rows/columns in narration (do not read every value)
- Avoid placeholder phrasing like "we fill the table" without specifying what the table contains
- The outline is STRUCTURAL. Do not repeat it verbatim in narration.
- Put full data and calculations ONLY in supporting_data (no truncation).
- Length target: ~{target_seconds} seconds (~{min_words}–{max_words} words). Stay close.

LECTURE OUTLINE:
{outline_text}

{page_note}
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

SUPPORTING DATA (CRITICAL — BE EXHAUSTIVE):
- Include a "supporting_data" array for visuals.
- Capture ALL useful data from this section, even if not narrated:
  full tables (all rows/columns), matrices, formulas with parameters,
  datasets, distributions, charts/axes data, constants, thresholds,
  algorithm inputs/outputs, categorical breakdowns, and any percentages.
- If a table appears, include the COMPLETE table data (no summarizing).
- Do NOT narrate every table value; summarize key takeaways instead.
- Prefer structured values (arrays/objects) so visuals can be generated accurately.
- Each item must include: type, label, value, notes (notes can be empty).

OUTPUT: Valid JSON only, no markdown. Generate complete narration:
{{"id": "{section_outline.get('id', f'section_{section_idx}')}",
"title": "{section_outline.get('title', f'Part {section_idx + 1}')}",
"narration": "Complete spoken narration for this section...",
"tts_narration": "TTS-ready narration: spell out math symbols (e.g., 'theta' not 'θ', 'x squared' not 'x²') AND write letter names as phonetic transcriptions for correct TTS pronunciation in the target language (e.g., in French: 'igrec' instead of 'y', 'double-ve' instead of 'w')...",
"supporting_data": [{{"type": "statistic", "label": "Example", "value": "42%", "notes": "Use in chart"}}]}}"""
        else:
            # Subsequent sections: Include previous context
            return f"""Continue generating the lecture video script.
{language_instruction}

LECTURE OUTLINE:
{outline_text}

PREVIOUS SECTIONS CONTEXT:
{previous_context}

SECTION REQUIREMENTS:
- Treat CONTENT TO COVER and KEY POINTS as a non-skippable checklist.
- For worked examples: narrate EVERY step and include ALL intermediate values.
- If you reference a table or matrix, summarize key rows/columns in narration (do not read every value).
- Avoid placeholder phrasing like "we fill the table" without specifying what the table contains.
- The outline is STRUCTURAL. Do not repeat it verbatim in narration.
- Put full data and calculations ONLY in supporting_data (no truncation).

DEPTH & LENGTH TARGETS:
- Maintain university-lecture depth (full motivation, intuition, formalism, and careful explanation)
- Aim for ~{target_seconds} seconds of narration (~{min_words}–{max_words} words)

{page_note}
═══════════════════════════════════════════════════════════════════════════════
REQUEST: Generate narration for SECTION {section_idx + 1}
═══════════════════════════════════════════════════════════════════════════════
SECTION: {section_outline.get('title', 'Untitled')}
TYPE: {section_outline.get('section_type', 'content')}
CONTENT TO COVER: {section_outline.get('content_to_cover', '')}
KEY POINTS: {json.dumps(section_outline.get('key_points', []))}

{position_note}{supplemental_content}

SUPPORTING DATA (CRITICAL — BE EXHAUSTIVE):
- Include a "supporting_data" array for visuals.
- Capture ALL useful data from this section, even if not narrated:
  full tables (all rows/columns), matrices, formulas with parameters,
  datasets, distributions, charts/axes data, constants, thresholds,
  algorithm inputs/outputs, categorical breakdowns, and any percentages.
- If a table appears, include the COMPLETE table data (no summarizing).
- Do NOT narrate every table value; summarize key takeaways instead.
- Prefer structured values (arrays/objects) so visuals can be generated accurately.
- Each item must include: type, label, value, notes (notes can be empty).

OUTPUT: Valid JSON only.
{{"id": "{section_outline.get('id', f'section_{section_idx}')}",
"title": "{section_outline.get('title', f'Part {section_idx + 1}')}",
"narration": "Complete spoken narration...",
"tts_narration": "TTS-ready: math symbols spelled out, letter names as phonetic transcriptions for correct pronunciation...",
"supporting_data": [{{"type": "statistic", "label": "Example", "value": "42%", "notes": "Use in chart"}}]}}"""

    def _coerce_page(self, value: Any) -> Optional[int]:
        try:
            if value is None:
                return None
            page = int(value)
            return page if page > 0 else None
        except Exception:
            return None

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

        MAX_CONTENT_PER_SECTION = 15000
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
