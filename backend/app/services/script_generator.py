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
    """Generates detailed video scripts using Gemini AI
    
    Uses a multi-phase approach for comprehensive videos:
    Phase 1: Create detailed pedagogical outline covering ALL material
    Phase 2: For EACH section, generate detailed narration (iterative, no content skipped)
    Phase 3: Segment narrations for audio sync
    """
    
    MODEL = "gemini-3-flash-preview"  # Latest flash model for comprehensive generation
    MODEL_OUTLINE = "gemini-3-flash-preview"  # Model for outline generation
    
    # Target segment duration for audio (in seconds) - ~10-12 seconds for good sync
    TARGET_SEGMENT_DURATION = 12
    # Speaking rate for estimation: ~150 words/min = 2.5 words/sec, ~5 chars/word = 12.5 chars/sec
    CHARS_PER_SECOND = 12.5
    
    # Comprehensive mode settings
    MAX_SECTIONS_PER_BATCH = 3  # Generate sections in small batches to avoid output limits
    MIN_SECTION_DURATION = 60  # Minimum seconds per section
    MAX_SECTION_DURATION = 300  # Maximum seconds per section (split if longer)
    
    def __init__(self):
        self.client = None
        api_key = os.getenv("GEMINI_API_KEY")
        if genai and api_key:
            self.client = genai.Client(api_key=api_key)
        else:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        
        # Default generation config with low thinking for faster generation
        self.generation_config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(
                thinking_level="LOW",
            ),
        ) if types else None
    
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
        detected_language: str = "en",
        content_focus: str = "as_document",
        document_context: str = "auto"
    ) -> Dict[str, Any]:
        """Use Gemini to generate a complete video script using MULTI-PHASE approach:
        
        COMPREHENSIVE MODE (iterative, no content skipped):
        Phase 1: Generate detailed pedagogical outline covering ALL material
        Phase 2: For EACH section, generate detailed narration (separate API call per section)
        Phase 3: Segment narrations for audio sync
        
        OVERVIEW MODE (single-phase):
        Generate a brief summary script in one call
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
            # COMPREHENSIVE MODE: Full lecture-style videos that REPLACE reading the document
            # No artificial duration limits - video should be as long as needed
            # Estimate: ~80 chars per minute for VERY thorough explanation with pauses
            suggested_duration = max(45, content_length // 80)
            section_count = "as many sections as needed - create a section for EVERY topic, theorem, proof, example, definition"
            section_duration = "60-300 seconds each (complex proofs/derivations need more time)"
            teaching_style = "comprehensive"
        
        # ═══════════════════════════════════════════════════════════════════════
        # PHASE 1: Generate overall plan/outline from document
        # ═══════════════════════════════════════════════════════════════════════
        print(f"[ScriptGenerator] PHASE 1: Generating overall plan in {language_name}...")
        
        # Build teaching-style specific instructions
        if teaching_style == "comprehensive":
            # Build content focus instructions
            if content_focus == "practice":
                focus_instructions = """
=== CONTENT FOCUS: PRACTICE-ORIENTED ===
EMPHASIS: More worked examples, applications, and hands-on problems.
- Prioritize examples over abstract theory
- For every concept, include at least 2-3 worked examples
- Show step-by-step problem solving
- Include practice exercises with solutions
- Focus on "how to apply" rather than "why it works"
- Still include necessary theory, but quickly move to applications
"""
            elif content_focus == "theory":
                focus_instructions = """
=== CONTENT FOCUS: THEORY-ORIENTED ===
EMPHASIS: More proofs, derivations, and conceptual depth.
- Prioritize rigorous proofs and formal derivations
- Explore the "why" behind every concept
- Include historical context and motivation where relevant
- Build deep understanding of underlying principles
- Examples should illustrate theory, not just demonstrate procedures
- Take time with mathematical rigor and precision
"""
            else:  # as_document
                focus_instructions = """
