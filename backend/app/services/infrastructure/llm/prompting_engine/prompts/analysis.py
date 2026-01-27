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

Analyze this content and determine the best video structure.
IMPORTANT: Detect the SUBJECT AREA (math, computer science, physics, economics, biology, engineering, general) from the content.

DOCUMENT INFO:
- Total pages: {total_pages}
- {size_note}

CONTENT:
{content_sample}

{instructions}

VIDEO PHILOSOPHY:
1. The video should show concepts VISUALLY - not just narrate them
2. Sometimes let the content "speak for itself" without constant narration
3. For derivations/algorithms: show step-by-step work
4. Include visual demonstration sections
5. Balance: 60% narrated content, 40% visual demonstrations

CONTENT ADAPTATION (analyze and identify):
- MATHEMATICS: Focus on equations, proofs, theorems, derivations
- COMPUTER SCIENCE: Focus on algorithms, data structures, code, complexity
- PHYSICS: Focus on phenomena, equations, experiments, applications
- ECONOMICS: Focus on models, graphs, market dynamics, policies
- BIOLOGY/CHEMISTRY: Focus on processes, structures, reactions
- ENGINEERING: Focus on systems, designs, trade-offs
- GENERAL: Focus on concepts, examples, analogies

Respond with ONLY valid JSON (no markdown, no code blocks):
{{{{
    "summary": "Comprehensive summary of the material",
    "main_subject": "The primary topic",
    "subject_area": "math|cs|physics|economics|biology|engineering|general",
    "key_concepts": ["all", "major", "concepts", "covered"],
    "detected_math_elements": {detected_math_elements},
    "document_structure": "single_topic|multi_chapter",
    "suggested_topics": [
        {{{{
            "index": 0,
            "title": "[Descriptive Topic Name]",
            "description": "Comprehensive video covering all material. Includes all key concepts, explanations, and examples.",
            "estimated_duration": 20,
            "complexity": "comprehensive",
            "subject_area": "math|cs|physics|economics|biology|engineering|general",
            "subtopics": ["all", "major", "sections"],
            "prerequisites": ["required background"],
            "visual_ideas": ["step-by-step explanations", "visualizations", "worked examples"]
        }}}}
    ],
    "estimated_total_videos": 1
}}}}

{closing_instruction}""",
    description="Analyze PDF content for educational videos"
)


ANALYZE_IMAGE = PromptTemplate(
    template="""You are an expert educator preparing COMPREHENSIVE educational video content.

Analyze this content from the image. Extract all text, equations, diagrams, concepts, code, or information visible.
IMPORTANT: Detect the SUBJECT AREA (math, computer science, physics, economics, biology, engineering, general).

Create ONE comprehensive video that covers ALL the content in this image:
- The video should REPLACE reading/studying this image entirely
- Include all concepts, explanations, and examples visible
- Show step-by-step explanations visually

Respond with ONLY valid JSON (no markdown, no code blocks):
{
    "summary": "Comprehensive summary of ALL content in this image",
    "main_subject": "The primary topic",
    "subject_area": "math|cs|physics|economics|biology|engineering|general",
    "key_concepts": ["all", "concepts", "visible", "in", "image"],
    "detected_math_elements": 5,
    "extracted_content": ["key content items"],
    "suggested_topics": [
        {
            "index": 0,
            "title": "[Descriptive Topic Name]",
            "description": "Comprehensive video covering EVERYTHING in this image.",
            "estimated_duration": 20,
            "complexity": "comprehensive",
            "subject_area": "math|cs|physics|economics|biology|engineering|general",
            "subtopics": ["every", "concept", "visible"],
            "prerequisites": ["required background"],
            "visual_ideas": ["step-by-step explanations", "visualizations"]
        }
    ],
    "estimated_total_videos": 1
}

CRITICAL: Create exactly ONE comprehensive video covering everything.""",
    description="Analyze image for video creation"
)
