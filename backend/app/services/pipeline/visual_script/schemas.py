"""
Visual Script Schemas

Defines the structured output schemas for visual script generation.
Uses Gemini API types.Schema format for structured JSON output.

These schemas define:
- VisualSegment: Individual segment with visual description and timing
- VisualScriptPlan: Complete visual storyboard for a section
"""

from typing import List, Optional
from dataclasses import dataclass, field
from app.services.infrastructure.llm.gemini import get_types_module


# =============================================================================
# DATACLASS MODELS (for internal use)
# =============================================================================

@dataclass
class VisualSegment:
    """
    A single segment of the visual script corresponding to one audio segment.
    
    Attributes:
        segment_id: Sequential index of the audio segment (0-based)
        narration_text: The exact spoken text for this segment
        visual_description: Detailed instructions for the Manim animator
        visual_elements: List of Manim objects needed
        audio_duration: Length of the audio segment in seconds
        post_narration_pause: Extra time to hold frame after audio ends
    """
    segment_id: int
    narration_text: str
    visual_description: str
    visual_elements: List[str]
    audio_duration: float
    post_narration_pause: float = 0.0
    
    @property
    def total_duration(self) -> float:
        """Total duration including pause"""
        return self.audio_duration + self.post_narration_pause
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "segment_id": self.segment_id,
            "narration_text": self.narration_text,
            "visual_description": self.visual_description,
            "visual_elements": self.visual_elements,
            "audio_duration": self.audio_duration,
            "post_narration_pause": self.post_narration_pause,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "VisualSegment":
        """Create from dictionary"""
        return cls(
            segment_id=data.get("segment_id", 0),
            narration_text=data.get("narration_text", ""),
            visual_description=data.get("visual_description", ""),
            visual_elements=data.get("visual_elements", []),
            audio_duration=data.get("audio_duration", 0.0),
            post_narration_pause=data.get("post_narration_pause", 0.0),
        )


@dataclass
class VisualScriptPlan:
    """
    Complete visual script for a section.
    
    Attributes:
        segments: List of visual segments
        total_duration: Sum of all segment durations (including pauses)
        section_title: Title of the section
        style_notes: Optional notes about visual style
    """
    segments: List[VisualSegment] = field(default_factory=list)
    section_title: str = ""
    style_notes: str = ""
    
    @property
    def total_duration(self) -> float:
        """Total duration of all segments"""
        return sum(seg.total_duration for seg in self.segments)
    
    @property
    def total_audio_duration(self) -> float:
        """Total audio duration (without pauses)"""
        return sum(seg.audio_duration for seg in self.segments)
    
    @property
    def total_pause_duration(self) -> float:
        """Total pause duration"""
        return sum(seg.post_narration_pause for seg in self.segments)
    
    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "segments": [seg.to_dict() for seg in self.segments],
            "section_title": self.section_title,
            "style_notes": self.style_notes,
            "total_duration": self.total_duration,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "VisualScriptPlan":
        """Create from dictionary"""
        segments = [
            VisualSegment.from_dict(seg) 
            for seg in data.get("segments", [])
        ]
        return cls(
            segments=segments,
            section_title=data.get("section_title", ""),
            style_notes=data.get("style_notes", ""),
        )
    
    def to_markdown(self) -> str:
        """Convert to readable markdown format"""
        lines = [
            f"# Visual Script: {self.section_title}",
            "",
            f"**Total Duration:** {self.total_duration:.1f}s (Audio: {self.total_audio_duration:.1f}s + Pauses: {self.total_pause_duration:.1f}s)",
            "",
        ]
        
        if self.style_notes:
            lines.extend([
                "## Style Notes",
                self.style_notes,
                "",
            ])
        
        lines.append("## Segments")
        lines.append("")
        
        cumulative_time = 0.0
        for seg in self.segments:
            end_time = cumulative_time + seg.total_duration
            lines.extend([
                f"### Segment {seg.segment_id + 1} [{cumulative_time:.1f}s - {end_time:.1f}s]",
                "",
                f"**Narration:** \"{seg.narration_text}\"",
                "",
                f"**Audio Duration:** {seg.audio_duration:.1f}s | **Post-Pause:** {seg.post_narration_pause:.1f}s",
                "",
                f"**Visual Description:**",
                seg.visual_description,
                "",
                f"**Visual Elements:** {', '.join(seg.visual_elements) if seg.visual_elements else 'None specified'}",
                "",
                "---",
                "",
            ])
            cumulative_time = end_time
        
        return "\n".join(lines)


# =============================================================================
# GEMINI STRUCTURED OUTPUT SCHEMA
# =============================================================================

def get_visual_script_schema():
    """
    Get the Gemini types.Schema for structured visual script output.
    
    Uses genai.types.Schema format as specified in the project standards.
    This schema is used with response_mime_type="application/json" for
    guaranteed structured output.
    """
    types = get_types_module()
    
    # Build the schema using genai.types.Schema
    schema = types.Schema(
        type=types.Type.OBJECT,
        required=["segments"],
        properties={
            "segments": types.Schema(
                type=types.Type.ARRAY,
                description="List of visual segments, one per audio segment",
                items=types.Schema(
                    type=types.Type.OBJECT,
                    required=[
                        "segment_id",
                        "narration_text",
                        "visual_description",
                        "visual_elements",
                        "audio_duration",
                        "post_narration_pause"
                    ],
                    properties={
                        "segment_id": types.Schema(
                            type=types.Type.INTEGER,
                            description="Sequential index of the audio segment (0-based)"
                        ),
                        "narration_text": types.Schema(
                            type=types.Type.STRING,
                            description="The exact spoken text for this segment"
                        ),
                        "visual_description": types.Schema(
                            type=types.Type.STRING,
                            description=(
                                "Detailed, director-level instructions for the Manim animator. "
                                "Specify geometric shapes, colors (Red, Blue, Yellow), "
                                "positions (UP, DOWN, LEFT, RIGHT), and transformations "
                                "(Transform, FadeIn, Write). Do NOT write code, write the plan."
                            )
                        ),
                        "visual_elements": types.Schema(
                            type=types.Type.ARRAY,
                            description="List of Manim objects needed (e.g., 'Circle', 'MathTex', 'NumberLine')",
                            items=types.Schema(type=types.Type.STRING)
                        ),
                        "audio_duration": types.Schema(
                            type=types.Type.NUMBER,
                            description="Length of the audio segment in seconds (from input)"
                        ),
                        "post_narration_pause": types.Schema(
                            type=types.Type.NUMBER,
                            description=(
                                "CRITICAL: Extra time in seconds to hold frame AFTER audio ends. "
                                "For complex animations (writing equations, graph transforms), use 1.5-3.0s. "
                                "For simple static visuals, use 0.0s."
                            )
                        ),
                    }
                )
            ),
            "section_title": types.Schema(
                type=types.Type.STRING,
                description="Title of the section being animated"
            ),
            "style_notes": types.Schema(
                type=types.Type.STRING,
                description="Optional notes about visual style, color themes, or layout preferences"
            ),
        }
    )
    
    return schema


# For backward compatibility - lazy evaluation
VISUAL_SCRIPT_PLAN_SCHEMA = None

def get_schema():
    """Get or create the visual script schema (lazy initialization)"""
    global VISUAL_SCRIPT_PLAN_SCHEMA
    if VISUAL_SCRIPT_PLAN_SCHEMA is None:
        VISUAL_SCRIPT_PLAN_SCHEMA = get_visual_script_schema()
    return VISUAL_SCRIPT_PLAN_SCHEMA