=== CONTENT FOCUS: FOLLOW DOCUMENT STRUCTURE ===
EMPHASIS: Mirror the document's natural balance of theory and practice.
- Follow the document's structure and emphasis
- If the document is example-heavy, be example-heavy
- If the document is proof-focused, be proof-focused
- Maintain the author's pedagogical choices
"""
            
            # Build document context instructions
            if document_context == "standalone":
                context_instructions = """
=== DOCUMENT CONTEXT: STANDALONE CONTENT ===
This is standalone content (like a research paper, independent article, or self-contained topic).
- Explain ALL referenced methods/concepts that aren't common knowledge
- If the paper mentions a technique like "MLE" or "gradient descent", explain it
- Don't assume viewers know specialized techniques or domain-specific terms
- Provide background context for the topic
- Make the video self-contained and accessible to newcomers
"""
            elif document_context == "series":
                context_instructions = """
=== DOCUMENT CONTEXT: PART OF A SERIES ===
This is part of a series (like a textbook chapter or lecture in a course).
- You CAN assume prior chapters/lectures have been covered
- Technical terms established earlier in the series can be used without full re-explanation
- Brief reminders of prior concepts are sufficient (e.g., "recall that...")
- Focus on NEW material introduced in this part
- Reference prior concepts briefly but don't re-teach them
"""
            else:  # auto
                context_instructions = """
=== DOCUMENT CONTEXT: AUTO-DETECT ===
Analyze the document and determine if it's:
A) STANDALONE CONTENT (e.g., a research paper, independent article, or single topic)
   → Explain ALL referenced methods/concepts that aren't common knowledge
   → Don't assume viewers know specialized techniques
   Signs: Paper/article format, self-contained, cites external works, 
   introduces topic from scratch, aimed at general audience

B) PART OF A SERIES (e.g., chapter 5 of a textbook, lecture notes building on prior lectures)
   → You can assume prior chapters/lectures have been covered
   → Focus on NEW material, referencing prior concepts briefly
   Signs: Chapter numbering, references to "last lecture", 
   builds directly on prior material, uses notation from earlier without definition
"""
            
            teaching_instructions = f"""
═══════════════════════════════════════════════════════════════════════════════
                    COMPREHENSIVE LECTURE MODE
═══════════════════════════════════════════════════════════════════════════════

YOUR GOAL: Create a COMPLETE university-quality lecture that REPLACES reading the document.
A student who watches this video should understand EVERYTHING without ever reading the source.

{focus_instructions}

{context_instructions}

═══════════════════════════════════════════════════════════════════════════════
                    PEDAGOGICAL STRUCTURE REQUIREMENTS
═══════════════════════════════════════════════════════════════════════════════

CREATE SECTIONS FOR EACH OF THESE (as applicable):

1. INTRODUCTION SECTION (~60-120s)
   - Hook: Why should viewers care about this topic?
   - Overview: What will we learn?
   - Prerequisites: Brief reminder of what viewers should already know
   
2. FOR EACH DEFINITION in the document:
   - State the definition formally
   - Explain what it means in plain language
   - Give the intuition: "Think of it as..."
   - Show examples and non-examples
   
3. FOR EACH THEOREM/LEMMA/PROPOSITION:
   - State the result formally
   - Explain what it means and why we care
   - PROVE IT COMPLETELY (separate section if proof is long):
     * State the proof strategy: "Here's how we'll prove this..."
     * Each step explained: what we're doing AND why
     * Key insights highlighted: "This is the clever part..."
     * NO skipping steps or "similarly..."
   - Show applications/corollaries
   
4. FOR EACH EXAMPLE in the document:
   - Set up the problem
   - Work through EVERY step
   - Explain the reasoning at each step
   - Summarize the technique used
   
5. FOR EACH ALGORITHM/PROCEDURE:
   - Explain the high-level idea
   - Walk through step-by-step
   - Trace through a concrete example
   - Discuss edge cases and complexity
   
