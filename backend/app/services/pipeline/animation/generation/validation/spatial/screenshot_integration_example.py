"""
Example: Using Screenshot-Enhanced Spatial Fixes in Animator

This demonstrates how the Animator can use screenshots from spatial validation
to provide visual context to the LLM when fixing layout issues.
"""

from pathlib import Path
from app.services.pipeline.animation.generation.validation.spatial.models import SpatialValidationResult
from backend.app.services.infrastructure.llm.prompting_engine.base_engine import PromptConfig


def format_visual_context_for_fix(validation_result: SpatialValidationResult) -> str:
    """
    Format screenshot information for inclusion in the surgical fix prompt.
    
    Call this when preparing the surgical fix prompt to add visual context.
    """
    if not validation_result.frame_captures:
        return ""
    
    # Group issues by frame
    frame_info = []
    for fc in validation_result.frame_captures:
        issues_at_frame = [
            issue for issue in (
                validation_result.errors + 
                validation_result.warnings + 
                validation_result.info
            )
            if issue.frame_id == fc.screenshot_path
        ]
        
        if issues_at_frame:
            frame_info.append(
                f"**Frame at t={fc.timestamp}s** (screenshot attached):\n" +
                "\n".join(f"  - {issue.message}" for issue in issues_at_frame)
            )
    
    if frame_info:
        return (
            "\n## VISUAL CONTEXT\n"
            "Screenshots are attached showing the exact layout issues:\n\n" +
            "\n\n".join(frame_info) +
            "\n\nLook at the attached images to understand the spatial problems before applying fixes.\n"
        )
    
    return ""


async def surgical_fix_with_screenshots(
    engine,  # PromptingEngine
    code: str,
    validation_result: SpatialValidationResult,
    editor_tool,  # ManimEditor
) -> str:
    """
    Example of how Animator._apply_surgical_fix should use screenshots.
    
    This shows the pattern for sending multimodal content to Gemini.
    """
    from app.services.pipeline.animation.prompts import SURGICAL_FIX_USER
    
    # 1. Format error summary
    errors_summary = "\n".join([
        f"Line {e.line_number}: {e.severity.upper()} - {e.message}"
        for e in (validation_result.errors + validation_result.warnings)
    ])
    
    # 2. Format visual context text
    visual_context = format_visual_context_for_fix(validation_result)
    
    # 3. Build text prompt
    prompt_text = SURGICAL_FIX_USER.format(
        code=code,
        errors=errors_summary,
        visual_context=visual_context
    )
    
    # 4. Build multimodal content list: [text, image1, image2, ...]
    contents = [prompt_text]
    
    # Add screenshots as image parts
    for fc in validation_result.frame_captures:
        if Path(fc.screenshot_path).exists():
            image_data = Path(fc.screenshot_path).read_bytes()
            # Use the engine's types module for compatibility
            # Try Vertex AI method first, fallback to Gemini API method
            try:
                image_part = engine.types.Part.from_data(
                    data=image_data,
                    mime_type="image/png"
                )
            except (AttributeError, TypeError):
                # Fallback for Gemini API
                image_part = engine.types.Part.from_bytes(
                    data=image_data,
                    mime_type="image/png"
                )
            contents.append(image_part)
    
    # 5. Create tool declarations
    from app.services.infrastructure.llm.tools import create_tool_declaration
    tool_declarations = [create_tool_declaration(editor_tool, engine.types)]
    
    # 6. Call LLM with multimodal content
    result = await engine.generate(
        prompt="",  # Empty because content is in `contents`
        contents=contents,  # [text, img1, img2, ...]
        tools=tool_declarations,
        config=PromptConfig(
            response_format="function_call",
            timeout=120.0
        )
    )
    
    # 7. Process tool calls
    updated_code = code
    if result.get("function_calls"):
        for fc in result["function_calls"]:
            if fc["name"] == "apply_surgical_edit":
                updated_code = editor_tool.execute(**fc["args"])
    
    # 8. Cleanup screenshots after fix attempt
    # (Animator should do this in finally block)
    # validation_result.cleanup_screenshots()
    
    return updated_code


# =============================================================================
# Integration Point: Where to Add This in Animator
# =============================================================================

"""
In backend/app/services/pipeline/animation/generation/processors.py:

class Animator:
    async def _apply_surgical_fix(
        self,
        code: str,
        validation: CodeValidationResult,
        attempt_num: int
    ) -> str:
        '''Apply surgical fixes to code using LLM with visual context.'''
        
        # Get spatial validation result with screenshots
        spatial_result = validation.spatial_result  # SpatialValidationResult
        
        # Format visual context
        visual_context = format_visual_context_for_fix(spatial_result)
        
        # Build error summary
        errors_summary = self._format_error_summary(validation)
        
        # Build prompt with visual context
        prompt_text = SURGICAL_FIX_USER.format(
            code=code,
            errors=errors_summary,
            visual_context=visual_context
        )
        
        # Build multimodal contents
        contents = [prompt_text]
        
        # Add screenshots
        for fc in spatial_result.frame_captures:
            if Path(fc.screenshot_path).exists():
                image_data = Path(fc.screenshot_path).read_bytes()
                image_part = self.engine.types.Part.from_data(
                    data=image_data,
                    mime_type="image/png"
                )
                contents.append(image_part)
        
        # Call LLM with tools
        tool_declarations = [create_tool_declaration(self.editor, self.engine.types)]
        
        result = await self.engine.generate(
            prompt="",
            contents=contents,
            tools=tool_declarations,
            system_prompt=ANIMATOR_SYSTEM.template,
            config=PromptConfig(response_format="function_call", timeout=120.0)
        )
        
        # Apply edits
        updated_code = code
        if result.get("function_calls"):
            for fc in result["function_calls"]:
                if fc["name"] == "apply_surgical_edit":
                    updated_code = self.editor.execute(**fc["args"])
        
        return updated_code
    
    async def animate(self, section, duration) -> str:
        '''Main animation generation with screenshot cleanup.'''
        try:
            # ... existing code ...
            code, is_valid = await self._agentic_fix_loop(code, section_title, duration)
            return code
        finally:
            # Cleanup any screenshots from validation
            if hasattr(self, '_last_validation') and self._last_validation:
                self._last_validation.spatial_result.cleanup_screenshots()
"""
