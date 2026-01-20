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
    
    MODEL = "gemini-3-flash-preview"  # Stable flash model for fast generation
    
    # Target segment duration for audio (in seconds) - ~10-12 seconds for good sync
    TARGET_SEGMENT_DURATION = 12
    # Speaking rate for estimation: ~150 words/min = 2.5 words/sec, ~5 chars/word = 12.5 chars/sec
    CHARS_PER_SECOND = 12.5
    
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
            language: Language code for content generation (en, fr, "auto" to use document language)
        
        Returns:
            Script dictionary with sections
        """
        
        # Extract content from file
        content = await self._extract_content(file_path)
        
        # Detect document language first
        detected_language = await self._detect_language(content[:5000])
        
        # Generate the script using Gemini
        script = await self._gemini_generate_script(content, topic, max_duration_minutes, video_mode, language, detected_language)
        
        # Add video_mode and language metadata
        script["video_mode"] = video_mode
        script["source_language"] = detected_language  # Original document language
        script["language"] = script.get("output_language", language)  # Output language
        
        return script
    
    async def _detect_language(self, text_sample: str) -> str:
        """Detect the language of the document using Gemini"""
        if not self.client or not text_sample.strip():
            return "en"  # Default to English
        
        try:
            prompt = f"""Analyze this text and identify its primary language.
Respond with ONLY a 2-letter ISO 639-1 language code (e.g., en, fr, es, de, zh, ja, ko, ru, ar, hy).
If the text contains multiple languages, identify the primary/dominant one.
If unsure, respond with "en".

TEXT SAMPLE:
{text_sample[:2000]}

LANGUAGE CODE:"""
            
            response = self.client.models.generate_content(
                model="gemini-flash-lite-latest",  # Use fast/cheap model for detection
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=10,
                )
            )
            
            detected = response.text.strip().lower()[:2]
            
            # Validate it's a known language code
            valid_codes = ["en", "fr", "es", "de", "it", "pt", "zh", "ja", "ko", "ar", "ru", "hy"]
            if detected in valid_codes:
                print(f"[ScriptGenerator] Detected document language: {detected}")
                return detected
            else:
                print(f"[ScriptGenerator] Unknown language code '{detected}', defaulting to 'en'")
                return "en"
                
        except Exception as e:
            print(f"[ScriptGenerator] Language detection failed: {e}, defaulting to 'en'")
            return "en"
    
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
        language: str = "auto",
        detected_language: str = "en"
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
            "hy": "Armenian",
        }
        
        # Use detected language from caller (already detected earlier)
        # The 'language' parameter represents the OUTPUT language
        # If language == "auto" or matches detected, use document language
        if language == "auto" or language == detected_language:
            output_language = detected_language
        else:
            output_language = language
        
        language_name = language_names.get(output_language, "English")
        detected_language_name = language_names.get(detected_language, "English")
        
        # Only add translation instruction if output differs from source
        if output_language != detected_language:
            language_instruction = f"\n\nIMPORTANT: The source material is in {detected_language_name}. Generate ALL narration text in {language_name}. Translate content accurately while maintaining educational clarity."
        else:
            language_instruction = f"\n\nGenerate all narration in {language_name} (the document's original language)."
        
        # Estimate content length to determine appropriate video length
        content_length = len(content)
        estimated_duration = topic.get('estimated_duration', 20)
        
        if video_mode == "overview":
            suggested_duration = min(7, max(3, estimated_duration // 3))
            section_count = "3-6 sections"
            section_duration = "30-60 seconds each"
            teaching_style = "brief"
        else:
            # COMPREHENSIVE MODE: Much longer, more thorough videos for teaching
            # More generous estimation: ~200 chars per minute of video (slower, more explanatory)
            suggested_duration = max(45, estimated_duration * 2, content_length // 200)
            # Cap at reasonable max for very long documents
            suggested_duration = min(suggested_duration, 90)
            section_count = "as many sections as needed to cover ALL material thoroughly"
            section_duration = "60-180 seconds each (adjust based on content complexity)"
            teaching_style = "comprehensive"
        
        # ═══════════════════════════════════════════════════════════════════════
        # PHASE 1: Generate overall plan/outline from document
        # ═══════════════════════════════════════════════════════════════════════
        print(f"[ScriptGenerator] PHASE 1: Generating overall plan in {language_name}...")
        
        # Build teaching-style specific instructions
        if teaching_style == "comprehensive":
            teaching_instructions = f"""
