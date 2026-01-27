"""
Manim Generator - Uses Tool-based Generation

Generates Manim animations using the unified prompting engine with tool calling.
All generation logic uses: app.services.manim_generator.tools
"""

import json
from typing import Dict, Any, Optional, Tuple
from pathlib import Path

# Prompting engine
from app.services.infrastructure.llm import PromptingEngine, PromptConfig, CostTracker

# Model configuration
from app.config.models import get_model_config

# Tool-based generation (unified approach)
from .tools import (
    GenerationToolHandler,
    CorrectionToolHandler,
    build_context,
)
from .code_helpers import clean_code, create_scene_file
from .validation import CodeValidator
from . import renderer


class ManimGenerator:
    """
    Generates Manim animations using tool-based approach.
    
    Uses GenerationToolHandler and CorrectionToolHandler for:
    - Visual script generation (structured output)
    - Manim code generation (function calling)
    - Error correction (tool-based fixes)
    
    All logic centralized in: tools/
    """

    MAX_CLEAN_RETRIES = 2

    def __init__(self, pipeline_name: Optional[str] = None):
        self.pipeline_name = pipeline_name

        # Initialize cost tracker
        self.cost_tracker = CostTracker()
        
        # Initialize prompting engines for different stages (pipeline-aware)
        self.script_engine = PromptingEngine("visual_script_generation", self.cost_tracker, pipeline_name=pipeline_name)
        self.code_engine = PromptingEngine("manim_generation", self.cost_tracker, pipeline_name=pipeline_name)
        self.correction_engine = PromptingEngine("code_correction", self.cost_tracker, pipeline_name=pipeline_name)
        
        # Initialize validator
        self.validator = CodeValidator()
        
        # Initialize tool handlers (unified approach)
        self.generation_handler = GenerationToolHandler(self.code_engine, self.validator)
        self.correction_handler = CorrectionToolHandler(self.correction_engine, self.validator)

        # Initialize stats
        self.stats = {
            "total_sections": 0,
            "regenerated_sections": 0,
            "total_retries": 0,
            "skipped_sections": 0,
            "failed_sections": []
        }
        
        # Load config
        self._refresh_config()

    def _refresh_config(self):
        """Refresh model configuration"""
        self._manim_config = get_model_config("manim_generation", self.pipeline_name)
        
        self.MAX_CORRECTION_ATTEMPTS = getattr(self._manim_config, 'max_correction_attempts', 3)

    def get_cost_summary(self) -> Dict[str, Any]:
        """Get cost summary"""
        return self.cost_tracker.get_summary(None)

    def print_cost_summary(self):
        """Print cost summary"""
        summary = self.get_cost_summary()
        print("\n" + "="*60)
        print("COST SUMMARY")
        print("="*60)
        for key, value in summary.items():
            if isinstance(value, dict):
                print(f"\n{key}:")
                for k, v in value.items():
                    print(f"  {k}: {v}")
            else:
                print(f"{key}: {value}")
        print("="*60 + "\n")

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
        """
        Generate a Manim video for a section.
        
        Args:
            section: Section data
            output_dir: Output directory
            section_index: Section index
            audio_duration: Actual audio duration
            style: Visual style
            language: Language code
            clean_retry: Current retry attempt
            
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
            reuse_visual_script=reuse_visual_script
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
                audio_duration, style, language, clean_retry + 1
            )
        elif output_video is None:
            self.stats["skipped_sections"] += 1
            self.stats["failed_sections"].append(section_index)

        with open(code_file, "r", encoding="utf-8") as f:
            final_code = f.read()

        return {
            "video_path": output_video,
            "manim_code": final_code,
            "manim_code_path": str(code_file)
        }

    async def _generate_manim_code(
        self,
        section: Dict[str, Any],
        audio_duration: float,
        output_dir: str,
        section_index: int,
        reuse_visual_script: bool = False
    ) -> Tuple[str, Optional[str]]:
        """
        Generate Manim code using tool-based approach.
        
        Uses GenerationToolHandler for structured generation.
        
        Returns:
            Tuple of (manim_code, visual_script)
        """
        style = section.get('style', '3b1b')
        language = section.get('language', 'en')
        
        # Try to reuse existing visual script
        visual_script = None
        if reuse_visual_script and output_dir:
            script_file = Path(output_dir) / f"visual_script_{section_index}.md"
            if script_file.exists():
                print("[ManimGenerator] ♻️ Reusing visual script")
                with open(script_file, "r", encoding="utf-8") as f:
                    visual_script = f.read().strip()

        # Use tool-based generation
        print("[ManimGenerator] Generating code with tool handler...")
        result = await self.generation_handler.generate(
            section=section,
            style=style,
            target_duration=audio_duration,
            language=language,
            use_visual_script=(visual_script is None)  # Generate script if we don't have one
        )
        
        if result.success and result.code:
            code = clean_code(result.code)
            
            # Save visual script if generated
            if result.visual_script and output_dir:
                script_file = Path(output_dir) / f"visual_script_{section_index}.md"
                visual_script_text = json.dumps(result.visual_script, indent=2)
                with open(script_file, "w", encoding="utf-8") as f:
                    f.write(visual_script_text)
                visual_script = visual_script_text
            
            print(f"[ManimGenerator] OK Code generated: {len(code)} chars")
            return (code, visual_script)
        
        # Fallback: basic generation
        print(f"[ManimGenerator] Tool generation failed: {result.error}")
        print("[ManimGenerator] Using fallback...")
        
        code = await self._generate_fallback(section, audio_duration, style, language)
        return (code, None)

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
