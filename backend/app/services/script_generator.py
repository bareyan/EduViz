"""
Script Generator V2 - Uses Gemini to create detailed video scripts
Each script has sections with narration, timing, and visual descriptions
"""

import os
import json
import asyncio
from typing import List, Dict, Any, Optional

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

# Cost tracking
from app.services.manim_generator.cost_tracker import CostTracker

# Model configuration
from app.config.models import get_model_config, get_thinking_config


class ScriptGenerator:
    """Generates detailed video scripts using Gemini AI
    
    Uses a TWO-PHASE approach:
    Phase 1: Generate a detailed pedagogical outline covering ALL material
    Phase 2: Generate the COMPLETE script in ONE call using the outline
    
    This ensures:
    - Complete coverage of all content (via outline)
    - Natural flow without repetition (single script generation)
    - Full context throughout (model sees all previous sections)
    - Deep explanations with intuition, motivation, and examples
    """
    
    # Model configuration - loaded from centralized config
    _script_config = get_model_config("script_generation")
    _lang_detect_config = get_model_config("language_detection")
    
    MODEL = _script_config.model_name
    LANGUAGE_DETECTION_MODEL = _lang_detect_config.model_name
    
    # Target segment duration for audio (in seconds) - ~10-12 seconds for good sync
    TARGET_SEGMENT_DURATION = 12
    # Speaking rate for estimation: ~150 words/min = 2.5 words/sec, ~5 chars/word = 12.5 chars/sec
    CHARS_PER_SECOND = 12.5
    
    def __init__(self, cost_tracker: Optional[CostTracker] = None):
        self.client = None
        self.cost_tracker = cost_tracker or CostTracker()
        api_key = os.getenv("GEMINI_API_KEY")
        if genai and api_key:
            self.client = genai.Client(api_key=api_key)
        else:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        
        # Generation config from centralized configuration
        thinking_config = get_thinking_config(self._script_config)
        if types and thinking_config:
            self.generation_config = types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(
                    thinking_level=thinking_config["thinking_level"],
                ),
            )
        else:
            self.generation_config = None
    
    async def generate_script(
        self,
        file_path: str,
        topic: Dict[str, Any],
        max_duration_minutes: int = 20,
        video_mode: str = "comprehensive",  # "comprehensive" or "overview"
        language: str = "en",  # Language code for content generation
        content_focus: str = "as_document",  # "practice", "theory", or "as_document"
        document_context: str = "auto"  # "standalone", "series", or "auto"
    ) -> Dict[str, Any]:
        """Generate a detailed video script for a topic
        
        Args:
            file_path: Path to the source file
            topic: Topic data with title, description, etc.
            max_duration_minutes: Maximum duration hint (ignored for comprehensive mode)
            video_mode: "comprehensive" for full detailed videos, "overview" for quick summaries
            language: Language code for content generation (en, fr, "auto" to use document language)
            content_focus: Content emphasis - "practice" for more examples, "theory" for more proofs/derivations
            document_context: Document context - "standalone" (explain all concepts), "series" (assume prior knowledge), "auto" (AI decides)
        
        Returns:
            Script dictionary with sections
        """
        
        # Extract content from file
        content = await self._extract_content(file_path)
        
        # Detect document language first
        detected_language = await self._detect_language(content[:5000])
        
        # Generate the script using Gemini
        script = await self._gemini_generate_script(content, topic, max_duration_minutes, video_mode, language, detected_language, content_focus, document_context)
        
        # Add video_mode and language metadata
        script["video_mode"] = video_mode
        script["source_language"] = detected_language  # Original document language
        script["language"] = script.get("output_language", language)  # Output language
        
        # Add cost tracking summary
        script["cost_summary"] = self.cost_tracker.get_summary()
        
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
                model=self.LANGUAGE_DETECTION_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=10,
                )
            )
            
            # Track cost for language detection
            self.cost_tracker.track_usage(response, self.LANGUAGE_DETECTION_MODEL)
            
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
        detected_language: str = "en",
        content_focus: str = "as_document",
        document_context: str = "auto"
    ) -> Dict[str, Any]:
        """Use Gemini to generate a complete video script using TWO-PHASE approach:
        
        Phase 1: Generate detailed pedagogical outline covering ALL material
        Phase 2: Generate the COMPLETE script in ONE call using the outline
        
        This ensures complete coverage while maintaining natural flow.
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
        
        # Determine output language
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
        
        # Estimate content length
        content_length = len(content)
        estimated_duration = topic.get('estimated_duration', 20)
        
        if video_mode == "overview":
            suggested_duration = min(7, max(3, estimated_duration // 3))
            section_guidance = "3-6 sections, 30-60 seconds each"
            teaching_style = "brief"
        else:
            # COMPREHENSIVE MODE: Full lecture-style videos
            suggested_duration = max(45, content_length // 80)
            section_guidance = "as many sections as needed - create sections for EVERY topic, theorem, proof, example"
            teaching_style = "comprehensive"
        
        # Build content focus instructions
        if content_focus == "practice":
            focus_instructions = """
