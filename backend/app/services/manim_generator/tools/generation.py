"""
Generation Tools - Tool-based Manim code generation

Uses Gemini function calling for structured, reliable code generation.
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from .schemas import GENERATE_CODE_SCHEMA, VISUAL_SCRIPT_SCHEMA
from .context import build_context, get_manim_reference, ManimContext


@dataclass
class GenerationResult:
    """Result from code generation tool"""
    success: bool
    code: Optional[str] = None
    visual_script: Optional[Dict] = None
    error: Optional[str] = None
    validation: Optional[Dict] = None


class GenerationToolHandler:
    """
    Handles Manim code generation using tool calling.
    
    Flow:
    1. Build context (style, timing, language)
    2. Generate visual script (optional 2-shot)
    3. Generate Manim code
    4. Validate code
    """
    
    def __init__(self, engine, validator):
        """
        Args:
            engine: PromptingEngine instance
            validator: CodeValidator instance
        """
        self.engine = engine
        self.validator = validator
    
    def get_tools(self, types_module) -> List[Any]:
        """
        Get Gemini tool declarations for generation.
        
        Args:
            types_module: Gemini types module
            
        Returns:
            List of Tool declarations for Gemini API
        """
        return [
            types_module.Tool(
                function_declarations=[
                    types_module.FunctionDeclaration(
                        name="generate_manim_code",
                        description="Generate complete Manim animation code for the construct() method",
                        parameters=GENERATE_CODE_SCHEMA
                    ),
                    types_module.FunctionDeclaration(
                        name="create_visual_script",
                        description="Create a visual storyboard with timing for the animation",
                        parameters=VISUAL_SCRIPT_SCHEMA
                    ),
                ]
            )
        ]
    
    async def generate(
        self,
        section: Dict[str, Any],
        style: str = "3b1b",
        target_duration: float = 30.0,
        language: str = "en",
        use_visual_script: bool = True
    ) -> GenerationResult:
        """
        Generate Manim code for a section.
        
        Args:
            section: Section data with narration, title, etc.
            style: Visual style name
            target_duration: Target duration in seconds
            language: Language code
            use_visual_script: Whether to use 2-shot with visual script
            
        Returns:
            GenerationResult with code or error
        """
        # Detect animation type from section
        animation_type = self._detect_animation_type(section)
        
        # Build context
        context = build_context(
            style=style,
            animation_type=animation_type,
            target_duration=target_duration,
            language=language
        )
        
        # Build user prompt
        user_prompt = self._build_generation_prompt(section, context)
        
        # Generate with function calling
        from app.services.prompting_engine import PromptConfig
        
        config = PromptConfig(
            temperature=0.7,
            max_output_tokens=4096,
            timeout=120,
            response_format="json"
        )
        
        try:
            response = await self.engine.generate(
                prompt=user_prompt,
                config=config,
                system_prompt=context.to_system_prompt(),
                response_schema=GENERATE_CODE_SCHEMA
            )
            
            if not response:
                return GenerationResult(success=False, error="Empty response from LLM")
            
            # Parse response
            import json
            if isinstance(response, str):
                result = json.loads(response)
            else:
                result = response
            
            code = result.get("code", "")
            
            # Validate
            validation = self.validator.validate_code(code)
            
            if validation["valid"]:
                return GenerationResult(
                    success=True,
                    code=code,
                    validation=validation
                )
            else:
                return GenerationResult(
                    success=False,
                    code=code,
                    error=validation.get("error", "Validation failed"),
                    validation=validation
                )
                
        except Exception as e:
            return GenerationResult(
                success=False,
                error=f"Generation failed: {str(e)}"
            )
    
    def _detect_animation_type(self, section: Dict[str, Any]) -> str:
        """Detect animation type from section content"""
        narration = section.get("narration", "").lower()
        visual_desc = section.get("visual_description", "").lower()
        content = narration + " " + visual_desc
        
        if any(kw in content for kw in ["equation", "formula", "integral", "derivative", "x^2", "fraction"]):
            return "equation"
        elif any(kw in content for kw in ["graph", "plot", "axes", "function"]):
            return "graph"
        elif any(kw in content for kw in ["diagram", "chart", "flow", "arrow"]):
            return "diagram"
        elif any(kw in content for kw in ["code", "function", "class", "variable"]):
            return "code"
        else:
            return "text"
    
    def _build_generation_prompt(self, section: Dict[str, Any], context: ManimContext) -> str:
        """Build the user prompt for generation"""
        title = section.get("title", "Section")
        narration = section.get("narration", section.get("tts_narration", ""))
        visual_desc = section.get("visual_description", "")
        
        # Build timing context from segments if available
        timing_context = ""
        if "segments" in section:
            segments = section["segments"]
            timing_lines = []
            cumulative = 0.0
            for seg in segments:
                seg_duration = seg.get("duration", 5.0)
                seg_text = seg.get("tts_text", seg.get("narration", ""))[:50]
                timing_lines.append(f"  [{cumulative:.1f}s-{cumulative + seg_duration:.1f}s]: \"{seg_text}...\"")
                cumulative += seg_duration
            timing_context = "TIMING:\n" + "\n".join(timing_lines)
        
        return f"""Generate Manim code for this section:

TITLE: {title}

NARRATION:
{narration[:500]}

VISUAL DESCRIPTION:
{visual_desc[:300] if visual_desc else 'Create appropriate visuals for the narration'}

{timing_context}

TARGET DURATION: {context.target_duration} seconds

Generate the construct() method body that creates engaging animations matching the narration.
Use self.wait() to sync with narration timing.
"""


def create_generation_tools(engine, validator) -> GenerationToolHandler:
    """Create generation tool handler"""
    return GenerationToolHandler(engine, validator)