=== ADAPTIVE LECTURE STYLE ===

First, ANALYZE the document to determine the best teaching approach:

DOCUMENT ANALYSIS (do this first):
1. What TYPE of content is this?
   - Theoretical concepts (proofs, theorems, abstract ideas)
   - Practical/procedural (how-to, algorithms, techniques)
   - Factual/descriptive (definitions, properties, classifications)
   - Problem-solving (worked examples, case studies)
   - Conceptual overview (survey, introduction to a field)
   
2. What is the COMPLEXITY level?
   - Introductory (new concepts, needs extensive motivation)
   - Intermediate (builds on prior knowledge)
   - Advanced (assumes background, focus on nuances)

3. What TEACHING APPROACH fits best?
   Choose ONE or combine as appropriate:
   
   A) CONCEPT-FIRST: For abstract/theoretical content
      - Start with the big idea and intuition
      - Build to formal definitions
      - Use analogies heavily
      
   B) EXAMPLE-DRIVEN: For procedural/problem-solving content
      - Lead with concrete examples
      - Extract patterns and rules from examples
      - "Here's what we want to do... let me show you how"
      
   C) COMPARISON-BASED: For content with alternatives/trade-offs
      - Side-by-side analysis
      - Pros/cons, when to use what
      - "On one hand... on the other hand..."
      
   D) STORY/JOURNEY: For historical or evolution-type content
      - Narrative arc with progression
      - "This led to... which made people realize..."
      
   E) PROBLEM-SOLUTION: For applied content
      - Start with the problem/need
      - Show why naive approaches fail
      - Present the solution and why it works

CORE TEACHING PRINCIPLES (apply regardless of approach):

1. MOTIVATE: Why should the viewer care? What can they DO with this?
2. INTUITION: Before formulas, explain the IDEA in plain language
3. DEPTH: Take time to explain - don't rush through complex material
4. EXAMPLES: Concrete illustrations make abstract ideas click
5. CONNECTIONS: Show how ideas relate to each other

STRUCTURE YOUR LECTURE:
- Opening hook that captures interest
- Logical flow that builds understanding
- Each section should have a clear teaching goal
- Pace based on complexity - harder topics get more time

TARGET: {suggested_duration}+ minutes. This is a FLOOR, not a ceiling.
Take as much time as the material genuinely needs.
"""
        else:
            teaching_instructions = """
OVERVIEW MODE - Quick summary focusing on key takeaways only.
"""
        
        phase1_prompt = f"""You are an expert university professor planning a lecture video.

Analyze this source material and create a LECTURE OUTLINE for an educational video.
DO NOT write the full script yet - just the structure and what each section will teach.{language_instruction}
{teaching_instructions}

TOPIC: {topic.get('title', 'Educational Content')}
DESCRIPTION: {topic.get('description', '')}
SUBJECT AREA: {topic.get('subject_area', 'general')}
VIDEO MODE: {video_mode.upper()}
TARGET DURATION: {suggested_duration} minutes minimum (longer if the material requires it)
TARGET SECTIONS: {section_count}, {section_duration}
OUTPUT LANGUAGE: {language_name}

SOURCE MATERIAL:
{content[:50000]}

FIRST: Analyze the document and decide on the teaching approach.
THEN: Create a lecture outline based on your analysis.

VISUAL TYPE GUIDANCE:
- "animated": Dynamic concepts - equations building, graphs plotting, processes unfolding
- "static": Definitions, key statements, summary points
- "mixed": Animated elements with static labels
- "diagram": Flowcharts, concept maps, relationship diagrams
- "graph": Data plots, function graphs, statistical visualizations
- "comparison": Side-by-side visuals showing differences