CONTENT FOCUS: PRACTICE-ORIENTED
- Prioritize examples over abstract theory
- For every concept, include 2-3 worked examples
- Show step-by-step problem solving
- Focus on "how to apply" rather than "why it works"
"""
        elif content_focus == "theory":
            focus_instructions = """
CONTENT FOCUS: THEORY-ORIENTED  
- Prioritize rigorous proofs and formal derivations
- Explore the "why" behind every concept
- Build deep understanding of underlying principles
- Take time with mathematical rigor
"""
        else:  # as_document
            focus_instructions = """
CONTENT FOCUS: FOLLOW DOCUMENT STRUCTURE
- Mirror the document's natural balance of theory and practice
- If the document is example-heavy, be example-heavy
- If the document is proof-focused, be proof-focused
"""
        
        # Build document context instructions
        if document_context == "standalone":
            context_instructions = """
DOCUMENT CONTEXT: STANDALONE CONTENT
- Explain ALL referenced methods/concepts that aren't common knowledge
- Don't assume viewers know specialized techniques
- Make the video self-contained and accessible
"""
        elif document_context == "series":
            context_instructions = """
DOCUMENT CONTEXT: PART OF A SERIES
- You CAN assume prior chapters/lectures have been covered
- Brief reminders of prior concepts are sufficient ("recall that...")
- Focus on NEW material introduced in this part
"""
        else:  # auto
            context_instructions = """
