"""
Visual Script Generator

Generates visual storyboards (Visual Scripts) from audio segments.
Uses the PromptingEngine with structured output for reliable JSON generation.

Flow:
1. Receives section with narration_segments (text + duration)
2. Generates visual descriptions for each segment
3. Determines appropriate post-narration pauses
4. Returns VisualScriptPlan for Manim generation
"""

import json
from typing import Dict, Any, Optional, List
from pathlib import Path

from app.services.infrastructure.llm import PromptingEngine, PromptConfig, CostTracker
from app.config.models import get_model_config

from .schemas import VisualScriptPlan, VisualSegment, get_schema
from .prompts import (
    VISUAL_SCRIPT_SYSTEM,
    build_user_prompt,
    build_audio_segments_from_section,
)
from .config import (
    GENERATION_TIMEOUT,
    GENERATION_TEMPERATURE,
    MAX_GENERATION_RETRIES,
    MAX_POST_PAUSE,
    MIN_POST_PAUSE,
)


class VisualScriptGenerator:
    """
    Generates Visual Scripts for animation planning.
    
    The Visual Script is a detailed storyboard that sits between
    script generation and Manim code generation. It provides:
    - Visual descriptions for each audio segment
    - Timing information including post-narration pauses
    - List of Manim objects to be used
    
    Usage:
        generator = VisualScriptGenerator()
        result = await generator.generate(section, source_context)
        if result.success:
            visual_script = result.visual_script
    """
    
    def __init__(
        self,
        cost_tracker: Optional[CostTracker] = None,
        pipeline_name: Optional[str] = None
    ):
        """
        Initialize the Visual Script Generator.
        
        Args:
            cost_tracker: Optional cost tracker for usage monitoring
            pipeline_name: Optional pipeline name for configuration
        """
        self.cost_tracker = cost_tracker or CostTracker()
        self.pipeline_name = pipeline_name
        
        # Initialize prompting engine for visual script generation
        self.engine = PromptingEngine(
            "visual_script_generation",
            self.cost_tracker,
            pipeline_name=pipeline_name
        )
        
        # System instruction
        self.system_instruction = VISUAL_SCRIPT_SYSTEM.template
    
    async def generate(
        self,
        section: Dict[str, Any],
        source_context: str = "",
        audio_segments: List[Dict[str, Any]] = None
    ) -> "GenerationResult":
        """
        Generate a Visual Script for a section.
        
        Args:
            section: Section dict with title, narration_segments, etc.
            source_context: Optional source material context
            audio_segments: Optional pre-built audio segments with actual durations
            
        Returns:
            GenerationResult with visual_script or error
        """
        section_title = section.get("title", "Untitled")
        
        # Use provided audio segments or build from section
        if audio_segments is None:
            audio_segments = build_audio_segments_from_section(section)
        
        if not audio_segments:
            return GenerationResult(
                success=False,
                error="No audio segments provided for visual script generation"
            )
        
        print(f"[VisualScriptGenerator] Generating visual script for '{section_title}' with {len(audio_segments)} segments")
        
        # Build user prompt
        user_prompt = build_user_prompt(
            section=section,
            source_context=source_context,
            audio_segments=audio_segments
        )
        
        # Get the structured output schema
        response_schema = get_schema()
        
        # Configure generation
        config = PromptConfig(
            temperature=GENERATION_TEMPERATURE,
            timeout=GENERATION_TIMEOUT,
            max_retries=MAX_GENERATION_RETRIES,
            response_format="json",
            enable_thinking=False,  # Structured output doesn't support thinking
        )
        
        try:
            # Call the LLM with structured output
            result = await self.engine.generate(
                prompt=user_prompt,
                config=config,
                system_instruction=self.system_instruction,
                response_schema=response_schema
            )
            
            if not result.get("success"):
                return GenerationResult(
                    success=False,
                    error=result.get("error", "Generation failed")
                )
            
            # Parse the response
            response_text = result.get("response", "")
            if not response_text:
                return GenerationResult(
                    success=False,
                    error="Empty response from LLM"
                )
            
            # Parse JSON response
            try:
                data = json.loads(response_text)
            except json.JSONDecodeError as e:
                return GenerationResult(
                    success=False,
                    error=f"Failed to parse JSON response: {e}"
                )
            
            # Validate and clamp pause values
            segments = data.get("segments", [])
            validated_segments = []
            
            for i, seg_data in enumerate(segments):
                # Clamp post_narration_pause to valid range
                pause = seg_data.get("post_narration_pause", 0.0)
                pause = max(MIN_POST_PAUSE, min(MAX_POST_PAUSE, pause))
                seg_data["post_narration_pause"] = pause
                
                # Ensure segment_id matches expected order
                seg_data["segment_id"] = i
                
                validated_segments.append(VisualSegment.from_dict(seg_data))
            
            # Create VisualScriptPlan
            visual_script = VisualScriptPlan(
                segments=validated_segments,
                section_title=data.get("section_title", section_title),
                style_notes=data.get("style_notes", "")
            )
            
            print(f"[VisualScriptGenerator] OK Generated visual script: {len(visual_script.segments)} segments, "
                  f"total duration: {visual_script.total_duration:.1f}s "
                  f"(audio: {visual_script.total_audio_duration:.1f}s, pauses: {visual_script.total_pause_duration:.1f}s)")
            
            return GenerationResult(
                success=True,
                visual_script=visual_script,
                raw_response=data
            )
            
        except Exception as e:
            print(f"[VisualScriptGenerator] ERROR: {e}")
            return GenerationResult(
                success=False,
                error=str(e)
            )
    
    async def generate_and_save(
        self,
        section: Dict[str, Any],
        output_dir: str,
        section_index: int,
        source_context: str = "",
        audio_segments: List[Dict[str, Any]] = None
    ) -> "GenerationResult":
        """
        Generate a Visual Script and save it to a file.
        
        Args:
            section: Section dict
            output_dir: Directory to save the visual script
            section_index: Index of the section
            source_context: Optional source material context
            audio_segments: Optional pre-built audio segments
            
        Returns:
            GenerationResult with visual_script and file paths
        """
        result = await self.generate(
            section=section,
            source_context=source_context,
            audio_segments=audio_segments
        )
        
        if not result.success:
            return result
        
        # Save files
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Save as JSON
        json_path = output_path / f"visual_script_{section_index}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(result.visual_script.to_dict(), f, indent=2)
        
        # Save as Markdown (human-readable)
        md_path = output_path / f"visual_script_{section_index}.md"
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(result.visual_script.to_markdown())
        
        result.json_path = str(json_path)
        result.markdown_path = str(md_path)
        
        print(f"[VisualScriptGenerator] Saved visual script to {json_path}")
        
        return result
    
    def get_cost_summary(self) -> Dict[str, Any]:
        """Get cost summary from the cost tracker"""
        return self.cost_tracker.get_summary()


