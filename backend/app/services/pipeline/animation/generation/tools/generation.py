"""
Generation Tools - Agentic Manim code generation

Uses Gemini function calling for agentic iteration:
- Model has access to generate_code and fix_code tools
- Tools validate and return feedback
- Model iterates until code is valid or max attempts reached
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from .schemas import GENERATE_CODE_SCHEMA
from .context import build_context, ManimContext


@dataclass
class GenerationResult:
    """Result from code generation tool"""
    success: bool
    code: Optional[str] = None
    visual_script: Optional[Dict] = None
    error: Optional[str] = None
    validation: Optional[Dict] = None
    iterations: int = 0
    feedback_history: Optional[List[str]] = None
    
    def __post_init__(self):
        """Initialize feedback_history if None"""
        if self.feedback_history is None:
            self.feedback_history = []


class GenerationToolHandler:
    """
    Agentic Manim code generation using tool calling.
    
    Flow:
    1. Model generates code via generate_manim_code tool
    2. Tool validates and returns feedback
    3. If invalid, model uses fix_manim_code tool with feedback
    4. Loop until code valid or max iterations reached
    5. Model controls iteration via tool calls
    """
    
    MAX_ITERATIONS = 5
    
    def __init__(self, engine, validator):
        """
        Args:
            engine: PromptingEngine instance
            validator: CodeValidator instance
        """
        self.engine = engine
        self.validator = validator
        self._feedback_history = []
    
    async def generate(
        self,
        section: Dict[str, Any],
        style: str = "3b1b",
        target_duration: float = 30.0,
        language: str = "en",
        use_visual_script: bool = True
    ) -> GenerationResult:
        """
        Agentic code generation with tool-based iteration.
        
        Args:
            section: Section data with narration, title, etc.
            style: Visual style name
            target_duration: Target duration in seconds
            language: Language code
            use_visual_script: Whether to use 2-shot with visual script
            
        Returns:
            GenerationResult with code or error
        """
        # Reset feedback history
        self._feedback_history = []
        
        # Detect animation type from section
        animation_type = self._detect_animation_type(section)
        
        # Build context
        context = build_context(
            style=style,
            animation_type=animation_type,
            target_duration=target_duration,
            language=language
        )
        
        # Build initial system prompt
        _ = self._build_system_prompt(context)

        # Build initial user prompt
        user_prompt = self._build_generation_prompt(section, context)
        
        # Run agentic loop
        from app.services.infrastructure.llm import PromptConfig
        from app.services.infrastructure.llm.gemini import get_types_module
        
        config = PromptConfig(
            temperature=0.7,
            timeout=300,
            enable_thinking=False  # Disable thinking for agentic iteration
        )
        
        code = None
        iteration = 0
        
        try:
            # Agentic loop - model calls tools and gets feedback
            while iteration < self.MAX_ITERATIONS:
                iteration += 1
                
                # Get available tools
                tools = self._get_tools(get_types_module())
                
                # Call model with tools available
                response = await self.engine.generate(
                    prompt=user_prompt,
                    config=config,
                    tools=tools
                )
                
                if not response.get("success"):
                    return GenerationResult(
                        success=False,
                        error=response.get("error", "Model call failed"),
                        iterations=iteration,
                        feedback_history=self._feedback_history
                    )
                
                # Extract function calls from response
                function_calls = response.get("function_calls", [])
                
                if not function_calls:
                    # Model didn't call tools - extract code from text if available
                    text_response = response.get("response", "")
                    code = self._extract_code_from_response(text_response)
                    if code:
                        validation = self.validator.validate_code(code)
                        if validation["valid"]:
                            return GenerationResult(
                                success=True,
                                code=code,
                                validation=validation,
                                iterations=iteration,
                                feedback_history=self._feedback_history
                            )
                    return GenerationResult(
                        success=False,
                        error="Model did not use tools",
                        iterations=iteration,
                        feedback_history=self._feedback_history
                    )
                
                # Process first function call
                func_call = function_calls[0]
                func_name = func_call.get("name", "")
                func_args = func_call.get("args", {})
                
                # Validate code from tool call
                code = func_args.get("code", "")
                if not code:
                    return GenerationResult(
                        success=False,
                        error=f"Tool '{func_name}' returned no code",
                        iterations=iteration,
                        feedback_history=self._feedback_history
                    )
                
                validation = self.validator.validate_code(code)
                
                if validation["valid"]:
                    # Success!
                    return GenerationResult(
                        success=True,
                        code=code,
                        validation=validation,
                        iterations=iteration,
                        feedback_history=self._feedback_history
                    )
                else:
                    # Invalid code - prepare feedback for next iteration
                    error_msg = validation.get("error", "Code validation failed")
                    feedback = f"Validation failed:\n{error_msg}"
                    self._feedback_history.append(feedback)
                    
                    # Update prompt with feedback for next iteration
                    user_prompt = f"Previous attempt had validation errors:\n\n{feedback}\n\nUse fix_manim_code tool to correct the code."
            
            # Max iterations reached
            return GenerationResult(
                success=False,
                code=code,
                error=f"Max iterations ({self.MAX_ITERATIONS}) reached without valid code",
                iterations=iteration,
                feedback_history=self._feedback_history
            )
                
        except Exception as e:
            return GenerationResult(
                success=False,
                error=f"Generation failed: {str(e)}",
                iterations=iteration,
                feedback_history=self._feedback_history
            )
    
    
    def _get_tools(self, types_module) -> List[Any]:
        """Get available tools for agentic generation"""
        return [
            types_module.Tool(
                function_declarations=[
                    types_module.FunctionDeclaration(
                        name="generate_manim_code",
                        description="Generate complete Manim animation code. Code will be validated and feedback returned.",
                        parameters=GENERATE_CODE_SCHEMA
                    ),
                    types_module.FunctionDeclaration(
                        name="fix_manim_code",
                        description="Fix Manim code that had validation errors. Provide corrected code.",
                        parameters=GENERATE_CODE_SCHEMA
                    ),
                ]
            )
        ]
    
    def _extract_code_from_response(self, response: str) -> Optional[str]:
        """Try to extract code from text response"""
        if not response:
            return None
        
        # Try to find code block or code-like content
        import re
        # Look for python code pattern
        pattern = r'```python\n(.*)\n```'
        match = re.search(pattern, response, re.DOTALL)
        if match:
            return match.group(1)
        
        # If no markdown, return the whole response if it looks like code
        if "self.play" in response or "self.wait" in response:
            return response
        
        return None
    
    
    def _build_system_prompt(self, context: ManimContext) -> str:
        """Build system prompt for agentic generation"""
        return f"""{context.to_system_prompt()}

TOOL-BASED ITERATION:
You have two tools: generate_manim_code and fix_manim_code

PROCESS:
1. Call generate_manim_code with your best attempt
2. You'll receive validation feedback
3. If there are errors, call fix_manim_code with corrections
4. Iterate until code validates or max attempts reached

CRITICAL: Only use the tools to submit code. Do NOT write code in messages.
Each tool call returns validation results to guide your fixes."""
    
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
        
        return f"""Use the generate_manim_code tool to create animation code for this section:

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
