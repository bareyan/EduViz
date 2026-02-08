"""
Overview script generator

Generates an informative overview video script in a single prompt.
Unlike the comprehensive mode which uses a two-phase approach (outline + sections),
overview mode generates everything at once for efficiency.
"""

import asyncio
import os
import re
from dataclasses import dataclass
from typing import Dict, Any, List, Optional

from app.core import get_logger
from app.services.infrastructure.parsing import parse_json_response
from .base import BaseScriptGenerator
from .schema_filter import filter_section

logger = get_logger(__name__, component="overview_script_generator")


@dataclass(frozen=True)
class OverviewConstraints:
    min_duration_seconds: int
    max_duration_seconds: int
    min_sections: int
    max_sections: int
    section_min_words: int
    section_max_words: int
    constraint_retry_count: int


@dataclass(frozen=True)
class OverviewPlanningProfile:
    effective_min_sections: int
    preferred_sections: int
    preferred_duration_seconds: int
    target_section_words: int
    depth_hint: str


class OverviewGenerator:
    """Generates concise overview video scripts in a single prompt."""

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
        self.constraints = self._load_constraints()

    @staticmethod
    def _read_int_env(name: str, default: int) -> int:
        raw = os.getenv(name, str(default)).strip()
        try:
            return int(raw)
        except Exception:
            return default

    @classmethod
    def _format_minutes(cls, seconds: int) -> str:
        minutes = seconds / 60.0
        if minutes.is_integer():
            return str(int(minutes))
        return f"{minutes:.1f}".rstrip("0").rstrip(".")

    def _load_constraints(self) -> OverviewConstraints:
        min_duration = max(60, self._read_int_env("OVERVIEW_MIN_DURATION_SECONDS", 180))
        max_duration = max(60, self._read_int_env("OVERVIEW_MAX_DURATION_SECONDS", 420))
        if max_duration < min_duration:
            max_duration = min_duration

        min_sections = max(1, self._read_int_env("OVERVIEW_MIN_SECTIONS", 5))
        max_sections = max(1, self._read_int_env("OVERVIEW_MAX_SECTIONS", 8))
        if max_sections < min_sections:
            max_sections = min_sections

        min_words = max(30, self._read_int_env("OVERVIEW_SECTION_MIN_WORDS", 80))
        max_words = max(30, self._read_int_env("OVERVIEW_SECTION_MAX_WORDS", 170))
        if max_words < min_words:
            max_words = min_words

        retry_count = max(0, self._read_int_env("OVERVIEW_CONSTRAINT_RETRY_COUNT", 1))

        return OverviewConstraints(
            min_duration_seconds=min_duration,
            max_duration_seconds=max_duration,
            min_sections=min_sections,
            max_sections=max_sections,
            section_min_words=min_words,
            section_max_words=max_words,
            constraint_retry_count=retry_count,
        )

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

        response_schema = self._get_response_schema()

        try:
            logger.info("Overview generation constraints", extra={
                "overview_constraints": {
                    "min_duration_seconds": self.constraints.min_duration_seconds,
                    "max_duration_seconds": self.constraints.max_duration_seconds,
                    "min_sections": self.constraints.min_sections,
                    "max_sections": self.constraints.max_sections,
                    "section_min_words": self.constraints.section_min_words,
                    "section_max_words": self.constraints.section_max_words,
                    "constraint_retry_count": self.constraints.constraint_retry_count,
                }
            })

            print("[OverviewGen] Generating complete overview script...")

            from app.services.infrastructure.llm import PromptConfig
            config = PromptConfig(
                temperature=0.7,
                max_output_tokens=int(32768 * 1.8),
                timeout=150,
                response_format="json"
            )

            pdf_part = None
            if pdf_path:
                pdf_part = self.base.build_pdf_part(pdf_path)

            planning = self._build_planning_profile(
                topic=topic,
                content=content_excerpt,
                total_pages=total_pages,
            )

            correction_note: Optional[str] = None
            max_attempts = self.constraints.constraint_retry_count + 1

            for attempt in range(max_attempts):
                prompt = self._build_overview_prompt(
                    content=content_excerpt,
                    topic=topic,
                    language_name=language_name,
                    language_instruction=language_instruction,
                    pdf_attached=bool(pdf_path),
                    total_pages=total_pages,
                    planning=planning,
                    correction_note=correction_note,
                )

                contents = None
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

                metrics = self._compute_script_metrics(script)
                violations = self._collect_constraint_violations(metrics, planning)
                self._log_script_metrics(metrics, violations, attempt)

                if not violations:
                    print(f"[OverviewGen] Successfully generated script with {len(script.get('sections', []))} sections")
                    return script

                if attempt < max_attempts - 1:
                    correction_note = self._build_constraint_correction_note(metrics, violations, planning)
                    logger.warning(
                        "Overview script constraints missed; retrying generation",
                        extra={
                            "attempt": attempt + 1,
                            "max_attempts": max_attempts,
                            "violations": violations,
                            "metrics": metrics,
                        },
                    )
                    continue

                logger.warning(
                    "Overview script constraints still missed after retries; returning best effort",
                    extra={
                        "violations": violations,
                        "metrics": metrics,
                    },
                )
                print(f"[OverviewGen] Returning best effort script with {len(script.get('sections', []))} sections")
                return script

            return self._fallback_script(topic)

        except asyncio.TimeoutError:
            print("[OverviewGen] ERROR: Request timed out after 150 seconds")
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
        planning: OverviewPlanningProfile,
        correction_note: Optional[str] = None,
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

        correction_block = ""
        if correction_note:
            correction_block = (
                "\nCONSTRAINT CORRECTION NOTE:\n"
                f"{correction_note}\n"
                "Regenerate the full script and satisfy all constraints above.\n"
            )

        min_minutes = self._format_minutes(self.constraints.min_duration_seconds)
        max_minutes = self._format_minutes(self.constraints.max_duration_seconds)

        return f"""You are an expert educator creating a SHORT, ENGAGING overview video script.
{language_instruction}

═══════════════════════════════════════════════════════════════════════════════
                         OVERVIEW VIDEO REQUIREMENTS
═══════════════════════════════════════════════════════════════════════════════

GOAL: Create a {min_minutes}-{max_minutes} MINUTE overview video that introduces the key concepts.
- This is NOT a comprehensive lecture - it's a quick, engaging introduction
- Focus on the BIG PICTURE and most important ideas
- Make viewers EXCITED to learn more about this topic
- Keep language clear, accessible, and engaging

STRUCTURE GUIDELINES:
- {self.constraints.min_sections}-{self.constraints.max_sections} sections total
- Minimum sections for this request: {planning.effective_min_sections}
- Target sections for this request: {planning.preferred_sections}
- Each section: approximately {self.constraints.section_min_words}-{self.constraints.section_max_words} words of narration
- Preferred per-section depth for this request: around {planning.target_section_words} words when naturally possible
- Prefer adding sections over making any one section oversized
- Total video target: {self.constraints.min_duration_seconds}-{self.constraints.max_duration_seconds} seconds
- Preferred total duration for this request: around {planning.preferred_duration_seconds} seconds

CONTENT GUIDELINES:
- Start with a hook: Why does this topic matter?
- Identify KEY concepts from the material
- Explain each concept briefly but clearly
- Add a bit more depth than a quick skim: give concise intuition and one concrete anchor example for major ideas
- Stay in OVERVIEW mode, not comprehensive lecture mode
- End with what viewers learned and what they could explore next
- {planning.depth_hint}
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

{correction_block}
Generate a COMPLETE video script with {self.constraints.min_sections}-{self.constraints.max_sections} sections. For each section, include:
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
                    "minItems": self.constraints.min_sections,
                    "maxItems": self.constraints.max_sections,
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
                                "description": (
                                    "Complete spoken narration for this section "
                                    f"({self.constraints.section_min_words}-{self.constraints.section_max_words} words)"
                                )
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
                    "description": (
                        f"{self.constraints.min_sections}-{self.constraints.max_sections} "
                        "sections for the video"
                    )
                }
            },
            "required": ["title", "overview", "sections"]
        }

    @staticmethod
    def _count_words(text: str) -> int:
        return len(re.findall(r"\b[\w'-]+\b", text or ""))

    def _compute_script_metrics(self, script: Dict[str, Any]) -> Dict[str, Any]:
        sections = script.get("sections", [])
        section_word_counts: List[int] = []
        section_estimated_durations: List[int] = []

        for section in sections:
            narration_text = section.get("tts_narration") or section.get("narration", "")
            section_word_counts.append(self._count_words(narration_text))
            section_estimated_durations.append(max(30, int(len(narration_text) / self.base.chars_per_second)))

        return {
            "section_count": len(sections),
            "section_word_counts": section_word_counts,
            "total_words": sum(section_word_counts),
            "estimated_duration_seconds": sum(section_estimated_durations),
        }

    def _build_planning_profile(
        self,
        topic: Dict[str, Any],
        content: str,
        total_pages: Optional[int],
    ) -> OverviewPlanningProfile:
        material_score = 0

        if total_pages and total_pages >= 25:
            material_score += 1
        if total_pages and total_pages >= 45:
            material_score += 1

        content_length = len(content or "")
        if content_length >= 15000:
            material_score += 1
        if content_length >= 35000:
            material_score += 1

        try:
            estimated_duration = int(topic.get("estimated_duration", 0))
        except Exception:
            estimated_duration = 0
        # Topic estimated duration is typically minute-like in analysis payloads.
        if estimated_duration >= 15:
            material_score += 1
        if estimated_duration >= 30:
            material_score += 1

        selected_titles = topic.get("selected_topic_titles")
        if isinstance(selected_titles, list) and len(selected_titles) > 1:
            material_score += 1

        extra_min_sections = 0
        if material_score >= 2:
            extra_min_sections = 1
        if material_score >= 4:
            extra_min_sections = 2

        effective_min_sections = min(
            self.constraints.max_sections,
            self.constraints.min_sections + extra_min_sections,
        )

        if material_score >= 4:
            preferred_sections = self.constraints.max_sections
            preferred_duration_seconds = self.constraints.max_duration_seconds
            target_section_words = self.constraints.section_max_words
            depth_hint = (
                "For this large source, spread coverage across more sections and spend a little more time "
                "on each major concept while staying concise."
            )
        elif material_score >= 2:
            preferred_sections = min(self.constraints.max_sections, effective_min_sections + 1)
            preferred_duration_seconds = int(
                self.constraints.min_duration_seconds
                + 0.85 * (self.constraints.max_duration_seconds - self.constraints.min_duration_seconds)
            )
            target_section_words = max(
                self.constraints.section_min_words,
                min(self.constraints.section_max_words, int(self.constraints.section_max_words * 0.9)),
            )
            depth_hint = (
                "For this moderately large source, use extra concept coverage and brief intuition per section "
                "instead of compressing everything into minimal structure."
            )
        else:
            preferred_sections = max(
                effective_min_sections,
                min(self.constraints.max_sections, self.constraints.min_sections + 1),
            )
            preferred_duration_seconds = int(
                (self.constraints.min_duration_seconds + self.constraints.max_duration_seconds) / 2
            )
            baseline_section_words = int(
                (self.constraints.section_min_words + self.constraints.section_max_words) / 2
            )
            # For shorter overviews, keep the structure compact but make each
            # section modestly deeper (about 20-30% longer than terse summaries).
            boosted_words = int(round(baseline_section_words * 1.25))
            target_section_words = max(
                self.constraints.section_min_words,
                min(self.constraints.section_max_words, boosted_words),
            )
            depth_hint = (
                "For shorter source material, keep section count compact but make each section around "
                "20-30% more developed than a minimal summary."
            )

        logger.info(
            "Overview planning profile",
            extra={
                "material_score": material_score,
                "total_pages": total_pages,
                "content_length": content_length,
                "estimated_duration_hint": estimated_duration,
                "effective_min_sections": effective_min_sections,
                "preferred_sections": preferred_sections,
                "preferred_duration_seconds": preferred_duration_seconds,
                "target_section_words": target_section_words,
            },
        )

        return OverviewPlanningProfile(
            effective_min_sections=effective_min_sections,
            preferred_sections=preferred_sections,
            preferred_duration_seconds=preferred_duration_seconds,
            target_section_words=target_section_words,
            depth_hint=depth_hint,
        )

    def _collect_constraint_violations(
        self,
        metrics: Dict[str, Any],
        planning: Optional[OverviewPlanningProfile] = None,
    ) -> List[str]:
        violations: List[str] = []

        section_count = metrics.get("section_count", 0)
        min_sections_required = (
            planning.effective_min_sections if planning else self.constraints.min_sections
        )
        if section_count < min_sections_required:
            violations.append("section_count_too_low")
        if section_count > self.constraints.max_sections:
            violations.append("section_count_too_high")

        word_counts = metrics.get("section_word_counts", [])
        if any(count < self.constraints.section_min_words for count in word_counts):
            violations.append("section_words_too_low")
        if any(count > self.constraints.section_max_words for count in word_counts):
            violations.append("section_words_too_high")

        estimated_duration = metrics.get("estimated_duration_seconds", 0)
        if estimated_duration < self.constraints.min_duration_seconds:
            violations.append("duration_too_low")
        if estimated_duration > self.constraints.max_duration_seconds:
            violations.append("duration_too_high")

        return violations

    def _build_constraint_correction_note(
        self,
        metrics: Dict[str, Any],
        violations: List[str],
        planning: Optional[OverviewPlanningProfile] = None,
    ) -> str:
        word_counts = metrics.get("section_word_counts", [])
        low_word = min(word_counts) if word_counts else 0
        high_word = max(word_counts) if word_counts else 0
        min_sections_required = (
            planning.effective_min_sections if planning else self.constraints.min_sections
        )
        preferred_sections = (
            planning.preferred_sections if planning else self.constraints.min_sections
        )
        preferred_duration = (
            planning.preferred_duration_seconds
            if planning
            else int((self.constraints.min_duration_seconds + self.constraints.max_duration_seconds) / 2)
        )
        preferred_words = (
            planning.target_section_words
            if planning
            else int((self.constraints.section_min_words + self.constraints.section_max_words) / 2)
        )

        details = [
            "Your previous output missed one or more hard constraints.",
            (
                f"Actual: sections={metrics.get('section_count', 0)}, "
                f"estimated_duration_seconds={metrics.get('estimated_duration_seconds', 0)}, "
                f"section_word_range={low_word}-{high_word}."
            ),
            (
                "Required: "
                f"sections={min_sections_required}-{self.constraints.max_sections}, "
                f"duration_seconds={self.constraints.min_duration_seconds}-{self.constraints.max_duration_seconds}, "
                f"section_words={self.constraints.section_min_words}-{self.constraints.section_max_words}."
            ),
            (
                "Preferred target for this request: "
                f"sections≈{preferred_sections}, duration≈{preferred_duration}s, section_words≈{preferred_words}."
            ),
            f"Violations: {', '.join(violations)}.",
            "Do not summarize too aggressively; expand coverage with additional sections when needed.",
        ]
        return "\n".join(details)

    def _log_script_metrics(self, metrics: Dict[str, Any], violations: List[str], attempt: int) -> None:
        logger.info(
            "Overview script metrics",
            extra={
                "attempt": attempt + 1,
                "metrics": {
                    "section_count": metrics.get("section_count", 0),
                    "total_words": metrics.get("total_words", 0),
                    "estimated_duration_seconds": metrics.get("estimated_duration_seconds", 0),
                    "section_word_counts": metrics.get("section_word_counts", []),
                },
                "violations": violations,
            },
        )

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
        sections = [
            {
                "id": "intro",
                "title": "Why This Topic Matters",
                "narration": "Welcome to this overview. In this section, we establish why the topic matters, where it appears in real work, and what questions we will answer in the rest of the video.",
                "tts_narration": "Welcome to this overview. In this section, we establish why the topic matters, where it appears in real work, and what questions we will answer in the rest of the video.",
                "key_points": ["Context and motivation"],
                "visual_type": "animated"
            },
            {
                "id": "core_concept_1",
                "title": "Core Concept One",
                "narration": "Now we introduce the first core concept and define the essential terms clearly. We focus on the idea itself first, then connect it to a simple example so the definition is easy to remember.",
                "tts_narration": "Now we introduce the first core concept and define the essential terms clearly. We focus on the idea itself first, then connect it to a simple example so the definition is easy to remember.",
                "key_points": ["First key concept"],
                "visual_type": "animated"
            },
            {
                "id": "core_concept_2",
                "title": "Core Concept Two",
                "narration": "Next we build on the first idea with a second concept that explains how the pieces interact. This section highlights relationships and common patterns that viewers should notice during examples.",
                "tts_narration": "Next we build on the first idea with a second concept that explains how the pieces interact. This section highlights relationships and common patterns that viewers should notice during examples.",
                "key_points": ["Second key concept"],
                "visual_type": "animated"
            },
            {
                "id": "applications",
                "title": "Practical Application",
                "narration": "With the main ideas established, we show how they are applied in practice. We walk through a representative scenario and emphasize the decisions, assumptions, and interpretation of results.",
                "tts_narration": "With the main ideas established, we show how they are applied in practice. We walk through a representative scenario and emphasize the decisions, assumptions, and interpretation of results.",
                "key_points": ["Application mindset"],
                "visual_type": "animated"
            },
            {
                "id": "conclusion",
                "title": "Summary and Next Steps",
                "narration": "In summary, we reviewed the big picture, clarified the most important concepts, and saw how they are used. To continue learning, viewers can explore deeper proofs, extensions, and advanced problem settings.",
                "tts_narration": "In summary, we reviewed the big picture, clarified the most important concepts, and saw how they are used. To continue learning, viewers can explore deeper proofs, extensions, and advanced problem settings.",
                "key_points": ["Recap and next steps"],
                "visual_type": "static"
            }
        ]

        min_required = self.constraints.min_sections
        if min_required <= len(sections):
            return sections[:min_required]

        while len(sections) < min_required:
            idx = len(sections) + 1
            sections.append(
                {
                    "id": f"extension_{idx}",
                    "title": f"Additional Insight {idx}",
                    "narration": "This additional section reinforces key ideas with another perspective, helping the viewer connect definitions, examples, and practical interpretation in a coherent way.",
                    "tts_narration": "This additional section reinforces key ideas with another perspective, helping the viewer connect definitions, examples, and practical interpretation in a coherent way.",
                    "key_points": ["Reinforcement"],
                    "visual_type": "animated",
                }
            )

        return sections

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
