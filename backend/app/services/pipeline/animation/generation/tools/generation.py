"""
Generation Tools - Agentic Manim code generation

Uses Gemini function calling for agentic iteration:
- Model has access to write_code and fix_code tools
- Tools validate and return feedback
- Model iterates until code is valid or max attempts reached

Responsibilities:
- Orchestrate LLM calls for code generation
- Handle tool responses and validation loops
- Manage retry logic with feedback

Delegates to:
- code_manipulation.py: Code extraction and fix application
- context.py: Prompt building and context management
- validation/: Code validation
"""

from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from .schemas import WRITE_CODE_SCHEMA, FIX_CODE_SCHEMA
from .context import build_context, ManimContext
from .code_manipulation import extract_code_from_response, apply_fixes
from ...config import (
    MAX_GENERATION_ITERATIONS,
    GENERATION_TIMEOUT,
    CORRECTION_TIMEOUT,
    BASE_GENERATION_TEMPERATURE,
    BASE_CORRECTION_TEMPERATURE,
    TEMPERATURE_INCREMENT
)
from ...prompts import FIX_CODE_USER, FIX_CODE_RETRY_USER, GENERATION_RETRY_USER, format_section_context


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
    
    def __init__(self, engine, validator):
        """
        Args:
            engine: PromptingEngine instance
            validator: CodeValidator instance
        """
        self.engine = engine
        self.validator = validator
        self._feedback_history = []
        self.MAX_ITERATIONS = MAX_GENERATION_ITERATIONS
    
    async def fix(
        self,
        code: str,
        error_message: str,
        section: Optional[Dict[str, Any]] = None,
        attempt: int = 0
    ) -> GenerationResult:
        """
        Fix code errors using write_code or fix_code tools.
        
        LLM can choose:
        - write_code: Full replacement (for major issues)
        - fix_code: Targeted search/replace (for small fixes)
        
        Args:
            code: Current code with errors
            error_message: Error message (from Manim, validator, etc.)
            section: Optional section context
            attempt: Current attempt number
            
        Returns:
            GenerationResult with fixed code or error
        """
        # Reset feedback history
        self._feedback_history = []
        
        # Build fix prompt using template
        user_prompt = FIX_CODE_USER.format(
            error_message=error_message,
            context_info=format_section_context(section),
            code=code
        )
        
        # Run fix loop
        from app.services.infrastructure.llm import PromptConfig
        from app.services.infrastructure.llm.gemini import get_types_module
        
        config = PromptConfig(
            temperature=BASE_CORRECTION_TEMPERATURE + (attempt * TEMPERATURE_INCREMENT),
            timeout=CORRECTION_TIMEOUT,
            enable_thinking=False
        )
        
        iteration = 0
        current_code = code
        
        try:
            while iteration < self.MAX_ITERATIONS:
                iteration += 1
                
                # Get tools
                tools = self._get_tools(get_types_module())
                
                # Call model
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
                
                # Extract function calls
                function_calls = response.get("function_calls", [])
                
                if not function_calls:
                    # Try to extract code from text
                    text_response = response.get("response", "")
                    fixed_code = extract_code_from_response(text_response)
                    if fixed_code:
                        validation = self.validator.validate_code(fixed_code)
                        if validation["valid"]:
                            return GenerationResult(
                                success=True,
                                code=fixed_code,
                                validation=validation,
                                iterations=iteration,
                                feedback_history=self._feedback_history
                            )
                    return GenerationResult(
                        success=False,
                        error="Model did not use fix_manim_code tool",
                        iterations=iteration,
                        feedback_history=self._feedback_history
                    )
                
                # Process function call
                func_call = function_calls[0]
                func_name = func_call.get("name", "")
                func_args = func_call.get("args", {})
                
                # Handle write_code (full replacement)
                if func_name == "write_code":
                    fixed_code = func_args.get("code", "")
                    if not fixed_code:
                        return GenerationResult(
                            success=False,
                            error="write_code tool returned no code",
                            iterations=iteration,
                            feedback_history=self._feedback_history
                        )
                
                # Handle fix_code (diff-based)
                elif func_name == "fix_code":
                    fixes = func_args.get("fixes", [])
                    if not fixes:
                        return GenerationResult(
                            success=False,
                            error="fix_code tool returned no fixes",
                            iterations=iteration,
                            feedback_history=self._feedback_history
                        )
                    
                    # Apply fixes to current code
                    fixed_code, applied, details = apply_fixes(current_code, fixes)
                    
                    if applied == 0:
                        error_details = "\n".join(details) if details else "No details"
                        return GenerationResult(
                            success=False,
                            error=f"No fixes could be applied:\n{error_details}",
                            iterations=iteration,
                            feedback_history=self._feedback_history
                        )
                    
                    # Log applied fixes
                    for detail in details:
                        print(f"[GenerationToolHandler] {detail}")
                
                else:
                    return GenerationResult(
                        success=False,
                        error=f"Model did not use write_code or fix_code tool (used: {func_name})",
                        iterations=iteration,
                        feedback_history=self._feedback_history
                    )
                
                # Validate
                validation = self.validator.validate_code(fixed_code)
                
                if validation["valid"]:
                    # Success!
                    return GenerationResult(
                        success=True,
                        code=fixed_code,
                        validation=validation,
                        iterations=iteration,
                        feedback_history=self._feedback_history
                    )
                else:
                    # Still invalid, prepare feedback
                    error_msg = validation.get("error", "Code validation failed")
                    feedback = f"Fix attempt had validation errors:\n{error_msg}"
                    self._feedback_history.append(feedback)
                    
                    # Update current_code and prompt for next iteration
                    current_code = fixed_code
                    user_prompt = FIX_CODE_RETRY_USER.format(
                        feedback=feedback,
                        code=current_code
                    )
            
            # Max iterations reached
            return GenerationResult(
                success=False,
                code=fixed_code if 'fixed_code' in locals() else None,
                error=f"Max iterations ({self.MAX_ITERATIONS}) reached without valid fix",
                iterations=iteration,
                feedback_history=self._feedback_history
            )
            
        except Exception as e:
            return GenerationResult(
                success=False,
                error=f"Fix failed: {str(e)}",
                iterations=iteration,
                feedback_history=self._feedback_history
            )
    
    async def generate(
        self,
        section: Dict[str, Any],
        style: str = "3b1b",
        target_duration: float = 30.0,
        language: str = "en",
        visual_script = None
    ) -> GenerationResult:
        """
        Agentic code generation with tool-based iteration.
        
        Args:
            section: Section data with narration, title, etc.
            style: Visual style name
            target_duration: Target duration in seconds
            language: Language code
            visual_script: Optional VisualScriptPlan for guided generation
            
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

        # Build initial user prompt - use visual script if available
        if visual_script is not None:
            user_prompt = self._build_generation_prompt_with_visual_script(section, context, visual_script)
        else:
            user_prompt = self._build_generation_prompt(section, context)
        
        # Run agentic loop
        from app.services.infrastructure.llm import PromptConfig
        from app.services.infrastructure.llm.gemini import get_types_module
        
        config = PromptConfig(
            temperature=BASE_GENERATION_TEMPERATURE,
            timeout=GENERATION_TIMEOUT,
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
                    code = extract_code_from_response(text_response)
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
                
                # Handle write_code (full replacement)
                if func_name in ["write_code", "generate_manim_code"]:  # Support old name
                    code = func_args.get("code", "")
                    if not code:
                        return GenerationResult(
                            success=False,
                            error=f"Tool '{func_name}' returned no code",
                            iterations=iteration,
                            feedback_history=self._feedback_history
                        )
                
                # Handle fix_code (diff-based)
                elif func_name == "fix_code":
                    fixes = func_args.get("fixes", [])
                    if not fixes:
                        return GenerationResult(
                            success=False,
                            error="fix_code tool returned no fixes",
                            iterations=iteration,
                            feedback_history=self._feedback_history
                        )
                    
                    # Apply fixes to current code
                    code, applied, details = apply_fixes(code, fixes)
                    
                    if applied == 0:
                        error_details = "\n".join(details) if details else "No details"
                        return GenerationResult(
                            success=False,
                            error=f"No fixes could be applied:\n{error_details}",
                            iterations=iteration,
                            feedback_history=self._feedback_history
                        )
                    
                    # Log applied fixes
                    for detail in details:
                        print(f"[GenerationToolHandler] {detail}")
                
                else:
                    return GenerationResult(
                        success=False,
                        error=f"Unknown tool: {func_name}",
                        iterations=iteration,
                        feedback_history=self._feedback_history
                    )
                
                # Validate resulting code
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
                    user_prompt = GENERATION_RETRY_USER.format(
                        feedback=feedback,
                        code=code
                    )
            
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
        """Get available tools: write_code (full replacement) and fix_code (diff-based)"""
        return [
            types_module.Tool(
                function_declarations=[
                    types_module.FunctionDeclaration(
                        name="write_code",
                        description="Write complete Manim animation code (full replacement). Use for initial generation or major rewrites. Code will be validated and feedback returned.",
                        parameters=WRITE_CODE_SCHEMA
                    ),
                    types_module.FunctionDeclaration(
                        name="fix_code",
                        description="Fix Manim code using targeted search/replace operations. Use for surgical fixes to preserve working code. Each fix will be validated.",
                        parameters=FIX_CODE_SCHEMA
                    ),
                ]
            )
        ]
    
    def _build_system_prompt(self, context: ManimContext) -> str:
        """Build system prompt for agentic generation"""
        from app.services.pipeline.animation.prompts import AGENTIC_GENERATION_SYSTEM
        return AGENTIC_GENERATION_SYSTEM.format(manim_context=context.to_system_prompt())
    
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
        """Build the user prompt for generation (without visual script)"""
        from app.services.pipeline.animation.prompts import AGENTIC_GENERATION_USER, format_timing_context
        
        title = section.get("title", "Section")
        narration = section.get("narration", section.get("tts_narration", ""))
        visual_desc = section.get("visual_description", "")
        
        return AGENTIC_GENERATION_USER.format(
            title=title,
            narration=narration[:500],
            visual_description=visual_desc[:300] if visual_desc else 'Create appropriate visuals for the narration',
            timing_context=format_timing_context(section),
            target_duration=context.target_duration
        )
    
    def _build_generation_prompt_with_visual_script(
        self,
        section: Dict[str, Any],
        context: ManimContext,
        visual_script
    ) -> str:
        """
        Build the user prompt for generation with visual script.
        
        Uses the detailed visual script for precise timing and visual guidance.
        
        Args:
            section: Section data
            context: Manim context
            visual_script: VisualScriptPlan with segment details
            
        Returns:
            Formatted prompt string
        """
        from app.services.pipeline.animation.prompts import (
            AGENTIC_GENERATION_WITH_VISUAL_SCRIPT_USER,
            format_visual_script_for_prompt,
            format_segment_timing_for_prompt,
        )
        
        title = section.get("title", "Section")
        
        return AGENTIC_GENERATION_WITH_VISUAL_SCRIPT_USER.format(
            title=title,
            target_duration=context.target_duration,
            visual_script=format_visual_script_for_prompt(visual_script),
            segment_timing=format_segment_timing_for_prompt(visual_script)
        )