6. SUMMARY SECTION (~60-90s)
   - Recap key definitions
   - Recap key theorems
   - Connect ideas together
   - What comes next / how this connects to other topics

═══════════════════════════════════════════════════════════════════════════════
                    COMPLETENESS REQUIREMENTS
═══════════════════════════════════════════════════════════════════════════════

- EVERY theorem, lemma, proposition, corollary → dedicated coverage
- EVERY proof → complete step-by-step explanation
- EVERY definition → explanation with intuition
- EVERY example → fully worked through
- EVERY derivation → all steps shown
- NO skipping, NO "similarly...", NO "it's easy to see..."
- NO rushing through content

═══════════════════════════════════════════════════════════════════════════════
                    TEACHING APPROACH
═══════════════════════════════════════════════════════════════════════════════

Analyze the document and choose the best approach:
- CONCEPT-FIRST: For abstract/theoretical → intuition before formalism
- EXAMPLE-DRIVEN: For procedural → examples before theory
- PROOF-FOCUSED: For theorem-heavy → careful proof presentation
- PROBLEM-SOLUTION: For applied → problem drives the exposition

TARGET DURATION: {suggested_duration}+ minutes - this is a MINIMUM, not a limit.
Take as much time as the material genuinely requires.
A 10-page paper might need 45-90 minutes of video.
"""
        else:
            teaching_instructions = """
OVERVIEW MODE - Quick summary focusing on key takeaways only.
"""
        
        phase1_prompt = f"""You are an expert university professor planning a comprehensive lecture video.

Your task: Create a DETAILED PEDAGOGICAL OUTLINE that ensures COMPLETE coverage of the source material.
This outline will be used to generate detailed narration for each section in a subsequent step.

DO NOT write the full script yet - create a thorough structure that captures EVERY piece of content.{language_instruction}
{teaching_instructions}

═══════════════════════════════════════════════════════════════════════════════
TOPIC: {topic.get('title', 'Educational Content')}
DESCRIPTION: {topic.get('description', '')}
SUBJECT AREA: {topic.get('subject_area', 'general')}
VIDEO MODE: {video_mode.upper()} - COMPLETE COVERAGE REQUIRED
CONTENT FOCUS: {content_focus.upper()}
DOCUMENT CONTEXT: {document_context.upper()}
TARGET DURATION: {suggested_duration} minutes MINIMUM (longer is fine if material requires it)
OUTPUT LANGUAGE: {language_name}
═══════════════════════════════════════════════════════════════════════════════

OUTLINE REQUIREMENTS:

1. COMPLETE COVERAGE - Create sections for EVERYTHING in the document:
   • Each definition gets coverage (can be combined with related concepts)
   • Each theorem/lemma/proposition gets its own section OR a section for proof
   • Each proof gets COMPLETE step-by-step coverage
   • Each example gets fully worked through
   • Each key concept gets explained with motivation

2. GRANULARITY:
   • Break large topics into multiple sections (60-180 seconds each)
   • Complex proofs should be split across multiple sections if needed
   • Better to have MORE sections than to cram content

3. FOR EACH SECTION, specify:
   • source_content_verbatim: Copy the EXACT relevant source text (definitions, theorems, proofs)
   • teaching_goal: What the viewer will understand
   • content_checklist: List EVERY item from source that MUST be covered
   • subsections: For complex sections, break into numbered steps

SOURCE MATERIAL (scan ALL of this - nothing should be omitted from outline):
{content[:60000]}

VISUAL TYPE OPTIONS:
- "animated": Equations building step-by-step, graphs drawing, processes unfolding
- "static": Definitions, statements, summary cards
- "mixed": Animated proofs with static theorem statements
- "diagram": Flowcharts, concept maps, hierarchies
- "graph": Function plots, data visualization
- "comparison": Side-by-side contrasts

