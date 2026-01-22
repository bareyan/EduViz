"""
Manim Generator - Uses Gemini to generate Manim code for each video section

This module provides the ManimGenerator class for generating animated math
videos using Manim Community Edition and Google's Gemini AI.
"""

import os
import json
import asyncio
from typing import Dict, Any, Optional, Tuple
from pathlib import Path

# Gemini
try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

# Visual Quality Control
try:
    from ..visual_qc import VisualQualityController
    VISUAL_QC_AVAILABLE = True
except ImportError:
    VISUAL_QC_AVAILABLE = False
    print("[ManimGenerator] Visual QC not available")

# Local imports
from .cost_tracker import CostTracker
from .prompts import (
    get_language_instructions,
    get_color_instructions,
    get_animation_guidance,
    build_generation_prompt,
    build_timing_context,
    build_visual_script_prompt,
    build_visual_script_analysis_prompt,
    get_visual_script_analysis_schema,
    build_code_from_script_prompt,
)
from .code_utils import clean_code, create_scene_file
from . import renderer


class ManimGenerator:
    """Generates Manim animations using Gemini AI"""
    
    # Model configuration
    MODEL = "gemini-3-flash-preview"  # Main generation
    CORRECTION_MODEL = "gemini-2.5-flash"  # Cheap model for corrections
    STRONG_MODEL = "gemini-3-flash-preview"  # Strong fallback for visual fixes
    MAX_CORRECTION_ATTEMPTS = 2
    MAX_CLEAN_RETRIES = 1
    
    # Visual QC settings
    ENABLE_VISUAL_QC = True  # Toggle: Set to True to enable visual QC
    QC_MODEL = "gemini-flash-lite-latest"
    MAX_QC_ITERATIONS = 3  # Allow up to 3 fix attempts before accepting
    
    def __init__(self):
        self.client = None
        api_key = os.getenv("GEMINI_API_KEY")
        if genai and api_key:
            self.client = genai.Client(api_key=api_key)
        else:
            raise ValueError("GEMINI_API_KEY environment variable is required")
        
        # Generation config with medium thinking for code generation
        self.generation_config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(
                thinking_level="MEDIUM",
            ),
        ) if types else None
        
        # Initialize cost tracker
        self.cost_tracker = CostTracker()
        
        # Initialize visual QC controller
        self.visual_qc = None
        if VISUAL_QC_AVAILABLE and self.ENABLE_VISUAL_QC:
            try:
                self.visual_qc = VisualQualityController(model=self.QC_MODEL)
                print(f"[ManimGenerator] Visual QC enabled with model: {self.QC_MODEL}")
            except Exception as e:
                print(f"[ManimGenerator] Failed to initialize Visual QC: {e}")
                self.visual_qc = None
    
    def get_cost_summary(self) -> Dict[str, Any]:
        """Get a summary of token usage and costs"""
        return self.cost_tracker.get_summary(self.visual_qc)
    
    def print_cost_summary(self):
        """Print a formatted cost summary to console"""
        self.cost_tracker.print_summary(self.visual_qc)
    
    async def generate_section_video(
        self,
        section: Dict[str, Any],
        output_dir: str,
        section_index: int,
        audio_duration: Optional[float] = None,
        style: str = "3b1b",
        language: str = "en",
        clean_retry: int = 0
    ) -> Dict[str, Any]:
        """Generate a video for a single section
        
        Args:
            section: Section data with title, narration, visual_description, etc.
            output_dir: Directory to save output files
            section_index: Index of this section
            audio_duration: Actual audio duration in seconds
            style: Visual style - "3b1b" for dark, "clean" for light
            language: Language code for proper text/LaTeX handling
            clean_retry: Current clean retry attempt
        
        Returns:
            Dict with video_path and manim_code
        """
        
        # Use audio duration as the target if available
        target_duration = audio_duration if audio_duration else section.get("duration_seconds", 60)
        section["target_duration"] = target_duration
        section["language"] = language
        section["style"] = style
        
        # Generate Manim code using Gemini (2-shot approach)
        retry_note = f" (clean retry {clean_retry})" if clean_retry > 0 else ""
        print(f"[ManimGenerator] Generating code for section {section_index}{retry_note}")
        manim_code, visual_script = await self._generate_manim_code(
            section, target_duration, output_dir=output_dir, section_index=section_index
        )
        
        # Write the code to a temp file
        section_id = section.get("id", f"section_{section_index}").replace("-", "_").replace(" ", "_")
        scene_name = f"Section{section_id.title().replace('_', '')}"
        
        code_file = Path(output_dir) / f"scene_{section_index}.py"
        
        # Visual script is already saved in _generate_manim_code immediately after generation
        
        # Create the full scene file with theme enforcement
        full_code = create_scene_file(manim_code, section_id, target_duration, style)
        
        with open(code_file, "w") as f:
            f.write(full_code)
        
        # Render the scene
        output_video = await renderer.render_scene(
            self,
            code_file, 
            scene_name, 
            output_dir, 
            section_index,
            section=section,
            clean_retry=clean_retry
        )
        
        # Check if we need to retry from clean
        if output_video is None and clean_retry < self.MAX_CLEAN_RETRIES:
            print(f"[ManimGenerator] ⚠️ Section {section_index} failed, attempting clean retry {clean_retry + 1}/{self.MAX_CLEAN_RETRIES}")
            return await self.generate_section_video(
                section=section,
                output_dir=output_dir,
                section_index=section_index,
                audio_duration=audio_duration,
                style=style,
                language=language,
                clean_retry=clean_retry + 1
            )
        
        # Re-read the final code
        with open(code_file, "r") as f:
            final_code = f.read()
        
        return {
            "video_path": output_video,
            "manim_code": final_code,
            "manim_code_path": str(code_file)
        }
    
    async def render_from_code(
        self,
        manim_code: str,
        output_dir: str,
        section_index: int = 0
    ) -> Optional[str]:
        """Render a Manim scene from existing code (e.g., translated code)"""
        return await renderer.render_from_code(self, manim_code, output_dir, section_index)
    
    async def _generate_manim_code(
        self, 
        section: Dict[str, Any], 
        target_duration: float,
        output_dir: Optional[str] = None,
        section_index: int = 0
    ) -> Tuple[str, Optional[str]]:
        """Use Gemini to generate Manim code for a section using 2-shot approach
        
        Shot 1: Generate detailed visual script with object descriptions, positions, timing
        Shot 1.5: Quick spatial safety check with structured JSON output
        Shot 2: Convert visual script to Manim code (with fixes if any)
        
        Args:
            section: Section data
            target_duration: Target duration in seconds
            output_dir: Directory to save visual script immediately (optional)
            section_index: Index of the section for naming the visual script file
        
        Returns:
            Tuple of (manim_code: str, visual_script: Optional[str])
        """
        
        audio_duration = target_duration
        
        # Get style and language settings
        style = section.get('style', '3b1b')
        language = section.get('language', 'en')
        animation_type = section.get('animation_type', 'text')
        
        # Get instructions from prompts module
        language_instructions = get_language_instructions(language)
        color_instructions = get_color_instructions(style)
        type_guidance = get_animation_guidance(animation_type)
        
        # Build timing context using the prompts module function
        narration_segments = section.get('narration_segments', [])
        timing_context = build_timing_context(section, narration_segments)
        
        # ══════════════════════════════════════════════════════════════════════
        # SHOT 1: Generate Visual Script (Storyboard)
        # ══════════════════════════════════════════════════════════════════════
        print(f"[ManimGenerator] Shot 1: Generating visual script...")
        
        visual_script_prompt = build_visual_script_prompt(
            section=section,
            audio_duration=audio_duration,
            timing_context=timing_context
        )
        
        visual_script = None
        try:
            response1 = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.MODEL,
                    contents=visual_script_prompt,
                    config=self.generation_config
                ),
                timeout=180
            )
            
            self.cost_tracker.track_usage(response1, self.MODEL)
            visual_script = response1.text.strip()
            print(f"[ManimGenerator] Shot 1 complete: {len(visual_script)} chars")
            
            # Save visual script IMMEDIATELY after generation (before analysis)
            if output_dir and visual_script:
                script_file = Path(output_dir) / f"visual_script_{section_index}.md"
                with open(script_file, "w") as f:
                    f.write(visual_script)
                print(f"[ManimGenerator] Visual script saved to {script_file}")
            
        except asyncio.TimeoutError:
            print(f"[ManimGenerator] Shot 1 timed out, falling back to single-shot")
            visual_script = None
        except Exception as e:
            print(f"[ManimGenerator] Shot 1 error: {e}, falling back to single-shot")
            visual_script = None
        
        # ══════════════════════════════════════════════════════════════════════
        # SHOT 1.5: Analyze Visual Script for Spatial Issues (Structured Output)
        # ══════════════════════════════════════════════════════════════════════
        
        spatial_fixes = []  # Will hold any fixes from analysis
        
        if visual_script:
            print(f"[ManimGenerator] Shot 1.5: Checking visual script for spatial issues...")
            
            analysis_prompt = build_visual_script_analysis_prompt(
                visual_script=visual_script,
                audio_duration=audio_duration
            )
            
            # Get the structured output schema
            analysis_schema = get_visual_script_analysis_schema()
            
            try:
                # Use structured output config if schema is available
                if analysis_schema:
                    analysis_config = types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=analysis_schema
                    )
                else:
                    analysis_config = self.generation_config
                
                analysis_response = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.client.models.generate_content,
                        model=self.CORRECTION_MODEL,  # Use cheaper model for analysis
                        contents=analysis_prompt,
                        config=analysis_config
                    ),
                    timeout=60  # Shorter timeout for quick check
                )
                
                self.cost_tracker.track_usage(analysis_response, self.CORRECTION_MODEL)
                analysis_text = analysis_response.text.strip()
                
                # Parse JSON response
                try:
                    analysis_result = json.loads(analysis_text)
                    status = analysis_result.get('status', 'ok')
                    issues_count = analysis_result.get('issues_found', 0)
                    spatial_fixes = analysis_result.get('fixes', [])
                    
                    if status == 'ok':
                        print(f"[ManimGenerator] Shot 1.5: Layout OK ✓")
                    else:
                        print(f"[ManimGenerator] Shot 1.5: Found {issues_count} issues, {len(spatial_fixes)} fixes")
                    
                    # Save analysis report
                    if output_dir:
                        analysis_file = Path(output_dir) / f"visual_script_analysis_{section_index}.json"
                        with open(analysis_file, "w") as f:
                            json.dump(analysis_result, f, indent=2)
                        print(f"[ManimGenerator] Analysis saved to {analysis_file}")
                        
                except json.JSONDecodeError:
                    print(f"[ManimGenerator] Shot 1.5: Could not parse JSON, skipping fixes")
                    # Save raw response for debugging
                    if output_dir:
                        analysis_file = Path(output_dir) / f"visual_script_analysis_{section_index}.txt"
                        with open(analysis_file, "w") as f:
                            f.write(analysis_text)
                    
            except asyncio.TimeoutError:
                print(f"[ManimGenerator] Shot 1.5 timed out, proceeding without fixes")
            except Exception as e:
                print(f"[ManimGenerator] Shot 1.5 error: {e}, proceeding without fixes")
        
        # ══════════════════════════════════════════════════════════════════════
        # SHOT 2: Generate Manim Code from Visual Script (with fixes if any)
        # ══════════════════════════════════════════════════════════════════════
        
        if visual_script:
            print(f"[ManimGenerator] Shot 2: Generating Manim code from visual script...")
            
            code_prompt = build_code_from_script_prompt(
                section=section,
                visual_script=visual_script,
                audio_duration=audio_duration,
                language_instructions=language_instructions,
                color_instructions=color_instructions,
                type_guidance=type_guidance,
                spatial_fixes=spatial_fixes if spatial_fixes else None
            )
            
            try:
                response2 = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.client.models.generate_content,
                        model=self.MODEL,
                        contents=code_prompt,
                        config=self.generation_config
                    ),
                    timeout=180
                )
                
                self.cost_tracker.track_usage(response2, self.MODEL)
                code = response2.text.strip()
                code = clean_code(code)
                print(f"[ManimGenerator] Shot 2 complete: {len(code)} chars of code")
                
                return (code, visual_script)
                
            except asyncio.TimeoutError:
                print(f"[ManimGenerator] Shot 2 timed out, falling back to single-shot")
            except Exception as e:
                print(f"[ManimGenerator] Shot 2 error: {e}, falling back to single-shot")
        
        # ══════════════════════════════════════════════════════════════════════
        # FALLBACK: Single-shot generation (original method)
        # ══════════════════════════════════════════════════════════════════════
        print(f"[ManimGenerator] Using single-shot fallback...")
        
        prompt = build_generation_prompt(
            section=section,
            audio_duration=audio_duration,
            timing_context=timing_context,
            language_instructions=language_instructions,
            color_instructions=color_instructions,
            type_guidance=type_guidance
        )

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.MODEL,
                    contents=prompt,
                    config=self.generation_config
                ),
                timeout=300
            )
            
            self.cost_tracker.track_usage(response, self.MODEL)
            
        except asyncio.TimeoutError:
            print(f"[ManimGenerator] Gemini API timed out for section code generation")
            return ('''        text = Text("Section", font_size=48)
        self.play(Write(text))
        self.wait(2)''', None)
        except Exception as e:
            print(f"[ManimGenerator] Gemini API error: {e}")
            return ('''        text = Text("Section", font_size=48)
        self.play(Write(text))
        self.wait(2)''', None)
        
        code = response.text.strip()
        code = clean_code(code)
        
        return (code, None)


# Re-export for backward compatibility
__all__ = ['ManimGenerator']
