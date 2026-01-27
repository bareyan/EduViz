"""
Script generation prompts.

Used by: script_generation/generator.py, overview_generator.py, section_generator.py
"""

from .base import PromptTemplate


SCRIPT_OVERVIEW = PromptTemplate(
    template="""You are an expert educator creating a video script.

Topic: {topic_title}
{topic_description}

Language: {language_name}
{language_instruction}

Content to cover:
{content}

Create a clear, engaging video script with sections.
Each section needs:
- title: Section title
- narration: What the narrator says (conversational, clear)
- visual_description: What viewers see on screen
- key_points: Main concepts covered

Output as JSON with "sections" array.""",
    description="Generate overview script from content"
)


SCRIPT_OUTLINE = PromptTemplate(
    template="""Analyze this educational content and create a detailed outline.

Topic: {topic_title}
Content: {content}

Language: {language_name}
{language_instruction}

Duration target: {duration_minutes} minutes

{focus_instructions}
{context_instructions}

Create an outline with:
1. Document analysis (content type, complexity, gaps)
2. Learning objectives
3. Prerequisites
4. Sections outline with timing

Output as JSON.""",
    description="Generate detailed outline for comprehensive mode"
)


SCRIPT_SECTION = PromptTemplate(
    template="""Generate the full narration for this section.

Section: {section_title}
Type: {section_type}
Content to cover: {content_to_cover}

Language: {language_name}
{language_instruction}

Duration target: {duration_seconds} seconds (~{word_count} words)

Write engaging, clear narration that explains the concepts.
Include natural transitions and emphasis on key points.""",
    description="Generate narration for a single section"
)