Respond with ONLY valid JSON:
{{
    "document_analysis": {{
        "content_type": "[theoretical|practical|factual|problem-solving|mixed]",
        "content_context": "[standalone|part-of-series]",
        "context_rationale": "[Evidence for your classification]",
        "concepts_to_explain": ["Specialized concepts requiring explanation"],
        "assumed_prior_knowledge": ["Prior knowledge if part of series"],
        "total_theorems": [count of theorems/lemmas/propositions],
        "total_proofs": [count of proofs],
        "total_definitions": [count of definitions],
        "total_examples": [count of examples],
        "complexity_level": "[introductory|intermediate|advanced]",
        "chosen_approach": "[concept-first|example-driven|proof-focused|problem-solution]",
        "approach_rationale": "[Why this approach]"
    }},
    "title": "[Engaging video title in {language_name}]",
    "subject_area": "[math|cs|physics|economics|biology|engineering|general]",
    "total_duration_minutes": [realistic estimate based on content],
    "overview": "[2-3 sentence hook]",
    "content_coverage_checklist": [
        "List of EVERY theorem/definition/example/proof that MUST be covered",
        "Use this to verify no content is skipped"
    ],
    "sections_outline": [
        {{
            "id": "[unique_id like 'intro', 'def_1', 'thm_1', 'proof_1', 'example_1']",
            "title": "[Section title in {language_name}]",
            "section_type": "[introduction|definition|theorem|proof|example|application|summary|transition]",
            "teaching_goal": "[What viewer will UNDERSTAND after this section]",
            "source_content_verbatim": "[EXACT text from source document this section covers - copy it here]",
            "content_checklist": ["Item 1 to cover", "Item 2 to cover", "Step 3 of proof", ...],
            "key_points": ["Main point 1", "Main point 2"],
            "teaching_method": "[How to teach this - intuition first? definition first?]",
            "visual_type": "[animated|static|mixed|diagram|graph|comparison]",
            "duration_seconds": [60-180 typically, up to 300 for complex proofs],
            "prerequisites": ["section_ids this section depends on"],
            "subsections": [
                {{
                    "step": 1,
                    "description": "[e.g., 'State the theorem formally']"
                }},
                {{
                    "step": 2, 
                    "description": "[e.g., 'Explain why we care about this']"
                }}
            ]
        }}
    ]
}}"""

        try:
            phase1_response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.MODEL,
                    contents=phase1_prompt,
                    config=self.generation_config
                ),
                timeout=600  # 10 minute timeout for comprehensive phase 1 outline
            )
            outline = self._parse_json_response(phase1_response.text)
            print(f"[ScriptGenerator] Phase 1 complete: {len(outline.get('sections_outline', []))} sections outlined")
        except Exception as e:
            print(f"[ScriptGenerator] Phase 1 failed: {e}, falling back to single-phase")
            return await self._gemini_generate_script_single_phase(content, topic, max_duration, video_mode, language)
        
        # ═══════════════════════════════════════════════════════════════════════
        # PHASE 2: Generate detailed sections ITERATIVELY (one by one)
        # This ensures NO content is skipped due to output length limits
        # ═══════════════════════════════════════════════════════════════════════
        sections_outline = outline.get('sections_outline', [])
        total_sections = len(sections_outline)
        print(f"[ScriptGenerator] PHASE 2: Generating {total_sections} detailed sections ITERATIVELY in {language_name}...")
        
        # Build teaching-style specific Phase 2 instructions
        document_analysis = outline.get('document_analysis', {})
        chosen_approach = document_analysis.get('chosen_approach', 'concept-first')
        content_type = document_analysis.get('content_type', 'theoretical')
        
        # Extract content context from outline analysis
        content_context = document_analysis.get("content_context", "standalone")
        concepts_to_explain = document_analysis.get("concepts_to_explain", [])
        
        # Build context-aware instructions
        if content_context == "standalone" and concepts_to_explain:
            context_instruction = f"""