class GenerationResult:
    """Result from visual script generation"""
    
    def __init__(
        self,
        success: bool,
        visual_script: Optional[VisualScriptPlan] = None,
        error: Optional[str] = None,
        raw_response: Optional[Dict] = None,
        json_path: Optional[str] = None,
        markdown_path: Optional[str] = None
    ):
        self.success = success
        self.visual_script = visual_script
        self.error = error
        self.raw_response = raw_response
        self.json_path = json_path
        self.markdown_path = markdown_path
    
    def __repr__(self) -> str:
        if self.success:
            return f"GenerationResult(success=True, segments={len(self.visual_script.segments) if self.visual_script else 0})"
        return f"GenerationResult(success=False, error={self.error})"


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def update_audio_segments_with_actual_durations(
    section: Dict[str, Any],
    actual_durations: List[float]
) -> List[Dict[str, Any]]:
    """
    Update audio segments with actual TTS durations after audio generation.
    
    This should be called after audio generation to get accurate timing
    for visual script generation.
    
    Args:
        section: Section dict with narration_segments
        actual_durations: List of actual audio durations in seconds
        
    Returns:
        Updated audio segments list
    """
    segments = section.get("narration_segments", [])
    audio_segments = []
    
    for i, seg in enumerate(segments):
        duration = actual_durations[i] if i < len(actual_durations) else seg.get("estimated_duration", 5.0)
        audio_segments.append({
            "text": seg.get("text", ""),
            "duration": duration
        })
    
    return audio_segments


def load_visual_script(file_path: str) -> Optional[VisualScriptPlan]:
    """
    Load a visual script from a JSON file.
    
    Args:
        file_path: Path to the visual script JSON file
        
    Returns:
        VisualScriptPlan or None if loading fails
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return VisualScriptPlan.from_dict(data)
    except Exception as e:
        print(f"[VisualScriptGenerator] Failed to load visual script: {e}")
        return None
