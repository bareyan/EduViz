"""
Outline builder for script generation (Phase 1)
"""

from typing import Dict, Any, Optional

from .base import BaseScriptGenerator


class OutlineBuilder:
    """Generates detailed pedagogical outlines for scripts."""

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
                        "content_type": {"type": "string"},
                        "content_context": {"type": "string"},
                        "total_theorems": {"type": "integer"},
                        "total_proofs": {"type": "integer"},
                        "total_definitions": {"type": "integer"},
                        "total_examples": {"type": "integer"},
                        "complexity_level": {"type": "string"},
                        "gaps_to_fill": {"type": "array", "items": {"type": "string"}}
                    }
                },
                "title": {"type": "string"},
                "subject_area": {"type": "string"},
                "overview": {"type": "string"},
                "learning_objectives": {"type": "array", "items": {"type": "string"}},
                "prerequisites": {"type": "array", "items": {"type": "string"}},
                "total_duration_minutes": {"type": "integer"},
                "sections_outline": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "title": {"type": "string"},
                            "section_type": {"type": "string"},
                            "content_to_cover": {"type": "string"},
                            "depth_elements": {
                                "type": "object",
                                "properties": {
                                    "motivation": {"type": "string"},
                                    "intuition": {"type": "string"},
                                    "connections": {"type": "string"}
                                }
                            },
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
                            "page_start",
                            "page_end",
                        ]
                    }
                }
            },
            "required": ["title", "subject_area", "overview", "learning_objectives", "sections_outline"]
        }

        try:
            # Create config with structured JSON output
            from app.services.infrastructure.llm import PromptConfig
            config = PromptConfig(
                temperature=0.7,
                max_output_tokens=4096,
                timeout=300,
                response_format="json"
            )

            contents = None
            if pdf_path:
                pdf_part = self.base.build_pdf_part(pdf_path)
                if pdf_part:
                    contents = self.base.build_prompt_contents(phase1_prompt, pdf_part)

            response_text = await self.base.generate_with_engine(
                prompt=phase1_prompt,
                config=config,
                response_schema=response_schema,
                contents=contents,
            )
            outline = self.base.parse_json(response_text)
            if not outline:
                outline = self._fallback_outline(topic)
        except Exception:
            outline = self._fallback_outline(topic)

        return outline

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
TARGET DURATION: {suggested_duration}+ minutes (take as long as needed for deep understanding)
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
    "total_duration_minutes": [realistic estimate - comprehensive videos can be 30-60+ min],
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
            "estimated_duration_seconds": [60-300],
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
