"""
Script Generator V2 - Uses Gemini to create detailed video scripts
Each script has sections with narration, timing, and visual descriptions
"""

import os
import json
import asyncio
from typing import List, Dict, Any

# PDF processing
try:
    import fitz
except ImportError:
    fitz = None

# Gemini
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None


class ScriptGenerator:
    """Generates detailed video scripts using Gemini AI"""
    
    MODEL = "gemini-3-flash-preview"
    
    def __init__(self):
        self.client = None
        api_key = os.getenv("GEMINI_API_KEY")
        if genai and api_key:
            self.client = genai.Client(api_key=api_key)
        else:
            raise ValueError("GEMINI_API_KEY environment variable is required")
    
    async def generate_script(
        self,
        file_path: str,
        topic: Dict[str, Any],
        max_duration_minutes: int = 20
    ) -> Dict[str, Any]:
        """Generate a detailed video script for a topic"""
        
        # Extract content from file
        content = await self._extract_content(file_path)
        
        # Generate the script using Gemini
        script = await self._gemini_generate_script(content, topic, max_duration_minutes)
        
        return script
    
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
        elif ext in [".tex", ".txt"]:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        else:
            return ""
    
    async def _gemini_generate_script(
        self,
        content: str,
        topic: Dict[str, Any],
        max_duration: int
    ) -> Dict[str, Any]:
        """Use Gemini to generate a complete video script"""
        
        # Estimate content length to determine appropriate video length
        # No max limit - video can be as long as needed for comprehensive coverage
        content_length = len(content)
        estimated_duration = topic.get('estimated_duration', 20)
        
        # Scale duration based on content: roughly 1 min per 500 chars of dense math content
        # But at least 15 minutes for comprehensive coverage
        suggested_duration = max(15, estimated_duration, content_length // 500)
        
        prompt = f"""You are a script writer for mathematical lecture videos with Manim-style animations (like 3Blue1Brown).

COMPREHENSIVE VIDEO STYLE:
- Include EVERY definition, theorem, and proof from the source material
- Show complete step-by-step derivations with detailed visual explanations
- Multiple examples with fully worked solutions
- The video should REPLACE reading the source material entirely
- ALWAYS provide INTUITION - explain the "why" behind every concept
- The video can be AS LONG AS NEEDED - do not rush or skip content

CRITICAL CONTENT PHILOSOPHY:
1. INTUITION FIRST: Before any formal definition, explain the intuition and motivation
2. DETAILED EXPLANATIONS: Every step should be explained, never skip reasoning
3. VISUAL CLARITY: For derivations, show each step visually with last 2 steps visible
4. ACADEMIC RIGOR + ACCESSIBILITY: Be precise but also make it understandable
5. BUILD UNDERSTANDING: Each concept should flow naturally to the next
6. PAUSE FOR COMPREHENSION: Give viewers time to process complex ideas
7. NO TIME LIMIT: Take as much time as needed for thorough coverage

NARRATION STYLE:
- Explain the intuition behind every formula and theorem
- Use phrases like "The key insight here is...", "Notice that this means...", "Intuitively, this captures..."
- Connect abstract concepts to concrete understanding
- Include "..." for natural pauses (1-2 seconds)
- Include "[PAUSE]" for longer pauses after complex ideas (3-4 seconds)

TTS-FRIENDLY NARRATION (CRITICAL):
For EACH section, you MUST provide TWO narration fields:
1. "narration": The display version with mathematical notation (e.g., "Consider φ_n = λ²x")
2. "tts_narration": The spoken version for text-to-speech (e.g., "Consider phi sub n equals lambda squared x")

CONVERSION RULES for tts_narration:
- Greek letters: α→"alpha", β→"beta", γ→"gamma", δ→"delta", ε→"epsilon", ζ→"zeta", η→"eta", θ→"theta", λ→"lambda", μ→"mu", ν→"nu", ξ→"xi", π→"pi", ρ→"rho", σ→"sigma", τ→"tau", φ→"phi", χ→"chi", ψ→"psi", ω→"omega", Γ→"capital gamma", Δ→"capital delta", Σ→"capital sigma", Ω→"capital omega"
- Subscripts: x_n→"x sub n", φ_0→"phi sub zero"
- Superscripts: x²→"x squared", x³→"x cubed", x^n→"x to the n"
- Fractions: ∂f/∂x→"partial f over partial x", a/b→"a over b"
- Operators: ∑→"the sum of", ∏→"the product of", ∫→"the integral of", ∂→"partial", ∇→"nabla" or "del", ∞→"infinity"
- Symbols: ≤→"less than or equal to", ≥→"greater than or equal to", ≠→"not equal to", ∈→"in" or "belongs to", ⊂→"is a subset of", →→"approaches" or "maps to"
- Norms/absolute: |x|→"the absolute value of x", ||v||→"the norm of v"
- Sets: ℝ→"the real numbers", ℂ→"the complex numbers", ℕ→"the natural numbers"

TOPIC: {topic.get('title', 'Mathematical Concepts')}
DESCRIPTION: {topic.get('description', '')}
KEY POINTS TO COVER: {topic.get('subtopics', topic.get('key_points', []))}
SUGGESTED DURATION: {suggested_duration} minutes (but can be longer if needed for complete coverage)

SOURCE MATERIAL (include ALL of this in the video):
{content[:30000]}

Generate a detailed script with as many sections as needed to cover everything thoroughly.
For short content: 8-12 sections. For longer content: 15-30+ sections.

Respond with ONLY valid JSON (no markdown code blocks):
{{
    "title": "Complete: [Topic Name]",
    "total_duration_seconds": <calculate based on all section durations>,
    "sections": [
        {{
            "id": "intro",
            "title": "Introduction and Motivation",
            "duration_seconds": 90,
            "narration": "Welcome to this comprehensive exploration of [topic]. ... Before we dive into the formalism, let's build some intuition. ... [Explain why this topic matters and what problem it solves]. ... By the end of this video, you'll have a complete understanding of [main concepts].",
            "tts_narration": "Welcome to this comprehensive exploration of [topic]. Before we dive into the formalism, let's build some intuition. [Explain why this topic matters and what problem it solves]. By the end of this video, you'll have a complete understanding of [main concepts].",
            "visual_description": "Title card fades in. Then show motivating example or visualization that captures the essence of the topic.",
            "key_equations": [],
            "animation_type": "text"
        }},
        {{
            "id": "definition_1", 
            "title": "Formal Definition with λ and φ_n",
            "duration_seconds": 120,
            "narration": "Now we can state the formal definition. ... Let φ_n be the eigenfunction corresponding to eigenvalue λ_n. ... The condition ∫|φ|² dx = 1 ensures normalization. [PAUSE] ... Notice how λ→∞ as n→∞.",
            "tts_narration": "Now we can state the formal definition. Let phi sub n be the eigenfunction corresponding to eigenvalue lambda sub n. The condition, the integral of the absolute value of phi squared d x equals 1, ensures normalization. Notice how lambda approaches infinity as n approaches infinity.",
            "visual_description": "Show definition in a framed box. Highlight each part as it's explained. Show visual representation alongside.",
            "key_equations": ["\\\\phi_n", "\\\\lambda_n", "\\\\int|\\\\phi|^2 dx = 1"],
            "animation_type": "equation"
        }},
        {{
            "id": "theorem_1",
            "title": "Main Theorem and Its Meaning",
            "duration_seconds": 150,
            "narration": "This brings us to the central result. ... Before stating it, let's understand what it's telling us intuitively. ... [Explain intuition]. [PAUSE] ... Now, formally: [state theorem]. ... The beauty of this result is [explain significance]. ... Let's work through the proof step by step.",
            "visual_description": "Build up to theorem with intuitive explanation first, then show formal statement. Highlight the key insight.",
            "key_equations": ["Theorem statement"],
            "animation_type": "theorem"
        }},
        {{
            "id": "proof_1",
            "title": "Proof with Explanation",
            "duration_seconds": 180,
            "narration": "The proof follows a beautiful argument. ... We start by [setup and motivation]. ... The key step is to notice that [insight]. [PAUSE] ... This allows us to write [step]. ... And from here, we can conclude [next step]. ... Each step follows naturally once you see the pattern. [PAUSE] ... And that completes the proof.",
            "visual_description": "Show proof step by step. Keep last 2 steps visible. Highlight connections between steps. Use arrows to show logical flow.",
            "key_equations": ["Step 1", "Step 2", "Step 3", "Conclusion"],
            "animation_type": "proof"
        }},
        {{
            "id": "example_1",
            "title": "Worked Example",
            "duration_seconds": 180,
            "narration": "Let's see this in action with a concrete example. ... Consider [problem setup]. ... The first thing to notice is [observation]. ... Applying what we learned, we get [step 1]. [PAUSE] ... Continuing, [step 2 with explanation]. ... And finally, [conclusion with interpretation of what the answer means].",
            "visual_description": "Problem at top. Work through solution step by step. Show intermediate steps clearly. Highlight the application of each concept.",
            "key_equations": ["Problem", "Step 1", "Step 2", "Answer"],
            "animation_type": "worked_example"
        }}
    ]
}}

CRITICAL REQUIREMENTS:
1. Create as many sections as needed for thorough coverage (8-30+ sections)
2. EVERY section must have detailed narration with intuition and explanation
3. Every equation and theorem from the source must appear with explanation
4. Take as much time as needed - no artificial time limits
5. Individual sections should be 60-180 seconds each
6. The video must be COMPLETE and SELF-CONTAINED - full understanding without the source"""

        # Debug logging
        print(f"[ScriptGenerator] Content length: {len(content)} chars")
        print(f"[ScriptGenerator] Content preview: {content[:500]}..." if content else "[ScriptGenerator] WARNING: No content extracted!")
        print(f"[ScriptGenerator] Topic: {topic}")
        print(f"[ScriptGenerator] Suggested duration: {suggested_duration} minutes")
        
        if not content or len(content) < 50:
            print("[ScriptGenerator] WARNING: Content is empty or too short!")

        response = await asyncio.to_thread(
            self.client.models.generate_content,
            model=self.MODEL,
            contents=prompt
        )
        
        print(f"[ScriptGenerator] Gemini response length: {len(response.text)} chars")
        print(f"[ScriptGenerator] Response preview: {response.text[:500]}...")
        
        script = self._parse_json_response(response.text)
        
        # Validate and fix the script structure
        script = self._validate_script(script, topic)
        
        return script
    
    def _fix_json_escapes(self, text: str) -> str:
        """Fix common JSON escape sequence issues from LLM responses"""
        import re
        
        # Fix invalid escape sequences by escaping lone backslashes
        # This handles cases like \x, \p, etc. that aren't valid JSON escapes
        # Valid JSON escapes: \", \\, \/, \b, \f, \n, \r, \t, \uXXXX
        
        # First, temporarily replace valid escapes
        valid_escapes = {
            '\\"': '<<QUOTE>>',
            '\\\\': '<<BACKSLASH>>',
            '\\/': '<<SLASH>>',
            '\\b': '<<BACKSPACE>>',
            '\\f': '<<FORMFEED>>',
            '\\n': '<<NEWLINE>>',
            '\\r': '<<RETURN>>',
            '\\t': '<<TAB>>',
        }
        
        for old, new in valid_escapes.items():
            text = text.replace(old, new)
        
        # Handle unicode escapes \uXXXX
        text = re.sub(r'\\u([0-9a-fA-F]{4})', r'<<UNICODE_\1>>', text)
        
        # Now escape any remaining backslashes (invalid escapes)
        text = text.replace('\\', '\\\\')
        
        # Restore valid escapes
        for old, new in valid_escapes.items():
            text = text.replace(new, old)
        
        # Restore unicode escapes
        text = re.sub(r'<<UNICODE_([0-9a-fA-F]{4})>>', r'\\u\1', text)
        
        return text
    
    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """Parse JSON from Gemini response"""
        text = text.strip()
        
        # Remove markdown code blocks
        if text.startswith("```"):
            lines = text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines)
        
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            print(f"JSON parse error (first attempt): {e}")
            
            # Try fixing escape sequences
            try:
                fixed_text = self._fix_json_escapes(text)
                print("Attempting parse with fixed escapes...")
                return json.loads(fixed_text)
            except json.JSONDecodeError as e2:
                print(f"JSON parse error (after escape fix): {e2}")
                
                # Last resort: try to extract JSON using regex
                try:
                    import re
                    # Find the outermost JSON object
                    match = re.search(r'\{[\s\S]*\}', text)
                    if match:
                        json_str = match.group(0)
                        fixed_json = self._fix_json_escapes(json_str)
                        return json.loads(fixed_json)
                except Exception as e3:
                    print(f"JSON extraction failed: {e3}")
                
                print(f"Response preview: {text[:500]}")
                return self._default_script()
    
    def _validate_script(self, script: Dict[str, Any], topic: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and fix script structure"""
        
        if "title" not in script:
            script["title"] = topic.get("title", "Math Exploration")
        
        if "sections" not in script or not script["sections"]:
            script["sections"] = self._default_script()["sections"]
        
        # Ensure each section has required fields
        for i, section in enumerate(script["sections"]):
            if "id" not in section:
                section["id"] = f"section_{i}"
            if "title" not in section:
                section["title"] = f"Part {i + 1}"
            if "duration_seconds" not in section:
                section["duration_seconds"] = 60
            if "narration" not in section:
                section["narration"] = "Let's explore this concept..."
            # Fallback: if no tts_narration, use narration (TTS will handle it)
            if "tts_narration" not in section:
                section["tts_narration"] = section["narration"]
            if "visual_description" not in section:
                section["visual_description"] = "Show relevant mathematical visuals"
            if "key_equations" not in section:
                section["key_equations"] = []
            if "animation_type" not in section:
                section["animation_type"] = "text"
        
        # Calculate total duration
        script["total_duration_seconds"] = sum(s["duration_seconds"] for s in script["sections"])
        
        return script
    
    def _default_script(self) -> Dict[str, Any]:
        """Return a default script structure"""
        return {
            "title": "Mathematical Exploration",
            "total_duration_seconds": 300,
            "sections": [
                {
                    "id": "intro",
                    "title": "Introduction",
                    "duration_seconds": 30,
                    "narration": "Welcome! Today we're going to explore a fascinating mathematical concept.",
                    "visual_description": "Show the title text with a gradient background",
                    "key_equations": [],
                    "animation_type": "text"
                },
                {
                    "id": "main",
                    "title": "Main Concept",
                    "duration_seconds": 180,
                    "narration": "Let's dive into the core idea and build our intuition step by step.",
                    "visual_description": "Animate the main mathematical concept with shapes and equations",
                    "key_equations": [],
                    "animation_type": "equation"
                },
                {
                    "id": "conclusion",
                    "title": "Conclusion",
                    "duration_seconds": 30,
                    "narration": "And that's the beautiful idea at the heart of this topic. Thanks for watching!",
                    "visual_description": "Show a summary of key points",
                    "key_equations": [],
                    "animation_type": "text"
                }
            ]
        }
