"""
Script Generator - Creates structured video scripts from analyzed content
"""

import os
import json
import re
from typing import List, Dict, Any, Optional

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None


class ScriptGenerator:
    """Generates video scripts with narration and animation cues"""
    
    def __init__(self):
        self.gemini_client = None
        if genai and os.getenv("GEMINI_API_KEY"):
            self.gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    
    async def generate_scripts(
        self,
        file_path: str,
        selected_topics: List[int],
        max_video_length: int = 20
    ) -> List[Dict[str, Any]]:
        """Generate scripts for selected topics"""
        
        # Extract content from file
        content = await self._extract_content(file_path)
        
        # Generate script for each topic
        scripts = []
        for topic_idx in selected_topics:
            script = await self._generate_single_script(
                content,
                topic_idx,
                max_video_length
            )
            scripts.append(script)
        
        return scripts
    
    async def _extract_content(self, file_path: str) -> str:
        """Extract text content from file"""
        
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext == ".pdf" and fitz:
            doc = fitz.open(file_path)
            text = ""
            for page in doc:
                text += page.get_text() + "\n\n"
            doc.close()
            return text
        else:
            # For images or if PyMuPDF not available
            return "Content extracted from uploaded material."
    
    async def _generate_single_script(
        self,
        content: str,
        topic_idx: int,
        max_video_length: int
    ) -> Dict[str, Any]:
        """Generate a single video script"""
        
        if self.gemini_client:
            return await self._ai_generate_script(content, topic_idx, max_video_length)
        else:
            return self._rule_based_script(content, topic_idx, max_video_length)
    
    async def _ai_generate_script(
        self,
        content: str,
        topic_idx: int,
        max_video_length: int
    ) -> Dict[str, Any]:
        """Use AI to generate a detailed video script"""
        
        prompt = f"""You are a script writer for 3Blue1Brown-style educational math videos.
Create a detailed video script based on this content. The video should be engaging, visual, and max {max_video_length} minutes.

Content:
{content[:4000]}

Generate a JSON script with this structure:
{{
    "title": "Video Title",
    "description": "Brief description",
    "total_duration_estimate": 10,
    "chapters": [
        {{
            "id": "chapter_1",
            "title": "Chapter Title",
            "duration_estimate": 3,
            "narration": "The full narration text for this chapter. Write it in a conversational, engaging style like Grant Sanderson. Explain concepts intuitively.",
            "animations": [
                {{
                    "type": "text",
                    "content": "Title text to display",
                    "style": "title"
                }},
                {{
                    "type": "equation",
                    "latex": "e^{{i\\pi}} + 1 = 0",
                    "animation": "write"
                }},
                {{
                    "type": "graph",
                    "function": "sin(x)",
                    "range": [-3.14, 3.14]
                }},
                {{
                    "type": "shape",
                    "shape": "circle",
                    "action": "transform_to_square"
                }},
                {{
                    "type": "numberline",
                    "range": [0, 10],
                    "highlight": [2, 5]
                }}
            ]
        }}
    ]
}}

Animation types: text, equation, graph, shape, numberline, vector, matrix, code, diagram
Make the narration natural and the animations sync logically with what's being explained.
Return ONLY valid JSON, no markdown formatting.
"""

        try:
            import asyncio
            response = await asyncio.to_thread(
                self.gemini_client.models.generate_content,
                model="gemini-3-flash-preview",
                contents=prompt
            )
            
            # Parse JSON from response
            response_text = response.text.strip()
            # Remove markdown code blocks if present
            if response_text.startswith("```"):
                import re
                response_text = re.sub(r'^```\w*\n?', '', response_text)
                response_text = re.sub(r'\n?```$', '', response_text)
            
            return json.loads(response_text)
        except Exception as e:
            print(f"AI script generation failed: {e}")
            return self._rule_based_script(content, topic_idx, max_video_length)
    
    def _rule_based_script(
        self,
        content: str,
        topic_idx: int,
        max_video_length: int
    ) -> Dict[str, Any]:
        """Generate a basic script using rules"""
        
        # Extract key elements from content
        equations = self._extract_equations(content)
        key_terms = self._extract_key_terms(content)
        
        # Build script structure
        chapters = []
        
        # Introduction chapter
        chapters.append({
            "id": "intro",
            "title": "Introduction",
            "duration_estimate": 2,
            "narration": f"Welcome to this exploration of mathematical concepts. Today, we'll be diving into some fascinating ideas that connect various areas of mathematics. Let's start by building our intuition.",
            "animations": [
                {"type": "text", "content": "Mathematical Exploration", "style": "title"},
                {"type": "text", "content": "Building Intuition", "style": "subtitle"}
            ]
        })
        
        # Core concept chapters
        if equations:
            eq_chapter = {
                "id": "equations",
                "title": "Key Equations",
                "duration_estimate": 5,
                "narration": "Let's look at the fundamental equations that govern these ideas. Each equation tells a story about how different quantities relate to each other.",
                "animations": []
            }
            
            for i, eq in enumerate(equations[:5]):
                eq_chapter["animations"].append({
                    "type": "equation",
                    "latex": eq,
                    "animation": "write"
                })
            
            chapters.append(eq_chapter)
        
        # Visual chapter
        chapters.append({
            "id": "visual",
            "title": "Visual Understanding",
            "duration_estimate": 4,
            "narration": "Now let's see these concepts come to life through visual representations. Watch how the shapes and graphs evolve to illustrate these relationships.",
            "animations": [
                {"type": "graph", "function": "x**2", "range": [-3, 3]},
                {"type": "shape", "shape": "circle", "action": "create"},
                {"type": "numberline", "range": [-5, 5], "highlight": [0, 3]}
            ]
        })
        
        # Conclusion
        chapters.append({
            "id": "conclusion",
            "title": "Wrapping Up",
            "duration_estimate": 2,
            "narration": "And that brings us to the end of our exploration. These mathematical ideas are powerful tools that help us understand the world around us. Keep exploring, and remember - the beauty of math is in the connections we discover.",
            "animations": [
                {"type": "text", "content": "Thank you for watching!", "style": "title"}
            ]
        })
        
        total_duration = sum(ch["duration_estimate"] for ch in chapters)
        
        return {
            "title": f"Mathematical Exploration - Part {topic_idx + 1}",
            "description": "An intuitive journey through mathematical concepts",
            "total_duration_estimate": total_duration,
            "chapters": chapters
        }
    
    def _extract_equations(self, content: str) -> List[str]:
        """Extract mathematical equations from content"""
        
        patterns = [
            r'\$\$(.+?)\$\$',  # Display math
            r'\$(.+?)\$',      # Inline math
            r'\\begin\{equation\}(.+?)\\end\{equation\}',
            r'([a-zA-Z]\s*=\s*[^,\n]{3,30})',  # Simple equations like x = 2y + 3
        ]
        
        equations = []
        for pattern in patterns:
            matches = re.findall(pattern, content, re.DOTALL)
            equations.extend(matches)
        
        # Clean up and deduplicate
        cleaned = []
        seen = set()
        for eq in equations:
            eq = eq.strip()
            if eq and eq not in seen and len(eq) < 100:
                seen.add(eq)
                cleaned.append(eq)
        
        return cleaned[:10]  # Limit to 10 equations
    
    def _extract_key_terms(self, content: str) -> List[str]:
        """Extract key mathematical terms"""
        
        math_terms = [
            "function", "derivative", "integral", "limit", "series",
            "matrix", "vector", "eigenvalue", "determinant", "polynomial",
            "equation", "theorem", "proof", "lemma", "corollary",
            "set", "group", "ring", "field", "space",
            "continuous", "differentiable", "convergent", "bounded"
        ]
        
        content_lower = content.lower()
        found_terms = [term for term in math_terms if term in content_lower]
        
        return found_terms