DOCUMENT CONTEXT: AUTO-DETECT
Analyze if this is standalone content or part of a series, and adjust accordingly.
"""
        
        # ═══════════════════════════════════════════════════════════════════════
        # PHASE 1: Generate detailed pedagogical outline
        # ═══════════════════════════════════════════════════════════════════════
        print(f"[ScriptGenerator] PHASE 1: Generating comprehensive outline in {language_name}...")
        
        phase1_prompt = f"""You are an expert university professor planning a COMPREHENSIVE lecture video that provides DEEP UNDERSTANDING.

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
            "estimated_duration_seconds": [60-300]
        }}
    ]
}}"""""

        try:
            phase1_response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.MODEL,
                    contents=phase1_prompt,
                    config=types.GenerateContentConfig(
                        thinking_config=types.ThinkingConfig(thinking_level="LOW"),
                        max_output_tokens=16384,
                    )
                ),
                timeout=300  # 5 minute timeout for outline
            )
            
            # Track cost for Phase 1
            self.cost_tracker.track_usage(phase1_response, self.MODEL)
            
            outline = self._parse_json_response(phase1_response.text)
            sections_outline = outline.get('sections_outline', [])
            print(f"[ScriptGenerator] Phase 1 complete: {len(sections_outline)} sections outlined")
        except Exception as e:
            print(f"[ScriptGenerator] Phase 1 failed: {e}, using fallback")
            # Create a basic outline
            outline = {
                "title": topic.get('title', 'Educational Content'),
                "subject_area": topic.get('subject_area', 'general'),
                "overview": topic.get('description', ''),
                "sections_outline": [
                    {"id": "intro", "title": "Introduction", "section_type": "introduction", "content_to_cover": "Overview of the topic", "key_points": ["Introduction"], "visual_type": "static", "estimated_duration_seconds": 60},
                    {"id": "main", "title": "Main Content", "section_type": "content", "content_to_cover": "Core material", "key_points": ["Main concepts"], "visual_type": "mixed", "estimated_duration_seconds": 300},
                    {"id": "conclusion", "title": "Conclusion", "section_type": "summary", "content_to_cover": "Summary", "key_points": ["Recap"], "visual_type": "static", "estimated_duration_seconds": 60}
                ]
            }
            sections_outline = outline.get('sections_outline', [])
        
        # ═══════════════════════════════════════════════════════════════════════
        # PHASE 2: Generate script sections
        # - OVERVIEW mode: Generate ALL sections in ONE call (faster, simpler)
        # - COMPREHENSIVE mode: Generate sections ONE BY ONE with context (detailed)
        # ═══════════════════════════════════════════════════════════════════════
        
        # Get learning objectives and prerequisites if available
        learning_objectives = outline.get('learning_objectives', [])
        prerequisites = outline.get('prerequisites', [])
        gaps_to_fill = outline.get('document_analysis', {}).get('gaps_to_fill', [])
        
        generated_sections = []
        
        if video_mode == "overview":
            # ═══════════════════════════════════════════════════════════════════
            # OVERVIEW MODE: Generate ALL sections in ONE prompt
            # ═══════════════════════════════════════════════════════════════════
            print(f"[ScriptGenerator] PHASE 2 (OVERVIEW): Generating ALL {len(sections_outline)} sections in one call...")
            
            generated_sections = await self._generate_all_sections_at_once(
                sections_outline=sections_outline,
                full_outline=outline,
                content=content,
                language_name=language_name,
                language_instruction=language_instruction,
                gaps_to_fill=gaps_to_fill,
            )
        else:
            # ═══════════════════════════════════════════════════════════════════
            # COMPREHENSIVE MODE: Generate sections ONE BY ONE with full context
            # ═══════════════════════════════════════════════════════════════════
            print(f"[ScriptGenerator] PHASE 2 (COMPREHENSIVE): Generating script section-by-section ({len(sections_outline)} sections) in {language_name}...")
            
            for section_idx, section_outline in enumerate(sections_outline):
                print(f"[ScriptGenerator] Generating section {section_idx + 1}/{len(sections_outline)}: {section_outline.get('title', 'Untitled')}...")
                
                section = await self._generate_single_section(
                    section_outline=section_outline,
                    section_idx=section_idx,
                    total_sections=len(sections_outline),
                    full_outline=outline,
                    previous_sections=generated_sections,
                    content=content,
                    language_name=language_name,
                    language_instruction=language_instruction,
                    gaps_to_fill=gaps_to_fill,
                )
                
                if section:
                    generated_sections.append(section)
                else:
                    # Fallback section if generation failed
                    generated_sections.append({
                        "id": section_outline.get("id", f"section_{section_idx}"),
                        "title": section_outline.get("title", f"Part {section_idx + 1}"),
                        "narration": f"Let's explore {section_outline.get('title', 'this topic')}.",
                        "tts_narration": f"Let's explore {section_outline.get('title', 'this topic')}.",
                    })
        
        # Build final script
        script = {
            "title": outline.get('title', topic.get('title', 'Educational Content')),
            "subject_area": outline.get('subject_area', 'general'),
            "overview": outline.get('overview', ''),
            "learning_objectives": learning_objectives,
            "sections": generated_sections,
        }
        
        # Calculate actual durations from narration lengths
        for section in script.get('sections', []):
            narration_len = len(section.get('narration', ''))
            section['duration_seconds'] = max(30, int(narration_len / self.CHARS_PER_SECOND))
        
        script['total_duration_seconds'] = sum(s.get('duration_seconds', 60) for s in script.get('sections', []))
        
        print(f"[ScriptGenerator] Phase 2 complete: {len(script.get('sections', []))} sections, ~{script['total_duration_seconds'] // 60} minutes")
        
        # Add document analysis from phase 1
        script['document_analysis'] = outline.get('document_analysis', {})
        
        # Validate and fix the script structure
        script = self._validate_script(script, topic)
        
        # Segment narration into ~10 second audio chunks for TTS
        print(f"[ScriptGenerator] Segmenting narration for audio sync...")
        script = self._segment_narrations(script)
        
        # Add language metadata
        script["output_language"] = output_language
        script["source_language"] = detected_language
        
        # Log cost summary
        self.cost_tracker.print_summary()
        
        return script
    
    def get_cost_tracker(self) -> CostTracker:
        """Get the cost tracker for this generator"""
        return self.cost_tracker
    
    async def _generate_single_section(
        self,
        section_outline: Dict[str, Any],
        section_idx: int,
        total_sections: int,
        full_outline: Dict[str, Any],
        previous_sections: List[Dict[str, Any]],
        content: str,
        language_name: str,
        language_instruction: str,
        gaps_to_fill: List[str],
    ) -> Optional[Dict[str, Any]]:
        """Generate a single section with full context of the outline and previous sections."""
        
        # Build context from previous sections - keep it concise to avoid token limits
        previous_sections_context = ""
        if previous_sections:
            prev_summaries = []
            for i, prev in enumerate(previous_sections):
                # Only include last 2 sections in detail, older ones get brief summary
                if i >= len(previous_sections) - 2:
                    # Recent sections: include narration ending for continuity
                    narration = prev.get('narration', '')
                    # Limit to last 500 chars to save tokens
                    narration_excerpt = narration[-500:] if len(narration) > 500 else narration
                    prev_summaries.append(f"[{i+1}] {prev.get('title', 'Untitled')}: ...{narration_excerpt}")
                else:
                    # Older sections: just title and key concepts
                    concepts = prev.get('key_concepts', [])[:3]
                    prev_summaries.append(f"[{i+1}] {prev.get('title', 'Untitled')} - covered: {', '.join(concepts)}")
            previous_sections_context = "\n".join(prev_summaries)
        
        # Format the full outline (very condensed)
        outline_summary = []
        for i, sec in enumerate(full_outline.get('sections_outline', [])):
            marker = ">>>" if i == section_idx else ("✓" if i < section_idx else " ")
            outline_summary.append(f"{marker} {i+1}. {sec.get('title', 'Untitled')}")
        outline_text = "\n".join(outline_summary)
        
        # Position-specific instructions (condensed)
        if section_idx == 0:
            position_note = "FIRST SECTION: Start with engaging hook, may greet viewer."
        elif section_idx == total_sections - 1:
            position_note = "FINAL SECTION: Summarize key insights, memorable conclusion."
        else:
            position_note = f"MIDDLE SECTION {section_idx + 1}/{total_sections}: Continue naturally, no greetings, reference earlier content."
        
        # Limit content size based on section - use relevant portion
        content_limit = 25000  # Reduced from 40000
        content_excerpt = content[:content_limit]
        
        # Build a more concise prompt - ONLY generate narration, not visual scripts
        prompt = f"""Generate narration for ONE lecture section. Focus ONLY on what to SAY.

