"""
Manim Generator - Uses Centralized PromptingEngine

Generates Manim animations using the unified prompting engine.
All prompts are centralized in: app.services.prompting_engine.prompts
"""

import json
import asyncio
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path

# Prompting engine with centralized prompts
from app.services.prompting_engine import PromptingEngine, PromptConfig, ToolHandler, format_prompt

# Model configuration
from app.config.models import get_model_config

# Visual Quality Control
try:
    from ..visual_qc import VisualQualityController
    VISUAL_QC_AVAILABLE = True
except ImportError:
    VISUAL_QC_AVAILABLE = False

# Local imports
from app.services.cost_tracker import CostTracker
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
from .code_helpers import clean_code, create_scene_file
from .validation import CodeValidator
from . import renderer


class ManimGenerator:
    """
    Generates Manim animations using centralized prompting engine.
    
    Uses separate engines for different generation stages:
    - script_engine: Visual script/storyboard generation
    - code_engine: Manim code generation
    - correction_engine: Error analysis and corrections
    
    All prompts centralized in: prompting_engine.prompts
    """

    MAX_CLEAN_RETRIES = 2
    ENABLE_VISUAL_QC = True
    MAX_QC_ITERATIONS = 3

    def __init__(self):
        # Initialize cost tracker
        self.cost_tracker = CostTracker()
        
        # Initialize prompting engines for different stages
        self.script_engine = PromptingEngine("visual_script_generation", self.cost_tracker)
        self.code_engine = PromptingEngine("manim_generation", self.cost_tracker)
        self.correction_engine = PromptingEngine("code_correction", self.cost_tracker)
        
        # Initialize validator
        self.validator = CodeValidator()

        # Initialize stats
        self.stats = {
            "total_sections": 0,
            "regenerated_sections": 0,
            "total_retries": 0,
            "skipped_sections": 0,
            "failed_sections": []
        }

        # Visual QC controller
        self.visual_qc = None
        self._qc_initialized = False
        
        # Load config
        self._refresh_config()

    def _refresh_config(self):
        """Refresh model configuration"""
        self._manim_config = get_model_config("manim_generation")
        self._visual_qc_config = get_model_config("visual_qc")
        
        self.MAX_CORRECTION_ATTEMPTS = getattr(self._manim_config, 'max_correction_attempts', 3)

        # Initialize Visual QC if needed
        if VISUAL_QC_AVAILABLE and self.ENABLE_VISUAL_QC and not self._qc_initialized:
            try:
                qc_model = self._visual_qc_config.model_name
                self.visual_qc = VisualQualityController(model=qc_model)
                self._qc_initialized = True
            except Exception as e:
                print(f"[ManimGenerator] Failed to initialize Visual QC: {e}")
                self.visual_qc = None

    def get_cost_summary(self) -> Dict[str, Any]:
        """Get cost summary"""
        return self.cost_tracker.get_summary(self.visual_qc)

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
            print(f"[ManimGenerator] ⚠️ Section {section_index} failed, retry {clean_retry + 1}/{self.MAX_CLEAN_RETRIES}")
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
        Generate Manim code using 2-shot approach with prompting engine.
        
        Returns:
            Tuple of (manim_code, visual_script)
        """
        # Get context
        style = section.get('style', '3b1b')
        language = section.get('language', 'en')
        animation_type = section.get('animation_type', 'text')
        
        language_instructions = get_language_instructions(language)
        color_instructions = get_color_instructions(style)
        type_guidance = get_animation_guidance(animation_type)
        
        narration_segments = section.get('narration_segments', [])
        timing_context = build_timing_context(section, narration_segments)

        # SHOT 1: Generate visual script
        visual_script = await self._generate_visual_script(
            section, audio_duration, timing_context,
            output_dir, section_index, reuse_visual_script
        )

        # SHOT 1.5: Analyze for spatial issues
        spatial_fixes = []
        if visual_script:
            spatial_fixes = await self._analyze_visual_script(
                visual_script, audio_duration, output_dir, section_index
            )

        # SHOT 2: Generate code from visual script
        if visual_script:
            code = await self._generate_code_from_script(
                section, visual_script, audio_duration,
                language_instructions, color_instructions,
                type_guidance, spatial_fixes
            )
            if code:
                return (code, visual_script)

        # Fallback: Single-shot generation
        print("[ManimGenerator] Using single-shot fallback...")
        code = await self._generate_code_single_shot(
            section, audio_duration, timing_context,
            language_instructions, color_instructions, type_guidance
        )
        
        return (code, None)

    async def _generate_visual_script(
        self,
        section: Dict[str, Any],
        audio_duration: float,
        timing_context: str,
        output_dir: str,
        section_index: int,
        reuse: bool
    ) -> Optional[str]:
        """Generate visual script (Shot 1)"""
        # Try to reuse existing
        if reuse and output_dir:
            script_file = Path(output_dir) / f"visual_script_{section_index}.md"
            if script_file.exists():
                print(f"[ManimGenerator] ♻️ Reusing visual script")
                with open(script_file, "r", encoding="utf-8") as f:
                    return f.read().strip()

        print("[ManimGenerator] Shot 1: Generating visual script...")
        
        prompt = build_visual_script_prompt(section, audio_duration, timing_context)
        config = PromptConfig(enable_thinking=True, timeout=180.0)
        
        result = await self.script_engine.generate(prompt, config)
        
        if result["success"]:
            visual_script = result["response"].strip()
            print(f"[ManimGenerator] Shot 1 complete: {len(visual_script)} chars")
            
            # Save immediately
            if output_dir:
                script_file = Path(output_dir) / f"visual_script_{section_index}.md"
                with open(script_file, "w", encoding="utf-8") as f:
                    f.write(visual_script)
            
            return visual_script
        else:
            print(f"[ManimGenerator] Shot 1 failed: {result.get('error')}")
            return None

    async def _analyze_visual_script(
        self,
        visual_script: str,
        audio_duration: float,
        output_dir: str,
        section_index: int
    ) -> List[Dict[str, Any]]:
        """Analyze visual script for spatial issues (Shot 1.5)"""
        print("[ManimGenerator] Shot 1.5: Analyzing visual script...")
        
        prompt = build_visual_script_analysis_prompt(visual_script, audio_duration)
        config = PromptConfig(response_format="json", timeout=60.0)
        
        result = await self.correction_engine.generate(prompt, config)
        
        if result["success"] and "parsed_json" in result:
            analysis = result["parsed_json"]
            status = analysis.get('status', 'ok')
            issues_count = analysis.get('issues_found', 0)
            fixes = analysis.get('fixes', [])
            
            if status == 'ok':
                print("[ManimGenerator] Shot 1.5: Layout OK ✓")
            else:
                print(f"[ManimGenerator] Shot 1.5: Found {issues_count} issues, {len(fixes)} fixes")
            
            # Save analysis
            if output_dir:
                analysis_file = Path(output_dir) / f"visual_script_analysis_{section_index}.json"
                with open(analysis_file, "w", encoding="utf-8") as f:
                    json.dump(analysis, f, indent=2)
            
            return fixes
        else:
            print(f"[ManimGenerator] Shot 1.5 failed: {result.get('error')}")
            return []

    async def _generate_code_from_script(
        self,
        section: Dict[str, Any],
        visual_script: str,
        audio_duration: float,
        language_instructions: str,
        color_instructions: str,
        type_guidance: str,
        spatial_fixes: List[Dict[str, Any]]
    ) -> Optional[str]:
        """Generate code from visual script (Shot 2)"""
        print("[ManimGenerator] Shot 2: Generating Manim code...")
        
        prompt = build_code_from_script_prompt(
            section, visual_script, audio_duration,
            language_instructions, color_instructions,
            type_guidance,
            spatial_fixes if spatial_fixes else None
        )
        
        config = PromptConfig(enable_thinking=True, timeout=300.0)
        result = await self.code_engine.generate(prompt, config)
        
        if result["success"]:
            code = clean_code(result["response"])
            
            # Validate
            validation = self.validator.validate_code(code)
            if validation["valid"]:
                print("[ManimGenerator] ✓ Code passed validation")
            else:
                print(f"[ManimGenerator] ⚠ Validation issues: {validation.get('error')}")
            
            print(f"[ManimGenerator] Shot 2 complete: {len(code)} chars")
            return code
        else:
            print(f"[ManimGenerator] Shot 2 failed: {result.get('error')}")
            return None

    async def _generate_code_single_shot(
        self,
        section: Dict[str, Any],
        audio_duration: float,
        timing_context: str,
        language_instructions: str,
        color_instructions: str,
        type_guidance: str
    ) -> str:
        """Fallback single-shot code generation"""
        prompt = build_generation_prompt(
            section, audio_duration, timing_context,
            language_instructions, color_instructions, type_guidance
        )
        
        config = PromptConfig(enable_thinking=True, timeout=300.0)
        result = await self.code_engine.generate(prompt, config)
        
        if result["success"]:
            code = clean_code(result["response"])
            validation = self.validator.validate_code(code)
            
            if validation["valid"]:
                print("[ManimGenerator] ✓ Fallback code passed validation")
            else:
                print(f"[ManimGenerator] ⚠ Fallback validation issues")
            
            return code
        else:
            # Ultimate fallback
            return '''        text = Text("Section", font_size=48)
        self.play(Write(text))
        self.wait(2)'''

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
