"""
Material Analyzer V2 - Uses Gemini to analyze PDFs and images for math content
Generates structured video topic suggestions
"""

import os
import json
import base64
import asyncio
from typing import List, Dict, Any, Optional
from pathlib import Path

# PDF processing
try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

# Image processing
try:
    from PIL import Image
except ImportError:
    Image = None

# Gemini
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None


class MaterialAnalyzer:
    """Analyzes educational materials using Gemini AI"""
    
    MODEL = "gemini-flash-lite-latest"  # Fast lite model for analysis
    
    # Threshold for "massive" documents that warrant multiple videos
    MASSIVE_DOC_PAGES = 15
    MASSIVE_DOC_CHAPTERS = 5
    
    def __init__(self):
        self.client = None
        api_key = os.getenv("GEMINI_API_KEY")
        if genai and api_key:
            self.client = genai.Client(api_key=api_key)
        else:
            raise ValueError("GEMINI_API_KEY environment variable is required")
    
    async def analyze(self, file_path: str, file_id: str) -> Dict[str, Any]:
        """Main analysis entry point"""
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext == ".pdf":
            return await self._analyze_pdf(file_path, file_id)
        elif file_ext in [".png", ".jpg", ".jpeg", ".webp", ".gif"]:
            return await self._analyze_image(file_path, file_id)
        elif file_ext in [".tex", ".txt"]:
            return await self._analyze_text(file_path, file_id)
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")
    
    async def _analyze_pdf(self, file_path: str, file_id: str) -> Dict[str, Any]:
        """Analyze a PDF document using Gemini"""
        if not fitz:
            raise ImportError("PyMuPDF (fitz) is required for PDF analysis")
        
        # Extract text from PDF
        doc = fitz.open(file_path)
        total_pages = len(doc)
        
        all_text = []
        for page_num in range(total_pages):
            page = doc[page_num]
            text = page.get_text()
            all_text.append(f"=== Page {page_num + 1} ===\n{text}")
        
        doc.close()
        full_text = "\n\n".join(all_text)
        
        # Use Gemini to analyze the content
        analysis = await self._gemini_analyze(full_text, total_pages)
        
        return {
            "analysis_id": f"analysis_{file_id}",
            "file_id": file_id,
            "material_type": "pdf",
            "total_content_pages": total_pages,
            **analysis
        }
    
    async def _analyze_text(self, file_path: str, file_id: str) -> Dict[str, Any]:
        """Analyze a text file (.tex or .txt) using Gemini"""
        
        # Read the text file
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            full_text = f.read()
        
        # Estimate "pages" based on content length (roughly 3000 chars per page)
        estimated_pages = max(1, len(full_text) // 3000)
        
        # Use Gemini to analyze the content
        analysis = await self._gemini_analyze(full_text, estimated_pages)
        
        return {
            "analysis_id": f"analysis_{file_id}",
            "file_id": file_id,
            "material_type": "text",
            "total_content_pages": estimated_pages,
            **analysis
        }
    
    async def _analyze_image(self, file_path: str, file_id: str) -> Dict[str, Any]:
        """Analyze an image using Gemini Vision"""
        
        # Read and encode image
        with open(file_path, "rb") as f:
            image_data = f.read()
        
        # Use Gemini to analyze with vision
        analysis = await self._gemini_analyze_image(image_data, file_path)
        
        return {
            "analysis_id": f"analysis_{file_id}",
            "file_id": file_id,
            "material_type": "image",
            "total_content_pages": 1,
            **analysis
        }
    
    async def _gemini_analyze(self, text: str, total_pages: int) -> Dict[str, Any]:
        """Use Gemini to analyze text content and suggest video topics"""
        
        # Determine if document is massive (warrants multiple videos)
        is_massive = total_pages >= self.MASSIVE_DOC_PAGES
        
        prompt = f"""You are an expert educator preparing comprehensive educational video content with animated visuals.

Analyze this content and determine the best video structure.
IMPORTANT: Detect the SUBJECT AREA (math, computer science, physics, economics, biology, engineering, general) from the content.

DOCUMENT INFO:
- Total pages: {total_pages}
- {"This is a LARGE document - consider splitting into logical chapter-based videos" if is_massive else "This is a standard-sized document - create ONE comprehensive video"}

CONTENT:
{text[:20000]}

{"LARGE DOCUMENT INSTRUCTIONS:" if is_massive else "STANDARD DOCUMENT INSTRUCTIONS:"}
{'''Since this is a large document with multiple distinct chapters/sections:
- Create separate video topics ONLY if there are clearly distinct chapters
- Each video should cover ONE complete chapter thoroughly
- Maximum 3-4 videos even for large documents
- Each video should be 15-25 minutes (comprehensive)''' if is_massive else '''Create ONE comprehensive video that covers ALL the material:
- The video should be thorough enough to REPLACE reading the document
- Include all key concepts, proofs/algorithms, and examples
- Target duration: 15-25 minutes for complete coverage
- Show step-by-step explanations visually'''}

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
{{
    "summary": "Comprehensive summary of the material",
    "main_subject": "The primary topic",
    "subject_area": "math|cs|physics|economics|biology|engineering|general",
    "key_concepts": ["all", "major", "concepts", "covered"],
    "detected_math_elements": {total_pages * 3},
    "document_structure": "single_topic|multi_chapter",
    "suggested_topics": [
        {{
            "index": 0,
            "title": "[Descriptive Topic Name]",
            "description": "Comprehensive video covering all material. Includes all key concepts, explanations, and examples.",
            "estimated_duration": 20,
            "complexity": "comprehensive",
            "subject_area": "math|cs|physics|economics|biology|engineering|general",
            "subtopics": ["all", "major", "sections"],
            "prerequisites": ["required background"],
            "visual_ideas": ["step-by-step explanations", "visualizations", "worked examples"]
        }}
    ],
    "estimated_total_videos": 1
}}

{"If the document has 5+ clearly distinct chapters, you may suggest up to 3 separate videos. Otherwise, create ONE comprehensive video." if is_massive else "Create exactly ONE comprehensive video covering everything."}
The goal is THOROUGH coverage - the video should contain ALL information from the source."""

        response = await asyncio.to_thread(
            self.client.models.generate_content,
            model=self.MODEL,
            contents=prompt
        )
        
        return self._parse_json_response(response.text)
    
    async def _gemini_analyze_image(self, image_data: bytes, file_path: str) -> Dict[str, Any]:
        """Use Gemini Vision to analyze an image"""
        
        # Determine mime type
        ext = Path(file_path).suffix.lower()
        mime_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif"
        }
        mime_type = mime_types.get(ext, "image/png")
        
        prompt = """You are an expert educator preparing COMPREHENSIVE educational video content.

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

CRITICAL: Create exactly ONE comprehensive video covering everything."""

        # Create image part for Gemini
        image_part = types.Part.from_bytes(data=image_data, mime_type=mime_type)
        
        response = await asyncio.to_thread(
            self.client.models.generate_content,
            model=self.MODEL,
            contents=[prompt, image_part]
        )
        
        return self._parse_json_response(response.text)
    
    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """Parse JSON from Gemini response, handling markdown code blocks"""
        text = text.strip()
        
        # Remove markdown code blocks if present
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first line (```json) and last line (```)
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)
        
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            print(f"JSON parse error: {e}")
            print(f"Response text: {text[:500]}")
            # Return a default structure
            return {
                "summary": "Failed to parse analysis",
                "main_subject": "Unknown",
                "difficulty_level": "intermediate",
                "key_concepts": [],
                "detected_math_elements": 0,
                "suggested_topics": [{
                    "index": 0,
                    "title": "Introduction to the Topic",
                    "description": "An overview of the mathematical concepts",
                    "estimated_duration": 10,
                    "complexity": "intermediate",
                    "subtopics": ["Overview"],
                    "prerequisites": [],
                    "visual_ideas": ["Basic animations"]
                }],
                "estimated_total_videos": 1
            }