SECTION: {section_outline.get('title', 'Untitled')}
TYPE: {section_outline.get('section_type', 'content')}
CONTENT TO COVER: {section_outline.get('content_to_cover', '')}
KEY POINTS: {json.dumps(section_outline.get('key_points', []))}

{position_note}
{language_instruction}

LECTURE OUTLINE:
{outline_text}

PREVIOUS SECTIONS (for continuity):
{previous_sections_context if previous_sections_context else "(First section)"}

DEPTH REQUIREMENTS:
- Explain the WHY, not just the WHAT
- For definitions: motivation → intuition → formal statement → example
- For theorems: importance → statement → proof strategy → steps → reinforcement  
- For proofs: reasoning behind each step, key insights
- Be thorough - no length limits

SOURCE MATERIAL:
{content_excerpt}

OUTPUT: Valid JSON only, no markdown. Generate ONLY narration text:
{{"id": "{section_outline.get('id', f'section_{section_idx}')}",
"title": "{section_outline.get('title', f'Part {section_idx + 1}')}",
"narration": "Complete spoken narration for this section...",
"tts_narration": "Same narration with math symbols spelled out (e.g., 'theta' not 'θ', 'x squared' not 'x²')..."}}"""

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        thinking_config=types.ThinkingConfig(thinking_level="LOW"),
                        max_output_tokens=8192,  # Reduced for reliability
                    )
                ),
                timeout=120  # 2 minute timeout per section
            )
            
            # Track cost
            self.cost_tracker.track_usage(response, self.MODEL)
            
            # Debug: check response
            if not response or not hasattr(response, 'text'):
                print(f"[ScriptGenerator] Section {section_idx + 1}: Empty response object")
                return None
            
            response_text = response.text
            if not response_text or not response_text.strip():
                print(f"[ScriptGenerator] Section {section_idx + 1}: Empty response text")
                # Check for safety/block reasons
                if hasattr(response, 'candidates') and response.candidates:
                    candidate = response.candidates[0]
                    if hasattr(candidate, 'finish_reason'):
                        print(f"[ScriptGenerator] Finish reason: {candidate.finish_reason}")
                    if hasattr(candidate, 'safety_ratings'):
                        print(f"[ScriptGenerator] Safety ratings: {candidate.safety_ratings}")
                return None
            
            print(f"[ScriptGenerator] Section {section_idx + 1}: Got {len(response_text)} chars response")
            
            section = self._parse_json_response(response_text)
            
            # Check if parse returned default (failed)
            if section.get('title') == 'Mathematical Exploration':
                print(f"[ScriptGenerator] Section {section_idx + 1}: JSON parse failed, response preview: {response_text[:300]}")
                return None
            
            # Ensure required fields
            section["id"] = section.get("id", section_outline.get("id", f"section_{section_idx}"))
            section["title"] = section.get("title", section_outline.get("title", f"Part {section_idx + 1}"))
            
            return section
            
        except asyncio.TimeoutError:
            print(f"[ScriptGenerator] Section {section_idx + 1}: Timeout after 120s")
            return None
        except Exception as e:
            print(f"[ScriptGenerator] Section {section_idx + 1} failed: {type(e).__name__}: {e}")
            return None

    async def _generate_all_sections_at_once(
        self,
        sections_outline: List[Dict[str, Any]],
        full_outline: Dict[str, Any],
        content: str,
        language_name: str,
        language_instruction: str,
        gaps_to_fill: List[str],
    ) -> List[Dict[str, Any]]:
        """Generate ALL sections in a single prompt for overview mode.
        
        This is faster and more efficient for short overview videos where
        we want concise, connected sections without the overhead of
        generating each section separately.
        """
        
        # Build sections outline summary
        sections_summary = []
        for i, sec in enumerate(sections_outline):
            sections_summary.append(
                f"{i + 1}. [{sec.get('id', f'section_{i}')}] {sec.get('title', f'Part {i+1}')}: "
                f"{sec.get('content_to_cover', 'Cover this topic')}"
            )
        sections_summary_str = "\n".join(sections_summary)
        
        # Limit content for overview mode
        content_excerpt = content[:8000] if len(content) > 8000 else content
        
        # Build learning objectives string
        objectives_str = "\n".join(f"- {obj}" for obj in full_outline.get('learning_objectives', []))
        if not objectives_str:
            objectives_str = "- Understand the key concepts from the material"
        
        prompt = f"""You are an expert educator creating a CONCISE VIDEO OVERVIEW script.
{language_instruction}

