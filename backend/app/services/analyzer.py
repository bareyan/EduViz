"""
Material Analyzer - Analyzes PDFs and images for math content
Uses AI to extract structure, equations, and suggest video topics
"""

import os
import re
import json
import base64
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import asyncio

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

# Gemini for analysis (optional, falls back to rule-based)
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None


@dataclass
class MathElement:
    """Represents a detected mathematical element"""
    type: str  # equation, theorem, definition, proof, example
    content: str
    page: int
    confidence: float


@dataclass 
class TopicSuggestion:
    """Suggested video topic"""
    index: int
    title: str
    description: str
    estimated_duration: int  # minutes
    complexity: str
    subtopics: List[str]
    content_refs: List[int]  # Page numbers


class MaterialAnalyzer:
    """Analyzes educational materials and suggests video topics"""
    
    def __init__(self):
        self.gemini_client = None
        if genai and os.getenv("GEMINI_API_KEY"):
            self.gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    
    async def analyze(self, file_path: str, file_id: str) -> Dict[str, Any]:
        """Main analysis entry point"""
        
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext == ".pdf":
            return await self._analyze_pdf(file_path, file_id)
        elif file_ext in [".png", ".jpg", ".jpeg", ".webp"]:
            return await self._analyze_image(file_path, file_id)
        else:
            raise ValueError(f"Unsupported file type: {file_ext}")
    
    async def _analyze_pdf(self, file_path: str, file_id: str) -> Dict[str, Any]:
        """Analyze a PDF document"""
        
        if not fitz:
            raise ImportError("PyMuPDF (fitz) is required for PDF analysis")
        
        doc = fitz.open(file_path)
        total_pages = len(doc)
        
        # Extract text and images from each page
        all_text = []
        math_elements = []
        
        for page_num in range(total_pages):
            page = doc[page_num]
            text = page.get_text()
            all_text.append(text)
            
            # Detect math elements using patterns
            elements = self._detect_math_elements(text, page_num + 1)
            math_elements.extend(elements)
        
        doc.close()
        
        # Combine all text for analysis
        full_text = "\n\n".join(all_text)
        
        # Generate topic suggestions
        topics = await self._generate_topic_suggestions(
            full_text, 
            math_elements,
            total_pages,
            "pdf"
        )
        
        # Calculate estimated videos needed
        total_duration = sum(t["estimated_duration"] for t in topics)
        estimated_videos = max(1, (total_duration + 19) // 20)  # 20 min per video
        
        return {
            "analysis_id": f"analysis_{file_id}",
            "file_id": file_id,
            "material_type": "pdf",
            "total_content_pages": total_pages,
            "detected_math_elements": len(math_elements),
            "suggested_topics": topics,
            "estimated_total_videos": estimated_videos,
            "summary": self._generate_summary(full_text, math_elements)
        }
    
    async def _analyze_image(self, file_path: str, file_id: str) -> Dict[str, Any]:
        """Analyze an image (single page of math content)"""
        
        # For images, we'll use OCR or vision AI
        extracted_text = await self._extract_text_from_image(file_path)
        math_elements = self._detect_math_elements(extracted_text, 1)
        
        topics = await self._generate_topic_suggestions(
            extracted_text,
            math_elements,
            1,
            "image"
        )
        
        return {
            "analysis_id": f"analysis_{file_id}",
            "file_id": file_id,
            "material_type": "image",
            "total_content_pages": 1,
            "detected_math_elements": len(math_elements),
            "suggested_topics": topics,
            "estimated_total_videos": 1,
            "summary": self._generate_summary(extracted_text, math_elements)
        }
    
    def _detect_math_elements(self, text: str, page: int) -> List[MathElement]:
        """Detect mathematical elements in text using pattern matching"""
        
        elements = []
        
        # Patterns for common math elements
        patterns = {
            "equation": [
                r"(?:equation|formula)[\s:]+(.+?)(?:\n|$)",
                r"(\$\$.+?\$\$)",
                r"(\\\[.+?\\\])",
                r"([a-zA-Z]\s*=\s*[^,\n]+)",
            ],
            "theorem": [
                r"(?:theorem|lemma|proposition)[\s\d.]*[:\s]+(.+?)(?:\n\n|$)",
            ],
            "definition": [
                r"(?:definition|def\.?)[\s\d.]*[:\s]+(.+?)(?:\n\n|$)",
            ],
            "proof": [
                r"(?:proof)[:\s]+(.+?)(?:□|QED|\n\n|$)",
            ],
            "example": [
                r"(?:example|ex\.?)[\s\d.]*[:\s]+(.+?)(?:\n\n|$)",
            ],
        }
        
        for elem_type, pattern_list in patterns.items():
            for pattern in pattern_list:
                matches = re.finditer(pattern, text, re.IGNORECASE | re.DOTALL)
                for match in matches:
                    elements.append(MathElement(
                        type=elem_type,
                        content=match.group(1) if match.lastindex else match.group(0),
                        page=page,
                        confidence=0.7
                    ))
        
        return elements
    
    async def _extract_text_from_image(self, file_path: str) -> str:
        """Extract text from an image using OCR or Vision AI"""
        
        # Try Gemini Vision if available
        if self.gemini_client:
            try:
                import PIL.Image
                image = PIL.Image.open(file_path)
                
                response = await asyncio.to_thread(
                    self.gemini_client.models.generate_content,
                    model="gemini-3-flash-preview",
                    contents=[
                        "Extract all text and mathematical content from this image. Format equations in LaTeX where possible.",
                        image
                    ]
                )
                return response.text
            except Exception as e:
                print(f"Gemini Vision API failed: {e}")
        
        # Fallback: return placeholder
        return "Mathematical content detected in image. Manual transcription may be needed."
    
    async def _generate_topic_suggestions(
        self,
        text: str,
        math_elements: List[MathElement],
        total_pages: int,
        material_type: str
    ) -> List[Dict[str, Any]]:
        """Generate video topic suggestions based on content"""
        
        # Try AI-powered suggestion first
        if self.gemini_client:
            try:
                return await self._ai_generate_topics(text, math_elements)
            except Exception as e:
                print(f"AI topic generation failed: {e}")
        
        # Fallback: rule-based topic generation
        return self._rule_based_topics(text, math_elements, total_pages)
    
    async def _ai_generate_topics(
        self,
        text: str,
        math_elements: List[MathElement]
    ) -> List[Dict[str, Any]]:
        """Use AI to generate topic suggestions"""
        
        # Prepare context about detected elements
        elements_summary = "\n".join([
            f"- {e.type}: {e.content[:100]}..." 
            for e in math_elements[:20]
        ])
        
        prompt = f"""Analyze this educational math material and suggest video topics.
Each video should be max 20 minutes. Create a 3Blue1Brown style breakdown.

Material excerpt (first 3000 chars):
{text[:3000]}

Detected math elements:
{elements_summary}

Return a JSON array of topics with this structure:
[
  {{
    "index": 0,
    "title": "Topic title",
    "description": "Brief description of what the video will cover",
    "estimated_duration": 10,  // minutes
    "complexity": "beginner|intermediate|advanced",
    "subtopics": ["subtopic1", "subtopic2"]
  }}
]

Generate 2-5 focused topics. Make them engaging and educational.
Return ONLY valid JSON, no markdown formatting."""

        response = await asyncio.to_thread(
            self.gemini_client.models.generate_content,
            model="gemini-3-flash-preview",
            contents=prompt
        )
        
        # Parse JSON from response
        response_text = response.text.strip()
        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            response_text = re.sub(r'^```\w*\n?', '', response_text)
            response_text = re.sub(r'\n?```$', '', response_text)
        
        result = json.loads(response_text)
        topics = result.get("topics", result) if isinstance(result, dict) else result
        
        # Ensure proper format
        formatted_topics = []
        for i, topic in enumerate(topics):
            formatted_topics.append({
                "index": i,
                "title": topic.get("title", f"Topic {i+1}"),
                "description": topic.get("description", ""),
                "estimated_duration": topic.get("estimated_duration", 10),
                "complexity": topic.get("complexity", "intermediate"),
                "subtopics": topic.get("subtopics", [])
            })
        
        return formatted_topics
    
    def _rule_based_topics(
        self,
        text: str,
        math_elements: List[MathElement],
        total_pages: int
    ) -> List[Dict[str, Any]]:
        """Generate topics using rule-based analysis"""
        
        topics = []
        
        # Group elements by type
        theorems = [e for e in math_elements if e.type == "theorem"]
        definitions = [e for e in math_elements if e.type == "definition"]
        equations = [e for e in math_elements if e.type == "equation"]
        
        # Detect main subject from text
        subject = self._detect_subject(text)
        
        # Generate overview topic
        topics.append({
            "index": 0,
            "title": f"Introduction to {subject}",
            "description": f"A visual overview of the key concepts in {subject}, setting the foundation for deeper understanding.",
            "estimated_duration": min(15, total_pages * 2),
            "complexity": "beginner",
            "subtopics": ["Core intuition", "Key definitions", "Why this matters"]
        })
        
        # Generate topics based on detected content
        if definitions:
            topics.append({
                "index": 1,
                "title": f"Key Definitions in {subject}",
                "description": "Deep dive into the fundamental definitions with visual intuition.",
                "estimated_duration": min(12, len(definitions) * 3),
                "complexity": "beginner",
                "subtopics": [d.content[:50] for d in definitions[:3]]
            })
        
        if theorems:
            topics.append({
                "index": len(topics),
                "title": "Theorems and Proofs Visualized",
                "description": "Understanding the key theorems through animated proofs.",
                "estimated_duration": min(18, len(theorems) * 5),
                "complexity": "intermediate",
                "subtopics": [t.content[:50] for t in theorems[:3]]
            })
        
        if equations:
            topics.append({
                "index": len(topics),
                "title": "Equations That Make It Click",
                "description": "Breaking down the important equations with step-by-step animations.",
                "estimated_duration": min(15, len(equations) * 2),
                "complexity": "intermediate",
                "subtopics": ["Derivation walkthrough", "Geometric interpretation", "Applications"]
            })
        
        # Add advanced topic if content is substantial
        if total_pages > 5 or len(math_elements) > 10:
            topics.append({
                "index": len(topics),
                "title": f"Advanced {subject}: Putting It All Together",
                "description": "Connecting all concepts with challenging examples and applications.",
                "estimated_duration": 18,
                "complexity": "advanced",
                "subtopics": ["Complex examples", "Real-world applications", "Further exploration"]
            })
        
        return topics
    
    def _detect_subject(self, text: str) -> str:
        """Detect the mathematical subject from text"""
        
        subjects = {
            "calculus": ["derivative", "integral", "limit", "differentiation", "integration"],
            "linear algebra": ["matrix", "vector", "eigenvalue", "determinant", "linear transformation"],
            "probability": ["probability", "random", "distribution", "expected value", "variance"],
            "statistics": ["mean", "median", "standard deviation", "hypothesis", "regression"],
            "number theory": ["prime", "divisibility", "modular", "congruence"],
            "geometry": ["triangle", "circle", "polygon", "angle", "area", "volume"],
            "topology": ["topology", "continuous", "homeomorphism", "manifold"],
            "algebra": ["group", "ring", "field", "polynomial", "equation"],
            "analysis": ["convergence", "series", "sequence", "continuity", "metric"],
        }
        
        text_lower = text.lower()
        scores = {}
        
        for subject, keywords in subjects.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > 0:
                scores[subject] = score
        
        if scores:
            return max(scores, key=scores.get).title()
        
        return "Mathematics"
    
    def _generate_summary(self, text: str, math_elements: List[MathElement]) -> str:
        """Generate a brief summary of the material"""
        
        subject = self._detect_subject(text)
        num_elements = len(math_elements)
        
        element_types = {}
        for e in math_elements:
            element_types[e.type] = element_types.get(e.type, 0) + 1
        
        type_summary = ", ".join([f"{count} {etype}s" for etype, count in element_types.items()])
        
        return f"This material covers {subject}. Detected {num_elements} mathematical elements including {type_summary or 'various concepts'}. Ready for visualization."