CONTENT CONTEXT: This is STANDALONE content.
Specialized concepts that may need explanation: {', '.join(concepts_to_explain[:10])}
"""
        elif content_context == "part-of-series":
            assumed_knowledge = document_analysis.get("assumed_prior_knowledge", [])
            context_instruction = f"CONTENT CONTEXT: Part of a series. Prior knowledge assumed: {', '.join(assumed_knowledge) if assumed_knowledge else 'earlier material'}."
        else:
            context_instruction = ""
        
        # Section type specific instructions
        section_type_instructions = {
            'introduction': """
INTRODUCTION SECTION REQUIREMENTS:
- Open with a compelling hook that grabs attention
- Clearly state what the viewer will learn
- Provide motivation: why is this topic important/interesting?
- Brief roadmap of what's coming
""",
            'definition': """
DEFINITION SECTION REQUIREMENTS:
- State the formal definition precisely
- Explain each part of the definition in plain language
- Provide intuition: "Think of it as..." or "This captures the idea that..."
- Give examples that satisfy the definition
- Give non-examples that violate it
- Connect to previously covered concepts
""",
            'theorem': """
THEOREM SECTION REQUIREMENTS:
- State the theorem formally and completely
- Explain what the theorem says in plain language
- Explain WHY we care about this result
- Discuss the conditions/hypotheses and why they matter
- If not proving in this section, preview the proof strategy
""",
            'proof': """
PROOF SECTION REQUIREMENTS:
- State what we're proving (reference the theorem)
- Explain the proof STRATEGY before diving in: "Here's our approach..."
- Go through EVERY step, explaining:
  * What we're doing at each step
  * WHY this step is valid
  * How it brings us closer to the goal
- Highlight key insights: "This is the clever part..."
- NO skipping steps, NO "it's easy to verify", NO "by a similar argument"
- Conclude by connecting back to the theorem statement
""",
            'example': """
EXAMPLE SECTION REQUIREMENTS:
- State the problem/example clearly
- Work through EVERY step of the solution
- Explain the reasoning at each step
- Show intermediate calculations
- Summarize the technique used
- Connect back to the general concept/theorem
""",
            'application': """
APPLICATION SECTION REQUIREMENTS:
- Describe the real-world context or application
- Show how the theory applies
- Work through concrete calculations
- Discuss practical implications
""",
            'summary': """
SUMMARY SECTION REQUIREMENTS:
- Recap the key definitions introduced
- Recap the main theorems and their significance
- Connect the ideas together: how do they relate?
- Preview what comes next or how this connects to other topics
"""
        }
        
        # Generate each section individually
        detailed_sections = []
        
        for idx, section_outline in enumerate(sections_outline):
            section_id = section_outline.get('id', f'section_{idx}')
            section_title = section_outline.get('title', f'Section {idx + 1}')
            section_type = section_outline.get('section_type', 'content')
            
            print(f"[ScriptGenerator] Generating section {idx + 1}/{total_sections}: {section_title} ({section_type})")
            
            # Get source content for this specific section
            source_content_for_section = section_outline.get('source_content_verbatim', '')
            if not source_content_for_section:
                source_content_for_section = section_outline.get('source_content', '')
            
            # Build the checklist for this section
            content_checklist = section_outline.get('content_checklist', section_outline.get('key_points', []))
            subsections = section_outline.get('subsections', [])
            
            # Get previous section for context/transition
            prev_section_summary = ""
            if idx > 0 and detailed_sections:
                prev = detailed_sections[-1]
                prev_section_summary = f"\nPREVIOUS SECTION: '{prev.get('title', '')}' ended with: ...{prev.get('narration', '')[-300:]}"
            
            # Get section-specific instructions
            type_specific_instructions = section_type_instructions.get(
                section_type, 
                "\nCover all content thoroughly with clear explanations."
            )
            
            # Calculate target word count based on duration
            target_duration = section_outline.get('duration_seconds', 120)
            # ~150 words per minute = 2.5 words per second
            target_words = int(target_duration * 2.5)
            
            section_prompt = f"""Generate COMPLETE, DETAILED narration for ONE section of an educational video.{language_instruction}

