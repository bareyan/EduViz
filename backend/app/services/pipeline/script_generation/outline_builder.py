"""
Outline builder for script generation (Phase 1)
"""

from typing import Dict, Any, Optional, List, Tuple

from app.core import get_logger
from app.services.infrastructure.parsing.json_parser import is_likely_truncated_json
from .schema_filter import filter_outline

from .base import BaseScriptGenerator


class OutlineBuilder:
    """Generates detailed pedagogical outlines for scripts."""
    MAX_OUTLINE_ATTEMPTS = 3

    LANGUAGE_NAMES = {
        "en": "English",
        "fr": "French",
        "es": "Spanish",
        "de": "German",
        "it": "Italian",
        "pt": "Portuguese",
        "zh": "Chinese",
        "ja": "Japanese",
        "ko": "Korean",
        "ar": "Arabic",
        "ru": "Russian",
        "hy": "Armenian",
    }

    def __init__(self, base: BaseScriptGenerator):
        self.base = base
        self.logger = get_logger(__name__, component="outline_builder")

    async def build_outline(
        self,
        content: str,
        topic: Dict[str, Any],
        language_instruction: str,
        language_name: str,
        content_focus: str,
        document_context: str = "auto",
        video_mode: str = "comprehensive",
        pdf_path: Optional[str] = None,
        total_pages: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Generate a detailed outline (Phase 1)."""

        content_length = len(content)
        estimated_duration = topic.get("estimated_duration", 20)

        if video_mode == "overview":
            suggested_duration = min(7, max(3, estimated_duration // 3))
        else:
            suggested_duration = max(45, content_length // 80)

        focus_instructions = self._build_focus_instructions(content_focus)
        context_instructions = self._build_context_instructions(document_context)

        prompt_content = content
        if pdf_path and not prompt_content:
            prompt_content = "PDF attached. Use the document directly."

        phase1_prompt = self._build_prompt(
            topic=topic,
            content=prompt_content,
            suggested_duration=suggested_duration,
            language_instruction=language_instruction,
            focus_instructions=focus_instructions,
            context_instructions=context_instructions,
            language_name=language_name,
            video_mode=video_mode,
            total_pages=total_pages,
            pdf_attached=bool(pdf_path),
        )

        # Define response schema for structured JSON output
        response_schema = {
            "type": "object",
            "properties": {
                "document_analysis": {
                    "type": "object",
                    "properties": {
                        "gaps_to_fill": {"type": "array", "items": {"type": "string"}}
                    }
                },
                "title": {"type": "string"},
                "subject_area": {"type": "string"},
                "overview": {"type": "string"},
                "learning_objectives": {"type": "array", "items": {"type": "string"}},
                "sections_outline": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "title": {"type": "string"},
                            "section_type": {"type": "string"},
                            "content_to_cover": {"type": "string"},
                            "key_points": {"type": "array", "items": {"type": "string"}},
                            "visual_type": {"type": "string"},
                            "estimated_duration_seconds": {"type": "integer"},
                            "page_start": {"type": "integer"},
                            "page_end": {"type": "integer"},
                        },
                        "required": [
                            "id",
                            "title",
                            "section_type",
                            "content_to_cover",
                            "key_points",
                            "visual_type",
                            "estimated_duration_seconds",
                        ]
                    }
                }
            },
            "required": ["title", "subject_area", "overview", "learning_objectives", "sections_outline"]
        }

        # Create config with structured JSON output
        from app.services.infrastructure.llm import PromptConfig
        config = PromptConfig(
            temperature=0.7,
            max_output_tokens=4096*4,
            timeout=300,
            response_format="json"
        )

        strict_suffix = (
            "\n\nSTRICT JSON ONLY:\n"
            "- Return ONLY valid JSON\n"
            "- Do NOT wrap in markdown\n"
            "- Include all required keys\n"
            "- No trailing commas\n"
        )

        last_error: Optional[Exception] = None
        for attempt in range(1, self.MAX_OUTLINE_ATTEMPTS + 1):
            prompt = phase1_prompt if attempt == 1 else f"{phase1_prompt}{strict_suffix}"
            contents = None
            if pdf_path:
                pdf_part = self.base.build_pdf_part(pdf_path)
                if pdf_part:
                    contents = self.base.build_prompt_contents(prompt, pdf_part)

            try:
                self.logger.info(
                    "Outline generation attempt",
                    extra={
                        "attempt": attempt,
                        "max_attempts": self.MAX_OUTLINE_ATTEMPTS,
                        "pdf_attached": bool(pdf_path),
                    },
                )

                response_text = await self.base.generate_with_engine(
                    prompt=prompt,
                    config=config,
                    response_schema=response_schema,
                    contents=contents,
                )

                if not response_text:
                    self.logger.error(
                        "Outline generation returned empty response",
                        extra={"attempt": attempt},
                    )
                    continue

                outline = self.base.parse_json(response_text)
                outline = filter_outline(outline)
                is_valid, issues = self._validate_outline(outline)

                if not is_valid:
                    self.logger.error(
                        "Outline parsing/validation failed",
                        extra={
                            "attempt": attempt,
                            "issues": issues,
                            "response_len": len(response_text),
                            "truncated_json": is_likely_truncated_json(response_text),
                            "response_preview": response_text[:2000],
                        },
                    )
                    continue

                self.logger.info(
                    "Outline generated successfully",
                    extra={
                        "attempt": attempt,
                        "sections_count": len(outline.get("sections_outline", [])),
                    },
                )
                return outline
            except Exception as exc:
                last_error = exc
                self.logger.exception(
                    "Outline generation attempt raised exception",
                    extra={"attempt": attempt},
                )

        error_msg = (
            f"Outline generation failed after {self.MAX_OUTLINE_ATTEMPTS} attempts"
        )
        if last_error:
            error_msg = f"{error_msg}: {last_error}"
        raise RuntimeError(error_msg)

    def _validate_outline(self, outline: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Basic validation for required outline fields."""
        issues: List[str] = []
        if not isinstance(outline, dict) or not outline:
            return False, ["outline_missing_or_empty"]

        required_keys = [
            "title",
            "subject_area",
            "overview",
            "learning_objectives",
            "sections_outline",
        ]
        missing = [key for key in required_keys if key not in outline]
        if missing:
            issues.append(f"missing_keys:{','.join(missing)}")

        sections = outline.get("sections_outline")
        if not isinstance(sections, list) or not sections:
            issues.append("sections_outline_missing_or_empty")
        return len(issues) == 0, issues

    def _build_focus_instructions(self, content_focus: str) -> str:
        if content_focus == "practice":
            return (
                """
CONTENT FOCUS: PRACTICE-ORIENTED
- Prioritize examples over abstract theory
- For every concept, include 2-3 worked examples
- Show step-by-step problem solving
- Focus on "how to apply" rather than "why it works"
"""
            )
        if content_focus == "theory":
            return (
                """
CONTENT FOCUS: THEORY-ORIENTED  
- Prioritize rigorous proofs and formal derivations
- Explore the "why" behind every concept
- Build deep understanding of underlying principles
- Take time with mathematical rigor
"""
            )
        return (
            """
CONTENT FOCUS: FOLLOW DOCUMENT STRUCTURE
- Mirror the document's natural balance of theory and practice
- If the document is example-heavy, be example-heavy
- If the document is proof-focused, be proof-focused
"""
        )

    def _build_context_instructions(self, document_context: str) -> str:
        """Build context instructions based on document_context setting."""
        if document_context == "standalone":
            return (
                """
DOCUMENT CONTEXT: STANDALONE
- This document is self-contained
- Provide all necessary background within this video
- Don't assume viewers have seen related content
"""
            )
        if document_context == "part-of-series":
            return (
                """
DOCUMENT CONTEXT: PART OF A SERIES
- This document is part of a larger series
- You may reference concepts from previous parts
- Focus on the new material being introduced
"""
            )
        # Default: "auto" - let the AI determine from content
        return (
            """
DOCUMENT CONTEXT: AUTO-DETECT
- Analyze the document to determine if it's standalone or part of a series
- Adjust explanations accordingly
"""
        )

    def _build_prompt(
        self,
        topic: Dict[str, Any],
        content: str,
        suggested_duration: int,
        language_instruction: str,
        focus_instructions: str,
        context_instructions: str,
        language_name: str,
        video_mode: str,
        total_pages: Optional[int],
        pdf_attached: bool,
    ) -> str:
        page_note = f"{total_pages}" if total_pages is not None else "unknown"
        pdf_note = ""
        if pdf_attached:
            pdf_note = (
                "\nPDF NOTE:\n"
                "- The source PDF is ATTACHED. Use it directly.\n"
                "- For EACH section, include page_start and page_end (1-based, inclusive).\n"
                f"- Total pages: {page_note}\n"
            )

        return f"""You are an expert university professor planning a COMPREHENSIVE lecture video that provides DEEP UNDERSTANDING.

Your goal is NOT just to cover the material, but to help viewers truly UNDERSTAND it at a profound level.
Create a DETAILED PEDAGOGICAL OUTLINE that ensures:
1. COMPLETE coverage of ALL source material
2. DEEP understanding through motivation, intuition, and context
3. SUPPLEMENTARY explanations that go BEYOND the source when needed{language_instruction}

SOURCE-FIRST PRIORITY:
- Cover EVERY detail from the source material before adding supplementary explanations.
- Do not skip steps or omit intermediate values in worked examples.
- Avoid placeholder phrasing like "we fill the table" unless the table is explicitly specified.

{focus_instructions}

{context_instructions}

═══════════════════════════════════════════════════════════════════════════════
                         DEPTH REQUIREMENTS
═══════════════════════════════════════════════════════════════════════════════

For EVERY concept, definition, or theorem, plan to cover:
• MOTIVATION: WHY do we need this? What problem does it solve?
• INTUITION: What's the underlying idea in simple terms?
• FORMAL STATEMENT: The precise mathematical formulation
• CONTEXT: How does this connect to what we already know?
• IMPLICATIONS: What does this allow us to do? Why is it powerful?

For EVERY proof or derivation:
• PROOF STRATEGY: What approach are we taking and why?
• KEY INSIGHTS: What are the clever ideas that make it work?
• STEP-BY-STEP: Break down each logical step
• POTENTIAL PITFALLS: Common mistakes or misconceptions

For EXAMPLES:
• Start with SIMPLE cases to build intuition
• Progress to COMPLEX applications
• Show EDGE CASES when relevant
• Connect back to theory
• Break worked examples into FINE-GRAINED steps (one step per section if needed)
• Specify ALL intermediate values, tables, matrices, and calculations that must be shown

ADD SUPPLEMENTARY CONTENT when it aids understanding:
• Historical context or motivation (if helpful)
• Visual intuitions and geometric interpretations
• Connections to other fields or concepts
• Common misconceptions and how to avoid them
• Alternative perspectives on the same concept

═══════════════════════════════════════════════════════════════════════════════
TOPIC: {topic.get('title', 'Educational Content')}
DESCRIPTION: {topic.get('description', '')}
SUBJECT AREA: {topic.get('subject_area', 'general')}
VIDEO MODE: {video_mode.upper()}
OUTPUT LANGUAGE: {language_name}
═══════════════════════════════════════════════════════════════════════════════

{pdf_note}
SOURCE MATERIAL (analyze ALL of this - nothing should be omitted):
{content[:60000]}

═══════════════════════════════════════════════════════════════════════════════

Create an outline with sections for:
- Introduction (hook, motivation, prerequisites, learning objectives)
- Each major definition (motivation → intuition → formal statement → examples)
- Each theorem/lemma/proposition (motivation → statement → proof strategy → proof → implications)
- Worked examples (simple → complex, with connections to theory)
- Connections and context (how concepts relate to each other)
- Conclusion (big picture, recap, what comes next)

IMPORTANT: If the source material is terse or assumes background knowledge, 
ADD explanatory sections to fill gaps and provide context.

DETAIL LEVEL REQUIREMENTS:
- This outline is STRUCTURAL, not exhaustive.
- Do NOT include full derivations, full tables, datasets, or long explanations here.
- Full data and calculations will be generated in the SECTION stage.
- Prefer more, smaller sections over broad summaries.
- Each section should focus on a single concept or a single step in a worked example.
- If a table, matrix, or dataset is referenced, outline where its full values will appear.

Respond with ONLY valid JSON:
{{
    "document_analysis": {{
        "content_type": "[theoretical|practical|factual|problem-solving|mixed]",
        "content_context": "[standalone|part-of-series]",
        "total_theorems": [count],
        "total_proofs": [count],
        "total_definitions": [count],
        "total_examples": [count],
        "complexity_level": "[introductory|intermediate|advanced]",
        "gaps_to_fill": ["List of concepts that need more explanation for clarity"]
    }},
    "title": "[Engaging video title in {language_name}]",
    "subject_area": "[math|cs|physics|economics|biology|engineering|general]",
    "overview": "[2-3 sentence hook describing what viewers will learn and WHY it matters]",
    "learning_objectives": ["What viewers will understand", "What they will be able to do"],
    "prerequisites": ["Concepts viewers should know beforehand"],
    "total_duration_minutes": [optional estimate, if helpful],
    "sections_outline": [
        {{
            "id": "[unique_id like 'intro', 'motivation_1', 'def_1', 'intuition_1', 'thm_1', 'proof_1', 'example_1']",
            "title": "[Section title in {language_name}]",
            "section_type": "[introduction|motivation|definition|intuition|theorem|proof|example|application|connection|summary]",
            "content_to_cover": "[Detailed description of what this section must cover from source]",
            "depth_elements": {{
                "motivation": "[Why this matters - for definitions/theorems]",
                "intuition": "[Simple explanation - for complex concepts]",
                "connections": "[Links to other concepts]"
            }},
            "key_points": ["Point 1", "Point 2", "Point 3", "Point 4"],
            "visual_type": "[animated|static|mixed|diagram|graph]",
            "estimated_duration_seconds": [integer],
            "page_start": [1-based start page],
            "page_end": [1-based end page]
        }}
    ]
}}"""

    def _fallback_outline(self, topic: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "title": topic.get("title", "Educational Content"),
            "subject_area": topic.get("subject_area", "general"),
            "overview": topic.get("description", ""),
            "sections_outline": [
                {"id": "intro", "title": "Introduction", "section_type": "introduction", "content_to_cover": "Overview of the topic", "key_points": ["Introduction"], "visual_type": "static", "estimated_duration_seconds": 60},
                {"id": "main", "title": "Main Content", "section_type": "content", "content_to_cover": "Core material", "key_points": ["Main concepts"], "visual_type": "mixed", "estimated_duration_seconds": 300},
                {"id": "conclusion", "title": "Conclusion", "section_type": "summary", "content_to_cover": "Summary", "key_points": ["Recap"], "visual_type": "static", "estimated_duration_seconds": 60},
            ],
        }
