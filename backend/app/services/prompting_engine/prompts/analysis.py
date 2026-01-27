"""
Content analysis prompts.

Used by: analysis/text.py, analysis/pdf.py, analysis/image.py
"""

from .base import PromptTemplate


ANALYZE_TEXT = PromptTemplate(
    template="""Analyze this text for educational video creation.

Content:
{content}

Identify:
- Main subject and topic
- Key concepts
- Complexity level
- Suggested video structure

Output as JSON.""",
    description="Basic text analysis"
)


ANALYZE_TEXT_CONTENT = PromptTemplate(
    template="""You are an expert educator preparing comprehensive educational video content.

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
{{{{
    "summary": "Comprehensive summary of the material",
    "main_subject": "The primary topic",
    "subject_area": "math|cs|physics|economics|biology|engineering|general",
    "key_concepts": ["all", "major", "concepts"],
    "detected_math_elements": 3,
    "suggested_topics": [
        {{{{
            "index": 0,
            "title": "[Descriptive Topic Name]",
            "description": "Comprehensive video covering all material",
            "estimated_duration": 20,
            "complexity": "intermediate",
            "subtopics": ["all", "major", "sections"],
            "prerequisites": ["required background"]
        }}}}
    ],
    "estimated_total_videos": 1
}}}}""",
    description="Analyze text content for educational videos"
)


ANALYZE_PDF = PromptTemplate(
    template="""Analyze this PDF content for video creation.

Pages: {page_count}
Content sample:
{content_sample}

Identify structure, key topics, and visual opportunities.
Output as JSON.""",
    description="Basic PDF analysis"
)


ANALYZE_PDF_CONTENT = PromptTemplate(
    template="""You are an expert educator preparing comprehensive educational video content with animated visuals.

Analyze this PDF document content and suggest video topics.
IMPORTANT: Detect the SUBJECT AREA (math, cs, physics, economics, biology, engineering, general).

DOCUMENT INFO:
- Total pages: {total_pages}
- Has mathematical content: {has_math}

CONTENT SAMPLE:
{content_sample}

Create ONE comprehensive video that covers ALL the material:
- The video should thoroughly cover the ENTIRE document
- Include all key concepts, examples, and visual elements
- Target duration: 15-30 minutes (longer for complex material)
- Consider Manim animations for mathematical/visual content

Respond with ONLY valid JSON (no markdown, no code blocks):
{{{{
    "summary": "Comprehensive summary",
    "main_subject": "Primary topic",
    "subject_area": "math|cs|physics|economics|biology|engineering|general",
    "key_concepts": ["all major concepts"],
    "detected_math_elements": 0,
    "suggested_topics": [
        {{{{
            "index": 0,
            "title": "[Descriptive Topic Name]",
            "description": "Comprehensive coverage",
            "estimated_duration": 20,
            "complexity": "intermediate",
            "subtopics": ["all sections"],
            "prerequisites": ["background needed"],
            "visual_ideas": ["animation ideas"]
        }}}}
    ],
    "estimated_total_videos": 1
}}}}""",
    description="Analyze PDF content for educational videos"
)


ANALYZE_IMAGE = PromptTemplate(
    template="""Analyze this image for educational video content.

Describe:
- What the image shows
- Key concepts illustrated
- How to animate/explain it
- Subject area

Output as JSON.""",
    description="Analyze image for video creation"
)