═══════════════════════════════════════════════════════════════════════════════
SECTION {idx + 1} OF {total_sections}: {section_title}
═══════════════════════════════════════════════════════════════════════════════

Section Type: {section_type.upper()}
Teaching Goal: {section_outline.get('teaching_goal', 'Explain the concept thoroughly')}
Teaching Method: {section_outline.get('teaching_method', chosen_approach)}
Target Duration: {target_duration} seconds (~{target_words} words of narration)
Visual Type: {section_outline.get('visual_type', 'mixed')}
{context_instruction}
{prev_section_summary}

{type_specific_instructions}

═══════════════════════════════════════════════════════════════════════════════
CONTENT CHECKLIST (MUST cover ALL of these):
═══════════════════════════════════════════════════════════════════════════════
{chr(10).join(f"□ {item}" for item in content_checklist) if content_checklist else "□ Cover all concepts in the source content below"}

{("SUBSECTION STRUCTURE TO FOLLOW:" + chr(10) + chr(10).join(f"Step {s.get('step', i+1)}: {s.get('description', '')}" for i, s in enumerate(subsections))) if subsections else ""}

═══════════════════════════════════════════════════════════════════════════════
SOURCE CONTENT FOR THIS SECTION:
═══════════════════════════════════════════════════════════════════════════════
{source_content_for_section if source_content_for_section else "(See full document context below)"}

FULL DOCUMENT CONTEXT (for reference - use to understand broader context):
{content[:25000]}

═══════════════════════════════════════════════════════════════════════════════
NARRATION REQUIREMENTS:
═══════════════════════════════════════════════════════════════════════════════

1. LENGTH: Aim for ~{target_words} words to fill {target_duration} seconds
2. COMPLETENESS: Cover EVERY item in the content checklist above
3. DEPTH: Explain the "why" behind every step, not just the "what"
4. PACING: 
   - Use "..." for brief pauses (1-2 seconds)
   - Use "[PAUSE]" for longer pauses after key insights (3-4 seconds)
   - Don't rush - let ideas sink in
5. CLARITY:
   - Define terms before using them
   - Use analogies to make abstract ideas concrete
   - Connect new ideas to what was covered before
6. ENGAGEMENT:
   - Use conversational, enthusiastic tone
   - "Here's the key insight..."
   - "Notice how this connects to..."
   - "This might seem strange at first, but..."
7. TRANSITIONS:
   - Smooth flow from previous section (if not first)
   - Hint at what's coming next (if not last)

OUTPUT LANGUAGE: {language_name}

