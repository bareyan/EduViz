"""
Animation Processors - specialized handlers for the animation pipeline.

Following Google-quality standards:
- Unified Agent: Using a single iterative Gemini session for consistency.
- No Silent Failures: Specific exceptions for different failure states.
- Clean Architecture: Decoupled validation and rendering.
"""

import json
from typing import Dict, Any, List, Optional

from app.core import get_logger
from app.services.infrastructure.llm import PromptingEngine, PromptConfig
from app.services.infrastructure.llm.tools import create_tool_declaration

from ..prompts import (
    ANIMATOR_SYSTEM, 
    ANIMATOR_USER, 
    REANIMATOR_USER, 
    SEGMENT_CODER_USER
)
from .core import (
    clean_code,
    ChoreographyError,
    ImplementationError,
    RefinementError,
    ManimEditor,
    ManimScaffolder
)
from .validation import CodeValidator

logger = get_logger(__name__, component="animation_processors")

class Animator:
    """Unified Animation Agent.
    
    This agent manages the complete lifecycle of creating an animation:
    1. Visual Planning (Choreography)
    2. Code Implementation (Manim)
    3. Iterative Refinement (based on validation/rendering feedback)
    
    It maintains a single conversation context with the LLM to ensure
    that refinements are informed by the original planning intent.
    """
    
    def __init__(self, engine: PromptingEngine, validator: CodeValidator, max_iterations: int = 3):
        """Initializes the Animator with required infra."""
        self.engine = engine
        self.validator = validator
        self.max_iterations = max_iterations
        self.types = engine.types  # Access Gemini types
        self.editor = ManimEditor()
        self.scaffolder = ManimScaffolder()

    def _create_content(self, role: str, text: Optional[str] = None, parts: Optional[List[Any]] = None):
        """Helper to create a Gemini Content object."""
        if parts:
            return self.types.Content(role=role, parts=parts)
        return self.types.Content(
            role=role,
            parts=[self.types.Part(text=text or "")]
        )

    def _create_tool_response(self, function_name: str, result: Dict[str, Any]):
        """Creates a Gemini Part for a function response."""
        return self.types.Part(
            function_response=self.types.FunctionResponse(
                name=function_name,
                response=result
            )
        )

    async def animate(self, section: Dict[str, Any], duration: float) -> str:
        """Runs the segmented iterative animation pipeline.
        
        This is more efficient as it generates code piece-by-piece,
        validating and refining each segment before moving forward.
        """
        section_title = section.get("title", f"Section {section.get('index', '')}")
        segments = section.get("narration_segments", [])
        logger.info(f"Animating section '{section_title}' with {len(segments)} segments")
        
        # Define tool declarations using infrastructure helper
        tool_declarations = [create_tool_declaration(self.editor, self.types)]
        
        # 1. Turn 1: Holistic Planning
        initial_prompt = ANIMATOR_USER.format(
            title=section_title,
            narration=section.get("narration", ""),
            timing_info=json.dumps(segments, indent=2),
            target_duration=duration
        )
        
        history = [self._create_content("user", initial_prompt)]
        config = PromptConfig(enable_thinking=True, timeout=300.0)
        
        # Generate initial choreography plan
        result = await self.engine.generate(
            prompt="", config=config,
            system_prompt=ANIMATOR_SYSTEM.template,
            contents=history
        )
        
        if not result.get("success") or not result.get("response"):
            raise ChoreographyError(f"Failed to generate animation plan: {result.get('error', 'Empty response')}")
            
        history.append(self._create_content("model", result["response"]))
        logger.info(f"Choreography plan finalized for '{section_title}'")
        
        # 2. Iterate through segments for incremental implementation
        cumulative_code_lines = []
        
        for i, segment in enumerate(segments):
            seg_text = segment.get("text", "")[:100] + "..."
            logger.info(f"Implementing Segment {i+1}/{len(segments)}: {seg_text}")
            
            seg_prompt = SEGMENT_CODER_USER.format(
                segment_index=i + 1,
                segment_text=segment.get("text", ""),
                duration=segment.get("duration", 5.0),
                start_time=segment.get("start_time", 0.0)
            )
            
            history.append(self._create_content("user", seg_prompt))
            
            # Segment coding state
            segment_code = ""
            
            # Segment coding loop (local refinement)
            for attempt in range(1, self.max_iterations + 1):
                # If we are retrying, enable tools and encourage surgical edits
                active_tools = tool_declarations if attempt > 1 else None
                
                # Multi-turn tool execution loop
                while True:
                    res = await self.engine.generate(
                        prompt="", config=config,
                        system_prompt=ANIMATOR_SYSTEM.template,
                        contents=history,
                        tools=active_tools
                    )
                    
                    if not res.get("success"):
                        raise ImplementationError(f"Failed to implement segment {i+1}")
                    
                    # Handle function calls (Surgical Edits)
                    if res.get("function_calls"):
                        # Add model's call to history
                        parts = []
                        if res.get("response"):
                            parts.append(self.types.Part(text=res["response"]))
                        
                        for fc in res["function_calls"]:
                            parts.append(self.types.Part(function_call=self.types.FunctionCall(
                                name=fc["name"],
                                args=fc["args"]
                            )))
                        history.append(self.types.Content(role="model", parts=parts))
                        
                        # Execute tools and add responses
                        tool_responses = []
                        for fc in res["function_calls"]:
                            if fc["name"] == "apply_surgical_edit":
                                try:
                                    # Execute tool with current segment code
                                    fc["args"]["code"] = segment_code
                                    segment_code = self.editor.execute(**fc["args"])
                                    tool_responses.append(self._create_tool_response(
                                        fc["name"], {"status": "success", "info": "Edit applied"}
                                    ))
                                except Exception as e:
                                    logger.warning(f"Surgical edit failed: {str(e)}")
                                    tool_responses.append(self._create_tool_response(
                                        fc["name"], {"status": "error", "error": str(e)}
                                    ))
                        
                        history.append(self.types.Content(role="user", parts=tool_responses))
                        continue # Re-call LLM to get final code or next edit
                    
                    # No more tool calls, we check for new code in response text
                    new_code = clean_code(res.get("response", ""))
                    if new_code.strip():
                        segment_code = new_code
                    break

                # Validate the CUMULATIVE code as a full file using Scaffolder
                test_snippet = "\n".join(cumulative_code_lines + [segment_code])
                test_full_code = self.scaffolder.assemble(test_snippet)
                validation = self.validator.validate(test_full_code)
                
                if validation.valid:
                    history.append(self._create_content("model", res.get("response", "")))
                    cumulative_code_lines.append(segment_code)
                    break
                
                # Fetch errors and translate them back to snippet coordinates
                raw_errors = validation.get_error_summary()
                translated_errors, _ = self.scaffolder.translate_error(
                    raw_errors, 
                    validation.syntax.line_number
                )
                
                logger.warning(f"Segment {i+1} validation failed (Attempt {attempt}): {translated_errors[:100]}")
                
                # If invalid, stay in the same session and ask for fix, encouraging tool use
                repair_prompt = REANIMATOR_USER.format(
                    errors=translated_errors,
                    code=segment_code
                )
                history.append(self._create_content("model", res.get("response", "")))
                history.append(self._create_content("user", repair_prompt))
                
                if attempt == self.max_iterations:
                    raise RefinementError(f"Could not stabilize Segment {i+1} after {self.max_iterations} attempts.")

        return "\n".join(cumulative_code_lines)
