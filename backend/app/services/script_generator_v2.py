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
        max_duration_minutes: int = 20,
        video_mode: str = "comprehensive",  # "comprehensive" or "overview"
        language: str = "en"  # Language code for content generation
    ) -> Dict[str, Any]:
        """Generate a detailed video script for a topic
        
        Args:
            file_path: Path to the source file
            topic: Topic data with title, description, etc.
            max_duration_minutes: Maximum duration hint (ignored for comprehensive mode)
            video_mode: "comprehensive" for full detailed videos, "overview" for quick summaries
            language: Language code for content generation (en, fr, etc.)
        
        Returns:
            Script dictionary with sections
        """
        
        # Extract content from file
        content = await self._extract_content(file_path)
        
        # Generate the script using Gemini
        script = await self._gemini_generate_script(content, topic, max_duration_minutes, video_mode, language)
        
        # Add video_mode and language to script metadata
        script["video_mode"] = video_mode
        script["language"] = language
        
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
        max_duration: int,
        video_mode: str = "comprehensive",
        language: str = "en"
    ) -> Dict[str, Any]:
        """Use Gemini to generate a complete video script using TWO-PHASE approach:
        Phase 1: Generate overall plan/outline from document
        Phase 2: Generate detailed sections from the plan
        """
        
        # Language name mapping for prompts
        language_names = {
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
        }
        language_name = language_names.get(language, "English")
        language_instruction = f"\n\nIMPORTANT: Generate ALL narration text in {language_name}. The source material may be in any language, but the output narration MUST be in {language_name}." if language != "en" else ""
        
        # Estimate content length to determine appropriate video length
        content_length = len(content)
        estimated_duration = topic.get('estimated_duration', 20)
        
        if video_mode == "overview":
            suggested_duration = min(7, max(3, estimated_duration // 3))
            section_count = "3-6 sections"
            section_duration = "30-60 seconds each"
        else:
            suggested_duration = max(20, estimated_duration, content_length // 400)
            section_count = "10-30+ sections"
            section_duration = "60-180 seconds each"
        
        # ═══════════════════════════════════════════════════════════════════════
        # PHASE 1: Generate overall plan/outline from document
        # ═══════════════════════════════════════════════════════════════════════
        print(f"[ScriptGenerator] PHASE 1: Generating overall plan in {language_name}...")
        
        phase1_prompt = f"""You are an expert educator analyzing content to create a video lecture plan.

Analyze this source material and create a HIGH-LEVEL OUTLINE for an educational video.
DO NOT write the full script yet - just the structure and key points for each section.{language_instruction}

TOPIC: {topic.get('title', 'Educational Content')}
DESCRIPTION: {topic.get('description', '')}
SUBJECT AREA: {topic.get('subject_area', 'general')}
VIDEO MODE: {video_mode.upper()}
TARGET DURATION: {suggested_duration} minutes
TARGET SECTIONS: {section_count}, {section_duration}
OUTPUT LANGUAGE: {language_name}

SOURCE MATERIAL:
{content[:40000]}

Create an outline that:
1. Follows the NATURAL FLOW of the source material
2. Identifies KEY CONCEPTS that need explanation
3. Notes which parts need ANIMATION vs STATIC visuals
4. Estimates duration for each section
5. All titles and key_points MUST be in {language_name}

VISUAL TYPE GUIDANCE:
- "animated": Complex concepts that benefit from step-by-step animation (equations transforming, algorithms running, diagrams building)
- "static": Explanatory text, definitions, simple concepts where a still image with narration works better
- "mixed": Some animation with static portions

Respond with ONLY valid JSON:
{{
    "title": "[Video title]",
    "subject_area": "[math|cs|physics|economics|biology|engineering|general]",
    "total_duration_minutes": {suggested_duration},
    "overview": "[2-3 sentence summary of what the video will cover]",
    "sections_outline": [
        {{
            "id": "[unique_id]",
            "title": "[Section title]",
            "key_points": ["point1", "point2", "point3"],
            "visual_type": "[animated|static|mixed]",
            "duration_seconds": [estimated duration],
            "purpose": "[What this section accomplishes]"
        }}
    ]
}}"""

        try:
            phase1_response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.MODEL,
                    contents=phase1_prompt
                ),
                timeout=300  # 5 minute timeout for phase 1 outline
            )
            outline = self._parse_json_response(phase1_response.text)
            print(f"[ScriptGenerator] Phase 1 complete: {len(outline.get('sections_outline', []))} sections outlined")
        except Exception as e:
            print(f"[ScriptGenerator] Phase 1 failed: {e}, falling back to single-phase")
            return await self._gemini_generate_script_single_phase(content, topic, max_duration, video_mode, language)
        
        # ═══════════════════════════════════════════════════════════════════════
        # PHASE 2: Generate detailed sections from the plan
        # ═══════════════════════════════════════════════════════════════════════
        print(f"[ScriptGenerator] PHASE 2: Generating detailed sections in {language_name}...")
        
        sections_outline_str = json.dumps(outline.get('sections_outline', []), indent=2)
        
        phase2_prompt = f"""You are a script writer for educational videos. You have an OUTLINE and need to write the FULL SCRIPT.{language_instruction}

VIDEO OUTLINE:
{sections_outline_str}

ORIGINAL SOURCE MATERIAL (for reference):
{content[:25000]}

OUTPUT LANGUAGE: {language_name}
ALL NARRATION MUST BE IN {language_name.upper()}.

For each section in the outline, write:
1. Full narration text in {language_name} (what the narrator says)
2. TTS-friendly version in {language_name} (no symbols, spelled out)
3. Visual description (what appears on screen)
4. Animation type

VISUAL TYPES - IMPORTANT:
- For "static" sections: Describe TEXT/IMAGES that appear on screen while narrator explains
- For "animated" sections: Describe step-by-step ANIMATIONS that build up
- For "mixed" sections: Combine both approaches

STATIC SCENE EXAMPLES:
- "Display title 'Key Definition' with bullet points appearing one by one"
- "Show a diagram of [X] that stays on screen while narrator explains"
- "Display the formula [Y] centered on screen"

ANIMATED SCENE EXAMPLES:
- "Animate the equation transforming step by step"
- "Build the graph point by point, drawing the curve"
- "Show the algorithm executing with highlighted steps"

TTS-FRIENDLY NARRATION:
- narration: Display version with symbols (x², O(n), α)
- tts_narration: Spoken version ("x squared", "O of n", "alpha")

Respond with ONLY valid JSON:
{{
    "title": "{outline.get('title', topic.get('title', 'Video'))}",
    "subject_area": "{outline.get('subject_area', 'general')}",
    "total_duration_seconds": [sum of all section durations],
    "sections": [
        {{
            "id": "[from outline]",
            "title": "[from outline]",
            "duration_seconds": [from outline],
            "narration": "[Full narration with proper notation, ... for pauses, [PAUSE] for long pauses]",
            "tts_narration": "[TTS-friendly version]",
            "visual_description": "[Detailed visual description]",
            "key_concepts": ["concept1", "concept2"],
            "animation_type": "[static|animated|mixed]",
            "visual_elements": ["element1", "element2"]
        }}
    ]
}}"""

        try:
            phase2_response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.MODEL,
                    contents=phase2_prompt
                ),
                timeout=600  # 10 minute timeout for phase 2 detailed sections
            )
            script = self._parse_json_response(phase2_response.text)
            print(f"[ScriptGenerator] Phase 2 complete: {len(script.get('sections', []))} detailed sections")
        except Exception as e:
            print(f"[ScriptGenerator] Phase 2 failed: {e}")
            # Convert outline to basic script
            script = self._outline_to_script(outline, topic)
        
        # Validate and fix the script structure
        script = self._validate_script(script, topic)
        
        return script
    
    async def _gemini_generate_script_single_phase(
        self,
        content: str,
        topic: Dict[str, Any],
        max_duration: int,
        video_mode: str = "comprehensive",
        language: str = "en"
    ) -> Dict[str, Any]:
        """Fallback single-phase script generation"""
        
        # Language name mapping for prompts
        language_names = {
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
        }
        language_name = language_names.get(language, "English")
        language_instruction = f"\n\nIMPORTANT: Generate ALL narration text in {language_name}." if language != "en" else ""
        
        content_length = len(content)
        estimated_duration = topic.get('estimated_duration', 20)
        
        if video_mode == "overview":
            suggested_duration = min(7, max(3, estimated_duration // 3))
            mode_instructions = "Create a SHORT summary (3-7 minutes), 3-6 sections, 30-60 seconds each."
        else:
            suggested_duration = max(20, estimated_duration, content_length // 400)
            mode_instructions = "Create a COMPREHENSIVE video (20+ minutes), 10-30+ sections, 60-180 seconds each."
        
        prompt = f"""Create a detailed video script for educational content.{language_instruction}

{mode_instructions}

TOPIC: {topic.get('title', 'Educational Content')}
OUTPUT LANGUAGE: {language_name}
SOURCE MATERIAL: {content[:30000]}

ALL NARRATION MUST BE IN {language_name.upper()}.

ANIMATION TYPES:
- "static": Text/images on screen with narration (use for definitions, simple explanations)
- "animated": Step-by-step animations (use for complex concepts, derivations)
- "mixed": Combination of both

Respond with JSON:
{{
    "title": "[title in {language_name}]",
    "subject_area": "[subject]",
    "total_duration_seconds": [total],
    "sections": [
        {{
            "id": "[id]",
            "title": "[title in {language_name}]",
            "duration_seconds": [duration],
            "narration": "[narration in {language_name} with pauses]",
            "tts_narration": "[spoken version in {language_name}]",
            "visual_description": "[what to show]",
            "key_concepts": ["concepts"],
            "animation_type": "[static|animated|mixed]"
        }}
    ]
}}"""

        response = await asyncio.to_thread(
            self.client.models.generate_content,
            model=self.MODEL,
            contents=prompt
        )
        
        script = self._parse_json_response(response.text)
        script = self._validate_script(script, topic)
        return script
    
    def _outline_to_script(self, outline: Dict[str, Any], topic: Dict[str, Any]) -> Dict[str, Any]:
        """Convert a phase-1 outline to a basic script if phase-2 fails"""
        sections = []
        for section_outline in outline.get('sections_outline', []):
            key_points = section_outline.get('key_points', [])
            narration = f"{section_outline.get('title', 'Section')}. " + ". ".join(key_points)
            
            sections.append({
                "id": section_outline.get('id', f"section_{len(sections)}"),
                "title": section_outline.get('title', 'Section'),
                "duration_seconds": section_outline.get('duration_seconds', 60),
                "narration": narration,
                "tts_narration": narration,
                "visual_description": section_outline.get('purpose', 'Display content'),
                "key_concepts": key_points[:3],
                "animation_type": section_outline.get('visual_type', 'mixed')
            })
        
        return {
            "title": outline.get('title', topic.get('title', 'Video')),
            "subject_area": outline.get('subject_area', 'general'),
            "total_duration_seconds": sum(s['duration_seconds'] for s in sections),
            "sections": sections
        }
    
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
            script["title"] = topic.get("title", "Educational Content")
        
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
                section["visual_description"] = "Show relevant visuals"
            # Support both key_equations (old) and key_concepts (new)
            if "key_equations" not in section and "key_concepts" not in section:
                section["key_concepts"] = []
            elif "key_equations" in section and "key_concepts" not in section:
                section["key_concepts"] = section["key_equations"]
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
