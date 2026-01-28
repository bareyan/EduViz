"""
Manim Generator - Uses Tool-based Generation

Generates Manim animations using the unified prompting engine with tool calling.
All generation logic uses: app.services.manim_generator.tools

Flow:
1. Generate Visual Script from audio segments (structured storyboard)
2. Generate Manim code from Visual Script (tool-based)
3. Validate and fix errors iteratively
4. Render the final animation
"""

import json
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path

# Prompting engine
from app.services.infrastructure.llm import PromptingEngine, PromptConfig, CostTracker

# Model configuration
from app.config.models import get_model_config

# Visual Script generation (Step 1)
from app.services.pipeline.visual_script import (
    VisualScriptGenerator,
    VisualScriptPlan,
    load_visual_script,
)

# Tool-based generation (unified approach)
from .tools import (
    GenerationToolHandler,
    build_context,
)
from .code_helpers import clean_code, create_scene_file
from .validation import CodeValidator
from . import renderer
from ..config import MAX_CLEAN_RETRIES, MAX_CORRECTION_ATTEMPTS


class ManimGenerator:
    """
    Generates Manim animations using tool-based approach.
    
    Pipeline:
    1. VisualScriptGenerator: Converts audio segments -> visual storyboard
    2. GenerationToolHandler: Converts visual script -> Manim code
    3. CodeValidator: Validates generated code
    4. Renderer: Creates final video
    
    All logic centralized in respective modules.
    """

    def __init__(self, pipeline_name: Optional[str] = None):
        self.pipeline_name = pipeline_name

        # Initialize cost tracker
        self.cost_tracker = CostTracker()
        
        # Initialize Visual Script Generator (Step 1)
        self.visual_script_generator = VisualScriptGenerator(
            cost_tracker=self.cost_tracker,
            pipeline_name=pipeline_name
        )
        
        # Initialize prompting engines for different stages (pipeline-aware)
        self.script_engine = PromptingEngine("visual_script_generation", self.cost_tracker, pipeline_name=pipeline_name)
        self.code_engine = PromptingEngine("manim_generation", self.cost_tracker, pipeline_name=pipeline_name)
        self.correction_engine = PromptingEngine("code_correction", self.cost_tracker, pipeline_name=pipeline_name)
        
        # Initialize validator
        self.validator = CodeValidator()
        
        # Initialize tool handlers (unified approach - same handler for generation and correction)
        self.generation_handler = GenerationToolHandler(self.code_engine, self.validator)
        self.correction_handler = GenerationToolHandler(self.correction_engine, self.validator)

        # Initialize stats
        self.stats = {
            "total_sections": 0,
            "regenerated_sections": 0,
            "total_retries": 0,
            "skipped_sections": 0,
            "failed_sections": []
        }
        
        # Load config and set limits
        self._refresh_config()
        self.MAX_CLEAN_RETRIES = MAX_CLEAN_RETRIES
        self.MAX_CORRECTION_ATTEMPTS = MAX_CORRECTION_ATTEMPTS

    def _refresh_config(self):
        """Refresh model configuration"""
        self._manim_config = get_model_config("manim_generation", self.pipeline_name)

    def get_cost_summary(self) -> Dict[str, Any]:
        """Get cost summary"""
        return self.cost_tracker.get_summary()

    def print_cost_summary(self):
        """Print cost summary"""
        self.cost_tracker.print_summary()

    async def generate_section_video(
        self,
        section: Dict[str, Any],
        output_dir: str,
        section_index: int,
        audio_duration: Optional[float] = None,
        style: str = "3b1b",
        language: str = "en",
        clean_retry: int = 0,
        audio_segments: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate a Manim video for a section.
        
        Args:
            section: Section data
            output_dir: Output directory
            section_index: Section index
            audio_duration: Actual audio duration (total)
            style: Visual style
            language: Language code
            clean_retry: Current retry attempt
            audio_segments: Optional list of audio segments with actual durations
                           [{"text": "...", "duration": 5.2}, ...]
            
        Returns:
            Dict with video_path and manim_code
        """
        if clean_retry == 0:
            self._refresh_config()
            self.stats["total_sections"] += 1

        target_duration = audio_duration if audio_duration else section.get("duration_seconds", 60)
        section["target_duration"] = target_duration
        section["language"] = language
        section["style"] = style

        retry_note = f" (clean retry {clean_retry})" if clean_retry > 0 else ""
        print(f"[ManimGenerator] Generating code for section {section_index}{retry_note}")

        # Generate code (2-shot with visual script)
        reuse_visual_script = (clean_retry > 0)
        manim_code, visual_script = await self._generate_manim_code(
            section,
            target_duration,
            output_dir=output_dir,
            section_index=section_index,
            reuse_visual_script=reuse_visual_script,
            audio_segments=audio_segments
        )

        # Write code file
        section_id = section.get("id", f"section_{section_index}").replace("-", "_").replace(" ", "_")
        scene_name = f"Section{section_id.title().replace('_', '')}"
        code_file = Path(output_dir) / f"scene_{section_index}.py"
        
        full_code = create_scene_file(manim_code, section_id, target_duration, style)
        
        with open(code_file, "w", encoding="utf-8") as f:
            f.write(full_code)

        # Render
        output_video = await renderer.render_scene(
            self,
            code_file,
            scene_name,
            output_dir,
            section_index,
            section=section,
            clean_retry=clean_retry
        )

        # Retry if needed
        if output_video is None and clean_retry < self.MAX_CLEAN_RETRIES:
            print(f"[ManimGenerator] WARN Section {section_index} failed, retry {clean_retry + 1}/{self.MAX_CLEAN_RETRIES}")
            if clean_retry == 0:
                self.stats["regenerated_sections"] += 1
            self.stats["total_retries"] += 1
            
            return await self.generate_section_video(
                section, output_dir, section_index,
                audio_duration, style, language, clean_retry + 1,
                audio_segments=audio_segments  # Pass audio segments for retry
            )
        elif output_video is None:
            self.stats["skipped_sections"] += 1
            self.stats["failed_sections"].append(section_index)

        with open(code_file, "r", encoding="utf-8") as f:
            final_code = f.read()

        return {
            "video_path": output_video,
            "manim_code": final_code,
            "manim_code_path": str(code_file),
            "visual_script": visual_script.to_dict() if visual_script else None
        }

    async def _generate_manim_code(
        self,
        section: Dict[str, Any],
        audio_duration: float,
        output_dir: str,
        section_index: int,
        reuse_visual_script: bool = False,
        audio_segments: List[Dict[str, Any]] = None
    ) -> Tuple[str, Optional[VisualScriptPlan]]:
        """
        Generate Manim code using visual script + tool-based approach.
        
        Flow:
        1. Generate or load Visual Script (storyboard with timing)
        2. Use Visual Script to generate Manim code with proper pauses
        
        Args:
            section: Section data with narration, title, etc.
            audio_duration: Target audio duration
            output_dir: Directory for output files
            section_index: Index of the section
            reuse_visual_script: Whether to try reusing existing visual script
            audio_segments: Optional audio segments with actual durations
            
        Returns:
            Tuple of (manim_code, visual_script_plan)
        """
        style = section.get('style', '3b1b')
        language = section.get('language', 'en')
        
        visual_script_plan = None
        
        # Step 1: Try to load existing visual script
        if reuse_visual_script and output_dir:
            json_file = Path(output_dir) / f"visual_script_{section_index}.json"
            if json_file.exists():
                print("[ManimGenerator] ♻️ Reusing existing visual script")
                visual_script_plan = load_visual_script(str(json_file))
        
        # Step 2: Generate Visual Script if not available
        if visual_script_plan is None:
            print("[ManimGenerator] 📝 Generating visual script...")
            
            vs_result = await self.visual_script_generator.generate_and_save(
                section=section,
                output_dir=output_dir,
                section_index=section_index,
                source_context=section.get("narration", "")[:500],
                audio_segments=audio_segments
            )
            
            if vs_result.success and vs_result.visual_script:
                visual_script_plan = vs_result.visual_script
                print(f"[ManimGenerator] ✓ Visual script generated: {len(visual_script_plan.segments)} segments, "
                      f"total duration: {visual_script_plan.total_duration:.1f}s")
            else:
                print(f"[ManimGenerator] WARN Visual script generation failed: {vs_result.error}")
                # Fallback: continue without visual script
        
        # Step 3: Generate Manim code using tool handler
        print("[ManimGenerator] 🎬 Generating Manim code...")
        result = await self.generation_handler.generate(
            section=section,
            style=style,
            target_duration=audio_duration,
            language=language,
            visual_script=visual_script_plan  # Pass visual script for guided generation
        )
        
        if result.success and result.code:
            code = clean_code(result.code)
            print(f"[ManimGenerator] ✓ Code generated: {len(code)} chars")
            return (code, visual_script_plan)
        
        # Fallback: basic generation without visual script
        print(f"[ManimGenerator] Tool generation failed: {result.error}")
        print("[ManimGenerator] Using fallback...")
        
        code = await self._generate_fallback(section, audio_duration, style, language)
        return (code, visual_script_plan)

    async def _generate_fallback(
        self,
        section: Dict[str, Any],
        audio_duration: float,
        style: str,
        language: str
    ) -> str:
        """Fallback single-shot code generation"""
        title = section.get("title", "Section")
        narration = section.get("narration", section.get("tts_narration", ""))[:300]
        
        context = build_context(
            style=style,
            animation_type="text",
            target_duration=audio_duration,
            language=language
        )
        
        prompt = f"""Generate simple Manim code for this section:

TITLE: {title}
NARRATION: {narration}
DURATION: {audio_duration}s

Generate code for the construct() method only. Keep it simple and reliable."""
        
        config = PromptConfig(enable_thinking=True, timeout=300.0)
        result = await self.code_engine.generate(
            prompt, 
            config,
            system_prompt=context.to_system_prompt()
        )
        
        if result.get("success"):
            code = clean_code(result["response"])
            validation = self.validator.validate_code(code)
            
            if validation["valid"]:
                print("[ManimGenerator] OK Fallback code passed validation")
            else:
                print("[ManimGenerator] WARN Fallback validation issues")
            
            return code
        else:
            # Ultimate fallback - guaranteed to work
            return f'''        title = Text("{title[:30]}", font_size=36).to_edge(UP)
        self.play(Write(title))
        self.wait({max(1.0, audio_duration - 2)})
        self.play(FadeOut(title))'''

    async def render_from_code(
        self,
        manim_code: str,
        output_dir: str,
        section_index: int = 0
    ) -> Optional[str]:
        """Render video from existing code"""
        section_id = f"section_{section_index}"
        scene_name = f"Section{section_id.title().replace('_', '')}"
        code_file = Path(output_dir) / f"scene_{section_index}.py"
        
        full_code = create_scene_file(manim_code, section_id, 60, "3b1b")
        
        with open(code_file, "w", encoding="utf-8") as f:
            f.write(full_code)

        return await renderer.render_scene(
            self, code_file, scene_name, output_dir,
            section_index, section={}, clean_retry=0
        )