Respond with ONLY valid JSON:
{{
    "document_analysis": {{
        "content_type": "[theoretical|practical|factual|problem-solving|conceptual-overview]",
        "complexity_level": "[introductory|intermediate|advanced]",
        "chosen_approach": "[concept-first|example-driven|comparison-based|story-journey|problem-solution]",
        "approach_rationale": "[Why this approach fits this document]"
    }},
    "title": "[Video title - engaging and descriptive]",
    "subject_area": "[math|cs|physics|economics|biology|engineering|general]",
    "total_duration_minutes": {suggested_duration},
    "overview": "[2-3 sentence hook that makes viewers want to watch]",
    "sections_outline": [
        {{
            "id": "[unique_id]",
            "title": "[Section title]",
            "teaching_goal": "[What the viewer will UNDERSTAND after this section]",
            "key_points": ["point1", "point2", "point3"],
            "teaching_method": "[How this section teaches - matches chosen approach]",
            "visual_type": "[animated|static|mixed|diagram|graph|comparison]",
            "duration_seconds": [estimated duration - be generous for complex topics],
            "source_content": "[What source material this covers]"
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
                timeout=600  # 10 minute timeout for comprehensive phase 1 outline
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
        
        # Build teaching-style specific Phase 2 instructions
        # Include the document analysis from Phase 1 to guide narration style
        document_analysis = outline.get('document_analysis', {})
        chosen_approach = document_analysis.get('chosen_approach', 'concept-first')
        content_type = document_analysis.get('content_type', 'theoretical')
        
        if teaching_style == "comprehensive":
            # Approach-specific narration guidance
            approach_guidance = {
                'concept-first': """
CONCEPT-FIRST APPROACH:
- Lead with the big idea and intuition before details
- Use analogies to make abstract ideas concrete
- Pattern: Intuition → Formal definition → Why it matters
- "Think of it like..." / "The key insight is..."
""",
                'example-driven': """
EXAMPLE-DRIVEN APPROACH:
- Start with concrete examples, extract patterns
- Show the "how" before the "why"
- Pattern: Example → Pattern → General rule
- "Let me show you..." / "Notice what happens when..."
""",
                'comparison-based': """
COMPARISON-BASED APPROACH:
- Present alternatives side by side
- Highlight trade-offs and when to use each
- Pattern: Option A → Option B → When to choose
- "On one hand... on the other hand..." / "Unlike X, Y does..."
""",
                'story-journey': """
STORY/JOURNEY APPROACH:
- Follow a narrative arc with progression
- Build suspense and resolution
- Pattern: Problem → Evolution → Solution
- "This led to..." / "People realized that..."
""",
                'problem-solution': """
PROBLEM-SOLUTION APPROACH:
- Start with the problem/need
- Show why simple approaches fail
- Pattern: Problem → Failed attempts → Real solution
- "We need to..." / "The naive approach fails because..."
"""
            }
            
            phase2_teaching = f"""
=== WRITING NARRATION FOR: {content_type.upper()} CONTENT ===
Using approach: {chosen_approach.upper()}

{approach_guidance.get(chosen_approach, approach_guidance['concept-first'])}

UNIVERSAL PRINCIPLES:

1. DEPTH OVER BREADTH
   - Explain things thoroughly, don't rush
   - It's better to explain one concept deeply than skim many
   - Take 20-30 seconds per key idea if needed

2. CONVERSATIONAL TONE
   - "Now, this might seem strange at first..."
   - "Here's the beautiful part..."
   - "I know this is a lot, so let's pause..."

3. PACING
   - Use "..." for short pauses
   - Use "[PAUSE]" after key insights
   - Give time for visuals to be absorbed

4. ENGAGEMENT
   - "Think about what this means..."
   - "Try to predict what happens next..."
   - "Notice how this connects to..."

5. CLEAR STRUCTURE
   - Each section should have a clear teaching goal
   - Transitions between sections should be smooth
   - Viewers should know where they are in the journey
"""
        else:
            phase2_teaching = "Write concise narration covering key points."
        
        phase2_prompt = f"""You are a script writer for educational videos. You have an OUTLINE and need to write the FULL SCRIPT.{language_instruction}
{phase2_teaching}

VIDEO OUTLINE:
{sections_outline_str}

ORIGINAL SOURCE MATERIAL (for reference - include ALL of this in your narration):
{content[:40000]}

OUTPUT LANGUAGE: {language_name}
ALL NARRATION MUST BE IN {language_name.upper()}.

For each section in the outline, write:
1. Full narration text in {language_name} - cover ALL content from source plus explanations
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
            "duration_seconds": [realistic duration based on narration length],
            "narration": "[Complete narration covering all source content plus explanations]",
            "tts_narration": "[TTS-friendly version - same content, symbols spelled out]",
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
                timeout=900  # 15 minute timeout for comprehensive phase 2 detailed sections
            )
            script = self._parse_json_response(phase2_response.text)
            print(f"[ScriptGenerator] Phase 2 complete: {len(script.get('sections', []))} detailed sections")
        except Exception as e:
            print(f"[ScriptGenerator] Phase 2 failed: {e}")
            # Convert outline to basic script
            script = self._outline_to_script(outline, topic)
        
        # Validate and fix the script structure
        script = self._validate_script(script, topic)
        
        # ═══════════════════════════════════════════════════════════════════════
        # PHASE 3: Segment narration into ~10 second audio chunks
        # ═══════════════════════════════════════════════════════════════════════
        print(f"[ScriptGenerator] PHASE 3: Segmenting narration for audio sync...")
        script = self._segment_narrations(script)
        
        # Add language metadata
        script["output_language"] = output_language
        script["source_language"] = detected_language
        
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
            "hy": "Armenian",
        }
        language_name = language_names.get(language, "English")
        language_instruction = f"\n\nIMPORTANT: Generate ALL narration text in {language_name}." if language != "en" else ""
        
        content_length = len(content)
        estimated_duration = topic.get('estimated_duration', 20)
        
        if video_mode == "overview":
            suggested_duration = min(7, max(3, estimated_duration // 3))
            mode_instructions = "Create a SHORT summary (3-7 minutes), 3-6 sections, 30-60 seconds each."
        else:
            # COMPREHENSIVE MODE: Full lecture-style coverage
            suggested_duration = max(30, estimated_duration * 2, content_length // 250)
            suggested_duration = min(suggested_duration, 90)
            mode_instructions = f"""Create an ADAPTIVE LECTURE style video (target: {suggested_duration}+ minutes).

FIRST, analyze the document:
- Content type: theoretical, practical, factual, problem-solving, or overview?
- Choose the best approach: concept-first, example-driven, comparison-based, story, or problem-solution

THEN, write the script using your chosen approach:

APPROACH OPTIONS:
- CONCEPT-FIRST: Lead with big idea → intuition → formal definition
- EXAMPLE-DRIVEN: Show examples → extract patterns → generalize
- COMPARISON-BASED: Present alternatives → pros/cons → when to use
- STORY/JOURNEY: Problem → evolution → solution narrative
- PROBLEM-SOLUTION: Need → failed attempts → real solution

UNIVERSAL PRINCIPLES:
1. DEPTH: Take time to explain thoroughly - don't rush
2. INTUITION: Before formulas, explain the IDEA in plain language
3. ENGAGEMENT: "Think about..." / "Notice how..."
4. PACING: Use [PAUSE] after key insights

This duration is a FLOOR, not a ceiling. Take as long as needed."""
        
        prompt = f"""Create a detailed video script for educational content.{language_instruction}

{mode_instructions}

TOPIC: {topic.get('title', 'Educational Content')}
OUTPUT LANGUAGE: {language_name}
SOURCE MATERIAL (cover ALL of this): {content[:45000]}

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
            "duration_seconds": [duration based on content complexity],
            "narration": "[Complete narration covering source content plus explanations]",
            "tts_narration": "[spoken version in {language_name} - symbols spelled out]",
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
    
    def _segment_narrations(self, script: Dict[str, Any]) -> Dict[str, Any]:
        """Segment each section's narration into ~10 second audio chunks
        
        This creates the 'narration_segments' field for each section, which
        will be used to:
        1. Generate audio files for each segment
        2. Get actual audio durations
        3. Pass timing info to Gemini for video generation
        
        Each segment is designed to be ~10 seconds for good audio-video sync.
        """
        import re
        
        for section in script.get("sections", []):
            narration = section.get("tts_narration") or section.get("narration", "")
            if not narration:
                section["narration_segments"] = []
                continue
            
            segments = self._split_narration_into_segments(narration)
            section["narration_segments"] = segments
            
            # Update estimated duration based on segments
            total_estimated = sum(seg["estimated_duration"] for seg in segments)
            section["duration_seconds"] = max(section.get("duration_seconds", 30), total_estimated)
            
            print(f"[ScriptGenerator] Section '{section.get('title', 'Untitled')}': {len(segments)} segments, ~{total_estimated:.1f}s")
        
        # Update total duration
        script["total_duration_seconds"] = sum(s["duration_seconds"] for s in script.get("sections", []))
        
        return script
    
    def _split_narration_into_segments(self, narration: str) -> List[Dict[str, Any]]:
        """Split narration into ~10 second segments at natural breakpoints
        
        Uses sentence boundaries and pause markers to find optimal split points.
        
        Returns:
            List of segment dicts with:
            - text: The narration text for this segment
            - estimated_duration: Estimated duration in seconds
            - segment_index: Index of this segment
        """
        import re
        
        if not narration or len(narration) < 50:
            # Very short narration - single segment
            estimated = len(narration) / self.CHARS_PER_SECOND
            return [{
                "text": narration,
                "estimated_duration": max(3.0, estimated),
                "segment_index": 0
            }]
        
        # Target ~12 seconds per segment for good sync
        target_chars = self.TARGET_SEGMENT_DURATION * self.CHARS_PER_SECOND  # ~150 chars
        max_chars = target_chars * 1.5  # ~225 chars max before forcing split
        
        # Split into sentences first (respecting pause markers)
        # Priority split points: [PAUSE] > sentence endings (. ! ?) > semicolons > commas
        
        # First, split on [PAUSE] markers (these are explicit long pauses)
        pause_parts = re.split(r'\[PAUSE\]', narration)
        
        segments = []
        current_text = []
        current_chars = 0
        
        for part_idx, part in enumerate(pause_parts):
            # Split each part into sentences
            sentences = re.split(r'(?<=[.!?])\s+', part.strip())
            sentences = [s.strip() for s in sentences if s.strip()]
            
            for sentence in sentences:
                sentence_len = len(sentence)
                
                # Check if adding this sentence would exceed max duration
                if current_chars + sentence_len > max_chars and current_text:
                    # Save current segment
                    segment_text = " ".join(current_text)
                    estimated = len(segment_text) / self.CHARS_PER_SECOND
                    segments.append({
                        "text": segment_text,
                        "estimated_duration": estimated,
                        "segment_index": len(segments)
                    })
                    current_text = [sentence]
                    current_chars = sentence_len
                elif current_chars + sentence_len > target_chars and current_text:
                    # At target duration - good split point
                    segment_text = " ".join(current_text)
                    estimated = len(segment_text) / self.CHARS_PER_SECOND
                    segments.append({
                        "text": segment_text,
                        "estimated_duration": estimated,
                        "segment_index": len(segments)
                    })
                    current_text = [sentence]
                    current_chars = sentence_len
                else:
                    current_text.append(sentence)
                    current_chars += sentence_len + 1  # +1 for space
            
            # If there was a [PAUSE] marker between parts, consider it a good break point
            if part_idx < len(pause_parts) - 1 and current_text:
                # Force a segment break at [PAUSE]
                segment_text = " ".join(current_text)
                estimated = len(segment_text) / self.CHARS_PER_SECOND
                segments.append({
                    "text": segment_text,
                    "estimated_duration": estimated,
                    "segment_index": len(segments)
                })
                current_text = []
                current_chars = 0
        
        # Don't forget the last segment
        if current_text:
            segment_text = " ".join(current_text)
            estimated = len(segment_text) / self.CHARS_PER_SECOND
            segments.append({
                "text": segment_text,
                "estimated_duration": estimated,
                "segment_index": len(segments)
            })
        
        # Ensure minimum segment duration (at least 3 seconds)
        # Merge very short segments with adjacent ones
        merged_segments = []
        for seg in segments:
            if seg["estimated_duration"] < 3.0 and merged_segments:
                # Merge with previous segment
                prev = merged_segments[-1]
                prev["text"] += " " + seg["text"]
                prev["estimated_duration"] = len(prev["text"]) / self.CHARS_PER_SECOND
            else:
                merged_segments.append(seg)
        
        # Re-index segments after merging
        for i, seg in enumerate(merged_segments):
            seg["segment_index"] = i
        
        return merged_segments
    
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
