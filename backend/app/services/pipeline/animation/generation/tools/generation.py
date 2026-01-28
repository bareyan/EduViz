"""
Generation Tools - Agentic Manim code generation

Uses Gemini function calling for agentic iteration:
- Model has access to write_manim_code and patch_manim_code tools
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

from .schemas import WRITE_CODE_SCHEMA, PATCH_CODE_SCHEMA
from .context import build_context, ManimContext
from .code_manipulation import extract_code_from_response, apply_patches
from app.services.infrastructure.llm.prompting_engine.base_engine import PromptConfig
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
    1. Model generates code via write_manim_code tool
    2. Tool validates and returns feedback
    3. If invalid, model uses patch_manim_code tool with feedback
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
    
    async def generate(
        self,
        section: Dict[str, Any],
        style: str = "3b1b",
        target_duration: float = 30.0,
        language: str = "en",
        visual_script = None
    ) -> GenerationResult:
        """
        Agentic code generation with unified tool-based iteration.
        """
        # 1. Setup Context
        animation_type = self._detect_animation_type(section)
        context = build_context(
            style=style,
            animation_type=animation_type,
            target_duration=target_duration,
            language=language
        )
        
        # 2. Build Prompts
        if visual_script is not None:
            user_prompt = self._build_generation_prompt_with_visual_script(section, context, visual_script)
        else:
            user_prompt = self._build_generation_prompt(section, context)
            
        system_prompt = self._build_system_prompt(context)
        
        # 3. Configure Thinking (CoT)
        config = PromptConfig(
            temperature=BASE_GENERATION_TEMPERATURE,
            timeout=GENERATION_TIMEOUT,
            enable_thinking=True, # Enable thinking for better reasoning
            system_instruction=system_prompt
        )
        
        # 4. Execute Unified Loop
        return await self._run_loop(user_prompt, config, initial_code=None)

    async def fix(
        self,
        code: str,
        error_message: str,
        section: Optional[Dict[str, Any]] = None,
        attempt: int = 0
    ) -> GenerationResult:
        """
        Fix code errors using the unified agentic loop.
        """
        # 1. Setup Context (for system prompt)
        animation_type = self._detect_animation_type(section) if section else "text"
        context = build_context(animation_type=animation_type)
        from app.services.pipeline.animation.prompts import TOOL_CORRECTION_SYSTEM
        system_prompt = TOOL_CORRECTION_SYSTEM.format(manim_context=context.to_system_prompt())

        # 2. Build User Prompt
        user_prompt = FIX_CODE_USER.format(
            error_message=error_message,
            context_info=format_section_context(section),
            code=code
        )
        
        # 3. Configure
        config = PromptConfig(
            temperature=BASE_CORRECTION_TEMPERATURE + (attempt * TEMPERATURE_INCREMENT),
            timeout=CORRECTION_TIMEOUT,
            enable_thinking=True, # Thinking helps solve errors
            system_instruction=system_prompt
        )
        
        return await self._run_loop(user_prompt, config, initial_code=code)

    async def _run_loop(
        self,
        prompt: str,
        config: PromptConfig,
        initial_code: Optional[str] = None
    ) -> GenerationResult:
        """
        The core agentic loop: Model calls tools -> Validation -> Feedback -> Loop.
        """
        from app.services.infrastructure.llm.gemini import get_types_module
        
        self._feedback_history = []
        current_code = initial_code
        user_prompt = prompt
        iteration = 0
        
        try:
            while iteration < self.MAX_ITERATIONS:
                iteration += 1
                
                # Call model with standardized tools
                response = await self.engine.generate(
                    prompt=user_prompt,
                    config=config,
                    tools=self._get_tools(get_types_module())
                )
                
                if not response.get("success"):
                    return GenerationResult(
                        success=False,
                        error=response.get("error", "Model interaction failed"),
                        iterations=iteration,
                        feedback_history=self._feedback_history
                    )
                
                function_calls = response.get("function_calls", [])
                
                # 1. Handle Text-only Fallback (if no tool used)
                if not function_calls:
                    code = extract_code_from_response(response.get("response", ""))
                    if code:
                        validation = self.validator.validate_code(code)
                        if validation["valid"]:
                            return GenerationResult(success=True, code=code, validation=validation, iterations=iteration)
                        # If invalid text code, feed back and continue loop
                        feedback = f"Validation failed:\n{validation.get('error')}"
                        self._feedback_history.append(feedback)
                        user_prompt = GENERATION_RETRY_USER.format(feedback=feedback, code=code)
                        current_code = code
                        continue
                    
                    return GenerationResult(success=False, error="Model did not use tools or provide code", iterations=iteration)

                # 2. Process Tools (Standardized Names)
                func_call = function_calls[0]
                name = func_call.get("name")
                args = func_call.get("args", {})
                
                if name == "write_manim_code":
                    new_code = args.get("code", "")
                elif name == "patch_manim_code":
                    if not current_code:
                        # LLM tried to patch nothing
                        feedback = "Error: Cannot use patch_manim_code without existing code. Use write_manim_code first."
                        self._feedback_history.append(feedback)
                        user_prompt = f"{feedback}\n\nOriginal prompt: {prompt}"
                        continue
                        
                    new_code, applied, details = apply_patches(current_code, args.get("fixes", []))
                    if applied == 0:
                        feedback = f"Error: No patches could be applied.\n" + "\n".join(details)
                        self._feedback_history.append(feedback)
                        user_prompt = FIX_CODE_RETRY_USER.format(feedback=feedback, code=current_code)
                        continue
                else:
                    feedback = f"Error: Unknown tool '{name}'. Use 'write_manim_code' or 'patch_manim_code'."
                    user_prompt = f"{feedback}\n\n{user_prompt}"
                    continue

                # 3. Validate and Iterate
                validation = self.validator.validate_code(new_code)
                if validation["valid"]:
                    return GenerationResult(
                        success=True,
                        code=new_code,
                        validation=validation,
                        iterations=iteration,
                        feedback_history=self._feedback_history
                    )
                
                feedback = f"Validation failed:\n{validation.get('error')}"
                self._feedback_history.append(feedback)
                current_code = new_code
                user_prompt = GENERATION_RETRY_USER.format(feedback=feedback, code=current_code)

            return GenerationResult(
                success=False,
                error=f"Exceeded max iterations ({self.MAX_ITERATIONS})",
                iterations=iteration,
                feedback_history=self._feedback_history
            )

        except Exception as e:
            return GenerationResult(success=False, error=f"Loop error: {str(e)}", iterations=iteration)

    def _get_tools(self, types_module) -> List[Any]:
        """Get standardized tools."""
        from .schemas import WRITE_CODE_SCHEMA, PATCH_CODE_SCHEMA
        return [
            types_module.Tool(
                function_declarations=[
                    types_module.FunctionDeclaration(
                        name="write_manim_code",
                        description="Write complete Manim code. Use for initial creation or full rewrites.",
                        parameters=WRITE_CODE_SCHEMA
                    ),
                    types_module.FunctionDeclaration(
                        name="patch_manim_code",
                        description="Apply targeted search/replace patches. Use for precise fixes to existing code.",
                        parameters=PATCH_CODE_SCHEMA
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