Respond with ONLY valid JSON (no markdown code blocks):
{{
    "id": "{section_id}",
    "title": "{section_title}",
    "section_type": "{section_type}",
    "duration_seconds": {target_duration},
    "narration": "[COMPLETE, THOROUGH narration covering ALL checklist items. Target ~{target_words} words. Be comprehensive and pedagogical.]",
    "tts_narration": "[TTS-friendly version - spell out ALL symbols: 'x squared' not 'x²', 'integral from a to b' not '∫', 'pi' not 'π', 'greater than or equal to' not '≥']",
    "visual_description": "[Detailed description of what to show on screen at each moment]",
    "key_concepts": ["list", "of", "key", "concepts", "covered"],
    "animation_type": "{section_outline.get('visual_type', 'mixed')}",
    "visual_elements": ["list", "of", "visual", "elements"],
    "covered_items": ["COPY each item from the content checklist that you covered"],
    "transition_to_next": "[1-2 sentences hinting at what comes in the next section]"
}}"""
            
            try:
                section_response = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.client.models.generate_content,
                        model=self.MODEL,
                        contents=section_prompt,
                        config=self.generation_config
                    ),
                    timeout=300  # 5 minute timeout per section
                )
                section_data = self._parse_json_response(section_response.text)
                
                # Ensure required fields
                section_data['id'] = section_data.get('id', section_id)
                section_data['title'] = section_data.get('title', section_title)
                
                detailed_sections.append(section_data)
                print(f"[ScriptGenerator] ✓ Section {idx + 1} complete: ~{section_data.get('duration_seconds', 60)}s, {len(section_data.get('narration', ''))} chars")
                
            except Exception as e:
                print(f"[ScriptGenerator] ⚠ Section {idx + 1} failed: {e}, using outline fallback")
                # Create basic section from outline
                fallback_section = {
                    'id': section_id,
                    'title': section_title,
                    'section_type': section_outline.get('section_type', 'content'),
                    'duration_seconds': section_outline.get('duration_seconds', 60),
                    'narration': f"{section_title}. " + ". ".join(section_outline.get('key_points', ['Let us explore this concept.'])),
                    'tts_narration': f"{section_title}. " + ". ".join(section_outline.get('key_points', ['Let us explore this concept.'])),
                    'visual_description': section_outline.get('teaching_goal', 'Display relevant visuals'),
                    'key_concepts': section_outline.get('key_points', [])[:3],
                    'animation_type': section_outline.get('visual_type', 'mixed'),
                    'visual_elements': []
                }
                detailed_sections.append(fallback_section)
        
        # Construct the final script
        script = {
            'title': outline.get('title', topic.get('title', 'Educational Video')),
            'subject_area': outline.get('subject_area', 'general'),
            'overview': outline.get('overview', ''),
            'document_analysis': document_analysis,
            'content_coverage_checklist': outline.get('content_coverage_checklist', []),
            'total_duration_seconds': sum(s.get('duration_seconds', 60) for s in detailed_sections),
            'sections': detailed_sections
        }
        
        print(f"[ScriptGenerator] Phase 2 complete: {len(detailed_sections)} detailed sections generated")
        
        # Verify content coverage
        script = self._verify_content_coverage(outline, script)
        
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
            contents=prompt,
            config=self.generation_config
        )
        
        script = self._parse_json_response(response.text)
        script = self._validate_script(script, topic)
        return script
    
    def _verify_content_coverage(self, outline: Dict[str, Any], script: Dict[str, Any]) -> Dict[str, Any]:
        """Verify that all content from the outline checklist was covered in the script
        
        Returns script with coverage_report metadata
        """
        # Get the content coverage checklist from outline
        content_checklist = outline.get('content_coverage_checklist', [])
        sections_outline = outline.get('sections_outline', [])
        
        # Collect all items that should be covered
        all_items_to_cover = set(content_checklist)
        for section in sections_outline:
            for item in section.get('content_checklist', []):
                all_items_to_cover.add(item)
        
        # Collect all covered items from generated sections
        covered_items = set()
        for section in script.get('sections', []):
            for item in section.get('covered_items', []):
                covered_items.add(item)
        
        # Calculate coverage
        total_items = len(all_items_to_cover)
        covered_count = len(covered_items & all_items_to_cover)
        
        script['coverage_report'] = {
            'total_items_to_cover': total_items,
            'items_covered': covered_count,
            'coverage_percentage': (covered_count / total_items * 100) if total_items > 0 else 100,
            'missing_items': list(all_items_to_cover - covered_items)[:20]  # Limit to 20 items
        }
        
        if total_items > 0:
            print(f"[ScriptGenerator] Coverage: {covered_count}/{total_items} items ({script['coverage_report']['coverage_percentage']:.1f}%)")
        
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
            
            # Add visual hints to each segment based on section's visual_description
            section_visual = section.get("visual_description", "")
            num_segments = len(segments)
            for i, seg in enumerate(segments):
                # Create segment-specific visual hint
                if num_segments == 1:
                    seg["visual_description"] = section_visual
                else:
                    # Add context about segment position
                    if i == 0:
                        seg["visual_description"] = f"INTRO: {section_visual}"
                    elif i == num_segments - 1:
                        seg["visual_description"] = f"CONCLUSION: {section_visual}"
                    else:
                        seg["visual_description"] = f"Part {i+1}/{num_segments}: {section_visual}"
            
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