Generate ALL sections for this video in ONE response. Keep each section brief and focused.

OVERVIEW TITLE: {full_outline.get('title', 'Educational Content')}

LEARNING OBJECTIVES:
{objectives_str}

SECTIONS TO GENERATE:
{sections_summary_str}

SOURCE MATERIAL:
{content_excerpt}

IMPORTANT - OVERVIEW MODE GUIDELINES:
- Keep narrations CONCISE (30-90 seconds per section typically)
- Focus on KEY POINTS only, not exhaustive detail
- Each section should flow naturally into the next
- Use clear, engaging language suitable for a summary video
- Total video should be around {len(sections_outline) * 45} seconds

OUTPUT FORMAT: Valid JSON array with ALL sections:
[
  {{
    "id": "section_id",
    "title": "Section Title",
    "narration": "Complete spoken narration for this section...",
    "tts_narration": "Same narration with math symbols spelled out..."
  }},
  ...
]

Generate the COMPLETE JSON array with ALL {len(sections_outline)} sections:"""

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.MODEL,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        thinking_config=types.ThinkingConfig(thinking_level="LOW"),
                        max_output_tokens=16384,  # Larger for all sections
                    )
                ),
                timeout=180  # 3 minute timeout for all sections
            )
            
            # Track cost
            self.cost_tracker.track_usage(response, self.MODEL)
            
            if not response or not hasattr(response, 'text') or not response.text.strip():
                print(f"[ScriptGenerator] Overview mode: Empty response")
                return self._fallback_sections(sections_outline)
            
            response_text = response.text.strip()
            print(f"[ScriptGenerator] Overview mode: Got {len(response_text)} chars response")
            
            # Parse JSON array
            sections = self._parse_json_array_response(response_text)
            
            if not sections:
                print(f"[ScriptGenerator] Overview mode: JSON parse failed")
                return self._fallback_sections(sections_outline)
            
            # Ensure all sections have required fields
            for i, section in enumerate(sections):
                section["id"] = section.get("id", sections_outline[i].get("id", f"section_{i}") if i < len(sections_outline) else f"section_{i}")
                section["title"] = section.get("title", sections_outline[i].get("title", f"Part {i + 1}") if i < len(sections_outline) else f"Part {i + 1}")
                if not section.get("tts_narration"):
                    section["tts_narration"] = section.get("narration", "")
            
            print(f"[ScriptGenerator] Overview mode complete: {len(sections)} sections generated")
            return sections
            
        except asyncio.TimeoutError:
            print(f"[ScriptGenerator] Overview mode: Timeout after 180s")
            return self._fallback_sections(sections_outline)
        except Exception as e:
            print(f"[ScriptGenerator] Overview mode failed: {type(e).__name__}: {e}")
            return self._fallback_sections(sections_outline)
    
    def _fallback_sections(self, sections_outline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate fallback sections when AI generation fails."""
        return [
            {
                "id": sec.get("id", f"section_{i}"),
                "title": sec.get("title", f"Part {i + 1}"),
                "narration": f"Let's explore {sec.get('title', 'this topic')}.",
                "tts_narration": f"Let's explore {sec.get('title', 'this topic')}.",
            }
            for i, sec in enumerate(sections_outline)
        ]
    
    def _parse_json_array_response(self, text: str) -> List[Dict[str, Any]]:
        """Parse a JSON array response from the model."""
        # Clean markdown code blocks
        if '```json' in text:
            text = text.split('```json')[1].split('```')[0]
        elif '```' in text:
            parts = text.split('```')
            if len(parts) >= 2:
                text = parts[1]
        
        text = text.strip()
        
        try:
            result = json.loads(text)
            if isinstance(result, list):
                return result
            elif isinstance(result, dict) and 'sections' in result:
                return result['sections']
            return []
        except json.JSONDecodeError as e:
            print(f"[ScriptGenerator] JSON array parse error: {e}")
            # Try to find array in text
            try:
                import re
                match = re.search(r'\[[\s\S]*\]', text)
                if match:
                    return json.loads(match.group(0))
            except Exception:
                pass
            return []

    def _segment_narrations(self, script: Dict[str, Any]) -> Dict[str, Any]:
        """Segment each section's narration into ~10 second audio chunks
        
        This creates the 'narration_segments' field for each section, which
        will be used to:
        1. Generate audio files for each segment
        2. Get actual audio durations
        3. Pass timing info to Gemini for video generation
        
        Each segment is designed to be ~10 seconds for good audio-video sync.
        Segments only contain: text, estimated_duration, segment_index
        """
        import re
        
        for section in script.get("sections", []):
            narration = section.get("tts_narration") or section.get("narration", "")
            if not narration:
                section["narration_segments"] = []
                continue
            
            segments = self._split_narration_into_segments(narration)
            # Segments only need: text, estimated_duration, segment_index
            # Visual descriptions are NOT duplicated here - handled at render time
            
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
        
        # Ensure each section has required fields (minimal set)
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
            # Remove legacy fields that are no longer needed
            # visual_description, key_concepts, animation_type are handled by Manim generator
        
        # Calculate total duration
        script["total_duration_seconds"] = sum(s["duration_seconds"] for s in script["sections"])
        
        return script
    
    def _default_script(self) -> Dict[str, Any]:
        """Return a default script structure - minimal fields only"""
        return {
            "title": "Mathematical Exploration",
            "total_duration_seconds": 300,
            "sections": [
                {
                    "id": "intro",
                    "title": "Introduction",
                    "duration_seconds": 30,
                    "narration": "Welcome! Today we're going to explore a fascinating mathematical concept.",
                    "tts_narration": "Welcome! Today we're going to explore a fascinating mathematical concept.",
                },
                {
                    "id": "main",
                    "title": "Main Concept",
                    "duration_seconds": 180,
                    "narration": "Let's dive into the core idea and build our intuition step by step.",
                    "tts_narration": "Let's dive into the core idea and build our intuition step by step.",
                },
                {
                    "id": "conclusion",
                    "title": "Conclusion",
                    "duration_seconds": 30,
                    "narration": "And that's the beautiful idea at the heart of this topic. Thanks for watching!",
                    "tts_narration": "And that's the beautiful idea at the heart of this topic. Thanks for watching!",
                }
            ]
        }
