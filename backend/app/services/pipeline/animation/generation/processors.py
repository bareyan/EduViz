"""
Animation Processors - Hybrid Agentic Architecture.

Pipeline:
1. Phase 1 (Planning): Deep choreography with gemini-3-pro-preview
2. Phase 2 (Generation): Single-shot code with gemini-3-flash-preview
3. Phase 3 (Fixes): Agentic loop with structured JSON edits
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

from app.core import get_logger
from app.core.llm_logger import llm_section_context, llm_section_log_path_var
from app.services.infrastructure.llm import PromptingEngine, PromptConfig, CostTracker
from app.services.infrastructure.parsing import (
    parse_json_response,
    is_likely_truncated_json,
    repair_json_payload,
)

from ..prompts import (
    ANIMATOR_SYSTEM,
    CHOREOGRAPHER_SYSTEM,
    CHOREOGRAPHY_USER,
    CHOREOGRAPHY_COMPACT_USER,
    CHOREOGRAPHY_OBJECTS_USER,
    CHOREOGRAPHY_SEGMENTS_USER,
    FULL_IMPLEMENTATION_USER,
    SURGICAL_FIX_USER,
    SURGICAL_FIX_SYSTEM,
    get_compact_patterns
)
from .core import (
    clean_code,
    is_incomplete_code,
    ChoreographyError,
    ImplementationError,
    RefinementError,
    ManimEditor,
    get_theme_palette_text
)
from .validation import CodeValidator
from .validation.spatial.formatter import format_visual_context_for_fix
from ..config import (
    CHOREOGRAPHY_MAX_SEGMENTS_PER_CALL,
    CHOREOGRAPHY_TEMPERATURE,
    CHOREOGRAPHY_MAX_OUTPUT_TOKENS,
    FIX_TEMPERATURE,
    IMPLEMENTATION_MAX_OUTPUT_TOKENS,
)

logger = get_logger(__name__, component="animation_processors")

ALLOWED_ACTIONS = [
    "Create",
    "FadeIn",
    "Transform",
    "ReplacementTransform",
    "Write",
    "Wait",
    "FadeOut",
]

ALLOWED_OBJECT_TYPES = [
    "Text",
    "MathTex",
    "Rectangle",
    "Circle",
    "Dot",
    "Line",
    "Arrow",
    "Axes",
    "NumberPlane",
    "Brace",
    "VGroup",
    "SVGMobject",
    "ImageMobject",
    "ThreeDAxes",
    "Sphere",
    "Cube",
    "Cylinder",
    "Cone",
    "Torus",
    "Surface",
    "ParametricSurface",
]

ALLOWED_SCENE_TYPES = ["2D", "3D"]

ALLOWED_POSITIONS = [
    "center",
    "left",
    "right",
    "up",
    "down",
    "upper_left",
    "upper_right",
    "lower_left",
    "lower_right",
    "x,y",
]

POSITION_SCHEMA = {
    "anyOf": [
        {"type": "string", "enum": ALLOWED_POSITIONS},
        {"type": "string", "pattern": r"^-?\d+(\.\d+)?\s*,\s*-?\d+(\.\d+)?$"},
    ]
}

CAMERA_SCHEMA = {
    "type": "object",
    "properties": {
        "phi": {"type": "number"},
        "theta": {"type": "number"},
        "distance": {"type": "number"},
        "ambient_rotation_rate": {"type": "number"},
    },
    "additionalProperties": False,
}

PLAN_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "scene_type": {"type": "string", "enum": ALLOWED_SCENE_TYPES},
        "camera": CAMERA_SCHEMA,
        "objects": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "type": {"type": "string", "enum": ALLOWED_OBJECT_TYPES},
                    "text": {"type": "string"},
                    "latex": {"type": "string"},
                    "asset_path": {"type": "string"},
                    "appears_at": {"type": "number"},
                    "removed_at": {"type": "number"},
                    "notes": {"type": "string"},
                },
                "required": ["id", "type", "appears_at", "removed_at"],
                "additionalProperties": False,
            },
        },
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "segment_index": {"type": "number"},
                    "start_time": {"type": "number"},
                    "end_time": {"type": "number"},
                    "steps": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "time": {"type": "number"},
                                "action": {"type": "string", "enum": ALLOWED_ACTIONS},
                                "target": {"type": "string"},
                                "source": {"type": "string"},
                                "position": POSITION_SCHEMA,
                                "duration": {"type": "number"},
                                "notes": {"type": "string"},
                            },
                            "required": ["time", "action", "target"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["segment_index", "start_time", "end_time", "steps"],
                "additionalProperties": False,
            },
        },
        "screen_bounds": {
            "type": "object",
            "properties": {
                "x": {"type": "array", "items": {"type": "number"}},
                "y": {"type": "array", "items": {"type": "number"}},
            },
            "additionalProperties": False,
        },
    },
    "required": ["objects", "segments"],
    "additionalProperties": False,
}

COMPACT_PLAN_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "scene_type": {"type": "string", "enum": ALLOWED_SCENE_TYPES},
        "camera": CAMERA_SCHEMA,
        "objects": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "type": {"type": "string", "enum": ALLOWED_OBJECT_TYPES},
                    "text": {"type": "string"},
                    "latex": {"type": "string"},
                    "asset_path": {"type": "string"},
                    "appears_at": {"type": "number"},
                    "removed_at": {"type": "number"},
                },
                "required": ["id", "type", "appears_at", "removed_at"],
                "additionalProperties": False,
            },
        },
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "segment_index": {"type": "number"},
                    "start_time": {"type": "number"},
                    "end_time": {"type": "number"},
                    "steps": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "time": {"type": "number"},
                                "action": {"type": "string", "enum": ALLOWED_ACTIONS},
                                "target": {"type": "string"},
                                "source": {"type": "string"},
                                "position": POSITION_SCHEMA,
                                "duration": {"type": "number"},
                            },
                            "required": ["time", "action", "target"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["segment_index", "start_time", "end_time", "steps"],
                "additionalProperties": False,
            },
        },
        "screen_bounds": {
            "type": "object",
            "properties": {
                "x": {"type": "array", "items": {"type": "number"}},
                "y": {"type": "array", "items": {"type": "number"}},
            },
            "additionalProperties": False,
        },
    },
    "required": ["objects", "segments"],
    "additionalProperties": False,
}

OBJECTS_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "scene_type": {"type": "string", "enum": ALLOWED_SCENE_TYPES},
        "camera": CAMERA_SCHEMA,
        "objects": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "type": {"type": "string", "enum": ALLOWED_OBJECT_TYPES},
                    "text": {"type": "string"},
                    "latex": {"type": "string"},
                    "asset_path": {"type": "string"},
                    "appears_at": {"type": "number"},
                    "removed_at": {"type": "number"},
                },
                "required": ["id", "type", "appears_at", "removed_at"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["objects"],
    "additionalProperties": False,
}

SEGMENTS_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "segment_index": {"type": "number"},
                    "start_time": {"type": "number"},
                    "end_time": {"type": "number"},
                    "steps": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "time": {"type": "number"},
                                "action": {"type": "string", "enum": ALLOWED_ACTIONS},
                                "target": {"type": "string"},
                                "source": {"type": "string"},
                                "position": POSITION_SCHEMA,
                                "duration": {"type": "number"},
                            },
                            "required": ["time", "action", "target"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["segment_index", "start_time", "end_time", "steps"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["segments"],
    "additionalProperties": False,
}

FIX_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "edits": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "search_text": {"type": "string"},
                    "replacement_text": {"type": "string"},
                },
                "required": ["search_text", "replacement_text"],
                "additionalProperties": False,
            },
        },
        "full_code_lines": {"type": "array", "items": {"type": "string"}},
        "full_code": {"type": "string"},
        "notes": {"type": "string"},
    },
    "additionalProperties": False,
}


class Animator:
    """Hybrid Agentic Animation Generator.
    
    Uses different models for each phase:
    - Planning: gemini-3-pro-preview (deep thinking)
    - Generation: gemini-3-flash-preview (fast, accurate)
    - Fixes: gemini-3-flash-preview (structured JSON edits)
    """
    
    def __init__(
        self, 
        engine: PromptingEngine, 
        validator: CodeValidator, 
        max_fix_attempts: int = 5,
        cost_tracker: Optional[CostTracker] = None
    ):
        """Initializes the Animator with required infrastructure.
        
        Args:
            engine: Primary engine (used for generation and fixes)
            validator: Code validator instance
            max_fix_attempts: Maximum surgical fix attempts
            cost_tracker: Optional cost tracker for monitoring
        """
        self.engine = engine
        self.validator = validator
        self.max_fix_attempts = max_fix_attempts
        self.editor = ManimEditor()
        self.cost_tracker = cost_tracker or engine.cost_tracker
        
        # Create separate engine for choreography (uses different model)
        self.choreography_engine = PromptingEngine(
            config_key="animation_choreography",
            cost_tracker=self.cost_tracker
        )
        

    async def animate(
        self,
        section: Dict[str, Any],
        duration: float,
        style: str = "3b1b",
        code_persistor: Optional[Any] = None,
        status_callback: Optional[Any] = None
    ) -> tuple[str, bool]:
        """Runs the hybrid animation generation pipeline.
        
        Args:
            section: Section metadata from narration stage.
            duration: Target duration for the animation.
            
        Returns:
            The complete Manim code for the section.
            
        Raises:
            ChoreographyError: If planning fails.
            ImplementationError: If initial code generation fails.
            RefinementError: If surgical fixes fail to stabilize the code after all retries.
        """
        from ..config import MAX_CLEAN_RETRIES
        
        section_title = section.get("title", f"Section {section.get('index', '')}")
        last_error = None
        last_code: Optional[str] = None
        last_syntax_valid_code: Optional[str] = None

        def _track_syntax_valid(code: str) -> None:
            nonlocal last_syntax_valid_code
            last_syntax_valid_code = code
        
        for clean_retry in range(MAX_CLEAN_RETRIES):
            if clean_retry > 0:
                logger.warning(f"Clean retry {clean_retry}/{MAX_CLEAN_RETRIES} for '{section_title}'")
            
            try:
                # 1. Phase 1: Deep Choreography Planning (gemini-3-pro-preview)
                plan = await self._generate_plan(
                    section,
                    duration,
                    style=style,
                    status_callback=status_callback,
                )
                logger.info(f"Choreography plan finalized for '{section_title}'")
                
                # 2. Phase 2: Full Implementation (gemini-3-flash-preview, single-shot)
                code = await self._generate_full_code(section, plan, duration, style=style)
                if is_incomplete_code(code):
                    logger.warning(
                        "Implementation appears truncated; regenerating full code",
                        extra={"error_reason": "implementation_truncated"},
                    )
                    if status_callback:
                        try:
                            status_callback(
                                "fixing_manim",
                                "Implementation truncated; regenerating full code",
                            )
                        except Exception:
                            pass
                    strict_suffix = (
                        "\n\nIMPORTANT:\n"
                        "- Return the FULL file only (no partials)\n"
                        "- Ensure all parentheses, brackets, and strings are closed\n"
                    )
                    code = await self._generate_full_code(
                        section,
                        plan,
                        duration,
                        style=style,
                        prompt_suffix=strict_suffix,
                        temperature=FIX_TEMPERATURE,
                    )
                    if is_incomplete_code(code):
                        logger.error(
                            "Implementation regeneration still truncated",
                            extra={"error_reason": "implementation_truncated"},
                        )
                        raise ImplementationError("Implementation output truncated")
                else:
                    static_check = self.validator.static_validator.validate(code)
                    if static_check.valid:
                        _track_syntax_valid(code)
                logger.info(f"Initial code generated for '{section_title}'")
                last_code = code
                self._persist_code(code, code_persistor, stage="initial")
                
                # 3. Phase 3: Agentic Fix Loop (with memory)
                code, is_valid = await self._agentic_fix_loop(
                    code,
                    section_title,
                    duration,
                    style=style,
                    code_persistor=code_persistor,
                    status_callback=status_callback,
                    syntax_ok_callback=_track_syntax_valid
                )
                last_code = code
                
                if is_valid:
                    return code, False
                else:
                    # Fix loop failed, try clean regeneration
                    last_error = "Surgical fixes could not stabilize code"
                    continue
                    
            except (ChoreographyError, ImplementationError) as e:
                last_error = str(e)
                continue
        
        # All retries exhausted - use last syntax-valid code if available
        logger.warning(f"All {MAX_CLEAN_RETRIES} clean retries exhausted.")
        if last_syntax_valid_code is not None:
            logger.warning(
                "Returning last syntax-valid code after retries",
                extra={"error_reason": "fallback_syntax_valid"},
            )
            return last_syntax_valid_code, True
        if last_code is None:
            raise RefinementError(last_error or "Failed to generate animation code")
        return last_code, False
    
    
    async def _agentic_fix_loop(
        self,
        code: str,
        section_title: str,
        target_duration: float,
        style: str,
        code_persistor: Optional[Any] = None,
        status_callback: Optional[Any] = None,
        syntax_ok_callback: Optional[Callable[[str], None]] = None,
    ) -> tuple[str, bool]:
        """Agentic fix loop with structured JSON edits.
        
        This loop:
        1. Corrects timing programmatically
        2. Validates the code
        3. If errors exist, applies surgical fix
        4. If only warnings/info, proceeds to render
        5. Stops when valid (no errors) or max attempts reached
        
        Returns:
            Tuple of (code, is_valid) where is_valid indicates if code is error-free
        
        Severity behavior:
        - errors: MUST fix, blocks loop
        - warnings: Include in summary but don't block
        - info: Not sent to LLM, doesn't block
        """
        last_validated_code: Optional[str] = None
        last_validation = None
        total_edits_applied = 0

        for attempt in range(1, self.max_fix_attempts + 1):
            # Timing adjuster disabled; keep generated timing as-is.

            if last_validated_code == code and last_validation is not None:
                validation = last_validation
            else:
                validation = self.validator.validate(code)
                last_validated_code = code
                last_validation = validation

            if validation.static.valid and syntax_ok_callback:
                try:
                    syntax_ok_callback(code)
                except Exception:
                    pass

            if not validation.static.valid:
                static_errors = " ".join(validation.static.errors).lower()
                if (
                    "syntax error" in static_errors
                    or "define at least one class" in static_errors
                    or "missing the 'construct(self)'" in static_errors
                ):
                    logger.warning(
                        "Structural validation failed; forcing clean regeneration",
                        extra={"error_reason": "implementation_truncated"},
                    )
                    return code, False
            
            # Only errors block the loop - warnings and info don't
            has_errors = (
                (not validation.static.valid)
                or (not validation.runtime.valid)
                or (len(validation.spatial.errors) > 0)
            )
            
            if not has_errors:
                if validation.spatial.warnings:
                    logger.info(f"Animation validated with {len(validation.spatial.warnings)} warnings (non-blocking)")
                else:
                    logger.info(f"Animation code validated successfully on attempt {attempt}")
                logger.info(
                    "Accepted Manim code after fixes",
                    extra={
                        "fix_attempts_used": max(0, attempt - 1),
                        "edits_applied_total": total_edits_applied,
                    },
                )
                return code, True
            
            error_summary = validation.get_error_summary()
            logger.warning(f"Validation failed (Attempt {attempt}): {error_summary[:100]}...")

            if status_callback:
                try:
                    status_callback("fixing_manim", error_summary)
                except Exception:
                    pass
            
            # Apply surgical fix
            new_code, edits_applied = await self._apply_surgical_fix(
                code,
                error_summary,
                validation,
                attempt=attempt,
                status_callback=status_callback,
                style=style,
            )
            if edits_applied:
                total_edits_applied += edits_applied
            code = new_code
            self._persist_code(code, code_persistor, stage=f"fix_{attempt}")
            
            # Clean up screenshots after fix attempt
            validation.spatial.cleanup_screenshots()
        
        # Return code but indicate it's not fully valid
        remaining_summary = last_validation.get_error_summary() if last_validation else "No validation run"
        logger.warning(
            f"Could not fully stabilize animation after {self.max_fix_attempts} attempts. "
            f"Remaining issues: {remaining_summary[:100]}..."
        )
        return code, False

    def _persist_code(self, code: str, persistor: Optional[Any], stage: str) -> None:
        if not persistor:
            return
        try:
            persistor(code, stage)
        except Exception as e:
            logger.warning(f"Failed to persist code at stage {stage}: {e}")


    async def _generate_plan(
        self,
        section: Dict[str, Any],
        duration: float,
        style: str,
        status_callback: Optional[Any] = None,
    ) -> str:
        """Generates a visual choreography plan using deep thinking model."""
        visual_description = section.get("visual_description") or ""
        visual_hints_lines: List[str] = []
        if visual_description:
            visual_hints_lines.append(f"- Section: {visual_description}")
        for i, seg in enumerate(section.get("narration_segments", []) or []):
            hint = seg.get("visual_description") or seg.get("visual_hint") or ""
            if hint:
                seg_idx = seg.get("segment_index", i)
                visual_hints_lines.append(f"- Segment {seg_idx}: {hint}")
        visual_hints = "\n".join(visual_hints_lines) if visual_hints_lines else "None"

        theme_info = get_theme_palette_text(style)
        prompt = CHOREOGRAPHY_USER.format(
            title=section.get("title", "Untitled"),
            narration=section.get("narration", ""),
            timing_info=self._format_timing_info(section),
            target_duration=duration,
            visual_hints=visual_hints,
            section_data=self._format_section_data(section),
            theme_info=theme_info,
        )
        
        config = PromptConfig(
            enable_thinking=True,
            timeout=300.0,
            response_format="json",
            response_schema=PLAN_RESPONSE_SCHEMA,
        )
        config.temperature = CHOREOGRAPHY_TEMPERATURE
        config.max_output_tokens = CHOREOGRAPHY_MAX_OUTPUT_TOKENS
        strict_suffix = (
            "\n\nSTRICT JSON RULES:\n"
            "- No line breaks inside strings\n"
            "- Notes must be 12 words or fewer\n"
            "- Max 20 objects total\n"
            "- Max 6 steps per segment\n"
            "- Use position tokens only: center, left, right, up, down, upper_left, upper_right, lower_left, lower_right, x,y\n"
            "- Use direction constants: UP, DOWN, LEFT, RIGHT, UL, UR, DL, DR, IN, OUT, ORIGIN\n"
            "- Do NOT use TOP or BOTTOM\n"
        )

        def _parse_json_result(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            parsed = result.get("parsed_json")
            if not parsed and result.get("response"):
                sentinel = object()
                repaired = repair_json_payload(result.get("response", ""))
                if repaired:
                    parsed = parse_json_response(repaired, default=sentinel)
                else:
                    parsed = parse_json_response(result.get("response"), default=sentinel)
                if parsed is sentinel:
                    parsed = None
            return parsed

        def _is_valid_plan(parsed: Any) -> bool:
            if not isinstance(parsed, dict):
                return False
            objects = parsed.get("objects")
            segments = parsed.get("segments")
            if not isinstance(objects, list) or not isinstance(segments, list):
                return False
            return True

        def _is_valid_objects(objects: Any) -> bool:
            if not isinstance(objects, list):
                return False
            for obj in objects:
                if not isinstance(obj, dict):
                    return False
                for key in ("id", "type", "appears_at", "removed_at"):
                    if key not in obj:
                        return False
            return True

        def _is_valid_segments(segments: Any) -> bool:
            if not isinstance(segments, list):
                return False
            for seg in segments:
                if not isinstance(seg, dict):
                    return False
                for key in ("segment_index", "start_time", "end_time", "steps"):
                    if key not in seg:
                        return False
                if not isinstance(seg.get("steps"), list):
                    return False
            return True

        last_error = None
        for attempt in range(2):
            with llm_section_context({"stage": "choreography", "retry": attempt}):
                result = await self.choreography_engine.generate(
                    prompt=prompt,
                    system_prompt=CHOREOGRAPHER_SYSTEM.template,
                    config=config
                )

            parsed = _parse_json_result(result)
            if parsed and _is_valid_plan(parsed):
                return json.dumps(parsed, indent=2)

            if parsed and not _is_valid_plan(parsed):
                last_error = "Missing required keys in choreography plan"
            else:
                last_error = result.get("error", "Invalid JSON response")
                if result.get("response") and is_likely_truncated_json(result.get("response", "")):
                    last_error = "choreography_truncated"
                    logger.warning(
                        "Choreography JSON appears truncated",
                        extra={"error_reason": "choreography_truncated"},
                    )
            if attempt == 0:
                prompt = f"{prompt}{strict_suffix}"

        if status_callback:
            try:
                status_callback(
                    "fixing_manim",
                    "Choreography JSON truncated; retrying with compact plan",
                )
            except Exception:
                pass

        compact_prompt = CHOREOGRAPHY_COMPACT_USER.format(
            title=section.get("title", "Untitled"),
            narration=section.get("narration", ""),
            timing_info=self._format_timing_info(section),
            target_duration=duration,
            visual_hints=visual_hints,
            theme_info=theme_info,
        )
        compact_config = PromptConfig(
            enable_thinking=True,
            timeout=300.0,
            response_format="json",
            response_schema=COMPACT_PLAN_RESPONSE_SCHEMA,
        )
        compact_config.temperature = CHOREOGRAPHY_TEMPERATURE
        compact_config.max_output_tokens = CHOREOGRAPHY_MAX_OUTPUT_TOKENS
        with llm_section_context({"stage": "choreography_compact"}):
            compact_result = await self.choreography_engine.generate(
                prompt=compact_prompt,
                system_prompt=CHOREOGRAPHER_SYSTEM.template,
                config=compact_config,
            )

        compact_parsed = _parse_json_result(compact_result)
        if compact_parsed and _is_valid_plan(compact_parsed):
            return json.dumps(compact_parsed, indent=2)

        if compact_parsed and not _is_valid_plan(compact_parsed):
            compact_error = "Missing required keys in compact choreography plan"
        else:
            compact_error = compact_result.get("error", "Invalid JSON response")
            if compact_result.get("response") and is_likely_truncated_json(compact_result.get("response", "")):
                compact_error = "choreography_truncated"
                logger.warning(
                    "Compact choreography JSON appears truncated",
                    extra={"error_reason": "choreography_truncated"},
                )

        if status_callback:
            try:
                status_callback(
                    "fixing_manim",
                    "Choreography JSON truncated; retrying with chunked plan",
                )
            except Exception:
                pass

        # Chunked fallback: objects first, then segments in small batches
        narration_segments = section.get("narration_segments", []) or []
        if not narration_segments:
            raise ChoreographyError(
                f"Failed to generate animation plan: {last_error}. "
                f"Compact fallback failed: {compact_error}. "
                "No narration segments available for chunked fallback."
            )

        objects_prompt = CHOREOGRAPHY_OBJECTS_USER.format(
            title=section.get("title", "Untitled"),
            narration=section.get("narration", ""),
            timing_info=self._format_timing_info(section),
            target_duration=duration,
            visual_hints=visual_hints,
            theme_info=theme_info,
        )
        objects_config = PromptConfig(
            enable_thinking=True,
            timeout=300.0,
            response_format="json",
            response_schema=OBJECTS_RESPONSE_SCHEMA,
        )
        objects_config.temperature = CHOREOGRAPHY_TEMPERATURE
        objects_config.max_output_tokens = CHOREOGRAPHY_MAX_OUTPUT_TOKENS
        with llm_section_context({"stage": "choreography_objects"}):
            objects_result = await self.choreography_engine.generate(
                prompt=objects_prompt,
                system_prompt=CHOREOGRAPHER_SYSTEM.template,
                config=objects_config,
            )

        objects_parsed = _parse_json_result(objects_result)
        if not isinstance(objects_parsed, dict):
            objects_parsed = {}
        objects = objects_parsed.get("objects")
        if not _is_valid_objects(objects):
            objects_error = objects_result.get("error", "Invalid objects JSON response")
            raise ChoreographyError(
                f"Failed to generate animation plan: {last_error}. "
                f"Compact fallback failed: {compact_error}. "
                f"Objects chunk failed: {objects_error}"
            )

        scene_type = objects_parsed.get("scene_type")
        camera = objects_parsed.get("camera")

        object_catalog = [
            {"id": obj.get("id"), "type": obj.get("type")}
            for obj in objects
        ]

        all_segments: List[Dict[str, Any]] = []
        for chunk_index in range(0, len(narration_segments), CHOREOGRAPHY_MAX_SEGMENTS_PER_CALL):
            chunk = narration_segments[chunk_index:chunk_index + CHOREOGRAPHY_MAX_SEGMENTS_PER_CALL]
            start_idx = chunk[0].get("segment_index", chunk_index)
            end_idx = chunk[-1].get("segment_index", chunk_index + len(chunk) - 1)
            segment_prompt = CHOREOGRAPHY_SEGMENTS_USER.format(
                title=section.get("title", "Untitled"),
                target_duration=duration,
                segment_range=f"{start_idx}..{end_idx}",
                segment_chunk=json.dumps(chunk, indent=2),
                object_catalog=json.dumps(object_catalog, indent=2),
            )
            segment_config = PromptConfig(
                enable_thinking=True,
                timeout=300.0,
                response_format="json",
                response_schema=SEGMENTS_RESPONSE_SCHEMA,
            )
            segment_config.temperature = CHOREOGRAPHY_TEMPERATURE
            segment_config.max_output_tokens = CHOREOGRAPHY_MAX_OUTPUT_TOKENS
            with llm_section_context(
                {"stage": "choreography_segments", "chunk": f"{start_idx}-{end_idx}"}
            ):
                segment_result = await self.choreography_engine.generate(
                    prompt=segment_prompt,
                    system_prompt=CHOREOGRAPHER_SYSTEM.template,
                    config=segment_config,
                )

            segment_parsed = _parse_json_result(segment_result)
            if not isinstance(segment_parsed, dict):
                segment_parsed = {}
            segments = segment_parsed.get("segments")
            if not _is_valid_segments(segments):
                segment_error = segment_result.get("error", "Invalid segments JSON response")
                raise ChoreographyError(
                    f"Failed to generate animation plan: {last_error}. "
                    f"Compact fallback failed: {compact_error}. "
                    f"Segments chunk {start_idx}-{end_idx} failed: {segment_error}"
                )
            all_segments.extend(segments)

        all_segments.sort(key=lambda s: s.get("segment_index", 0))
        chunked_plan = {
            "scene_type": scene_type,
            "camera": camera,
            "objects": objects,
            "segments": all_segments,
            "screen_bounds": {"x": [-5.5, 5.5], "y": [-3.0, 3.0]},
        }
        return json.dumps(chunked_plan, indent=2)


    async def _generate_full_code(
        self,
        section: Dict[str, Any],
        plan: str,
        duration: float,
        style: str,
        prompt_suffix: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Generates the full Manim code in one shot."""
        segment_timings = self._format_segment_timings(section)
        section_id_title = self._get_section_class_name(section)
        
        theme_info = get_theme_palette_text(style)
        prompt = FULL_IMPLEMENTATION_USER.format(
            plan=plan,
            segment_timings=segment_timings,
            total_duration=duration,
            section_id_title=section_id_title,
            patterns=get_compact_patterns(),
            section_data=self._format_section_data(section),
            theme_info=theme_info,
        )

        if prompt_suffix:
            prompt = f"{prompt}\n{prompt_suffix}"
        
        config = PromptConfig(enable_thinking=True, timeout=300.0)
        if temperature is not None:
            config.temperature = temperature
        config.max_output_tokens = IMPLEMENTATION_MAX_OUTPUT_TOKENS
        with llm_section_context({"stage": "implementation"}):
            result = await self.engine.generate(
                prompt=prompt,
                system_prompt=ANIMATOR_SYSTEM.template,
                config=config
            )
        
        if not result.get("success") or not result.get("response"):
            raise ImplementationError(
                f"Failed to generate initial code: {result.get('error', 'Empty response')}"
            )
            
        return clean_code(result["response"])


    async def _apply_surgical_fix(
        self,
        code: str,
        errors: str,
        validation=None,
        attempt: Optional[int] = None,
        status_callback: Optional[Any] = None,
        style: str = "3b1b",
    ) -> tuple[str, int]:
        """Applies a surgical fix using structured JSON edits."""
        def _truncate(value: Optional[str], limit: int = 1600) -> str:
            if value is None:
                return ""
            text = str(value)
            if len(text) <= limit:
                return text
            return f"{text[:limit]}... [truncated {len(text) - limit} chars]"

        def _append_section_log_block(title: str, body: str) -> None:
            log_path = llm_section_log_path_var.get()
            if not log_path:
                return
            try:
                text_log_path = Path(log_path).parent / "section.log"
                timestamp = datetime.utcnow().isoformat() + "Z"
                header = f"\n=== {title} (attempt {attempt}) {timestamp} ===\n"
                with text_log_path.open("a", encoding="utf-8") as f:
                    f.write(header)
                    f.write(body or "")
                    if not (body or "").endswith("\n"):
                        f.write("\n")
            except Exception:
                pass

        original_code = code
        visual_context = ""
        if validation is not None and getattr(validation, "spatial", None) is not None:
            try:
                visual_context = format_visual_context_for_fix(validation.spatial)
            except Exception:
                pass
        theme_info = get_theme_palette_text(style)
        prompt_text = SURGICAL_FIX_USER.format(
            code=code,
            errors=errors or "Unknown error",
            visual_context=visual_context,
            theme_info=theme_info,
        )

        screenshot_count = 0
        if validation is not None and getattr(validation, "spatial", None) is not None:
            frame_captures = validation.spatial.frame_captures or []
            screenshot_count = len(frame_captures)

        logger.info(
            "Surgical fix request",
            extra={
                "attempt": attempt,
                "code_len": len(code or ""),
                "errors_len": len(errors or ""),
                "prompt_len": len(prompt_text),
                "has_visual_context": bool(visual_context),
                "visual_context_len": len(visual_context),
                "screenshot_count": screenshot_count,
                "errors_preview": _truncate(errors or "", 800),
                "prompt_preview": _truncate(prompt_text, 1200),
            },
        )
        _append_section_log_block("Surgical fix request prompt", prompt_text)

        config = PromptConfig(
            timeout=120.0,
            response_format="json",
            response_schema=FIX_RESPONSE_SCHEMA,
        )
        config.temperature = FIX_TEMPERATURE

        def _is_transient_error(message: str) -> bool:
            msg = (message or "").lower()
            return (
                "503" in msg
                or "429" in msg
                or "timeout" in msg
                or "timed out" in msg
                or "unavailable" in msg
                or "overloaded" in msg
                or "rate limit" in msg
            )

        result = None
        transient_attempts = 3
        for retry in range(transient_attempts):
            with llm_section_context({"stage": "surgical_fix", "attempt": attempt}):
                contents = None
                if validation is not None and getattr(validation, "spatial", None) is not None:
                    frame_captures = validation.spatial.frame_captures or []
                    if frame_captures:
                        contents = [prompt_text]
                        for fc in frame_captures:
                            try:
                                path = Path(fc.screenshot_path)
                                if not path.exists():
                                    continue
                                image_data = path.read_bytes()
                                try:
                                    image_part = self.engine.types.Part.from_data(
                                        data=image_data,
                                        mime_type="image/png"
                                    )
                                except (AttributeError, TypeError):
                                    image_part = self.engine.types.Part.from_bytes(
                                        data=image_data,
                                        mime_type="image/png"
                                    )
                                contents.append(image_part)
                            except Exception:
                                continue
                result = await self.engine.generate(
                    prompt=prompt_text,
                    system_prompt=SURGICAL_FIX_SYSTEM.template,
                    config=config,
                    contents=contents
                )

            logger.info(
                "Surgical fix response",
                extra={
                    "attempt": attempt,
                    "retry": retry,
                    "success": bool(result.get("success")) if result else False,
                    "error": (result or {}).get("error"),
                    "response_len": len((result or {}).get("response") or ""),
                    "response_preview": _truncate((result or {}).get("response") or "", 1200),
                    "has_parsed_json": (result or {}).get("parsed_json") is not None,
                },
            )
            _append_section_log_block(
                "Surgical fix raw response",
                (result or {}).get("response") or "",
            )

            if result.get("success"):
                break

            error_msg = result.get("error", "")
            if _is_transient_error(error_msg) and retry < transient_attempts - 1:
                logger.warning(
                    f"Surgical fix LLM transient failure: {error_msg}",
                    extra={"error_reason": "fix_llm_overloaded"},
                )
                if status_callback:
                    try:
                        status_callback("fixing_manim", "LLM overloaded; retrying fix request")
                    except Exception:
                        pass
                await asyncio.sleep(2 ** retry)
                continue

            logger.error(f"Surgical fix call failed: {error_msg}")
            return code, 0
        
        if not result or not result.get("success"):
            logger.error("Surgical fix call failed: empty result")
            return code, 0

        payload = result.get("parsed_json")
        if payload is None and result.get("response"):
            repaired = repair_json_payload(result.get("response", ""))
            if repaired:
                sentinel = object()
                payload = parse_json_response(repaired, default=sentinel)
                if payload is sentinel:
                    payload = None
        if payload is None:
            logger.warning("Surgical fix returned no parsed_json payload")
            return code, 0

        payload = payload or {}
        edits = payload.get("edits") or []
        logger.info(
            "Surgical fix payload summary",
            extra={
                "attempt": attempt,
                "edits_count": len(edits),
                "has_full_code_lines": isinstance(payload.get("full_code_lines"), list),
                "full_code_lines_count": len(payload.get("full_code_lines") or []),
                "has_full_code": bool(payload.get("full_code")),
            },
        )
        applied = 0

        for edit_index, edit in enumerate(edits):
            search_text = (edit or {}).get("search_text") or ""
            replacement_text = (edit or {}).get("replacement_text") or ""
            if not search_text:
                logger.info(
                    "Surgical edit skipped: empty search text",
                    extra={"attempt": attempt, "edit_index": edit_index},
                )
                continue

            match_count = code.count(search_text)
            logger.info(
                "Surgical edit analysis",
                extra={
                    "attempt": attempt,
                    "edit_index": edit_index,
                    "search_len": len(search_text),
                    "replacement_len": len(replacement_text),
                    "match_count": match_count,
                    "is_valid_match": match_count == 1,
                    "search_preview": _truncate(search_text, 400),
                    "replacement_preview": _truncate(replacement_text, 400),
                },
            )
            try:
                code = self.editor.execute(
                    code=code,
                    search_text=search_text,
                    replacement_text=replacement_text
                )
                applied += 1
                logger.info(
                    "Surgical edit applied",
                    extra={
                        "attempt": attempt,
                        "edit_index": edit_index,
                        "applied": True,
                        "match_count": match_count,
                    },
                )
            except Exception as e:
                logger.warning(
                    "Surgical edit failed",
                    extra={
                        "attempt": attempt,
                        "edit_index": edit_index,
                        "applied": False,
                        "match_count": match_count,
                        "error": str(e),
                    },
                )

        if applied:
            logger.info(
                "Surgical fix edits applied",
                extra={
                    "attempt": attempt,
                    "edits_applied": applied,
                    "edits_total": len(edits),
                },
            )
            return code, applied

        full_code_lines = payload.get("full_code_lines") or []
        if isinstance(full_code_lines, list) and full_code_lines:
            joined = "\n".join(full_code_lines)
            cleaned = clean_code(joined)
            if cleaned:
                logger.info("Using full_code_lines fallback from JSON fix response")
                logger.info(
                    "Surgical fix fallback applied",
                    extra={"attempt": attempt, "fallback": "full_code_lines"},
                )
                return cleaned, 1

        full_code = payload.get("full_code")
        if full_code:
            cleaned = clean_code(full_code)
            if cleaned:
                logger.info("Using full_code fallback from JSON fix response")
                logger.info(
                    "Surgical fix fallback applied",
                    extra={"attempt": attempt, "fallback": "full_code"},
                )
                return cleaned, 1

        return code, 0


    def _format_timing_info(self, section: Dict[str, Any]) -> str:
        """Format segment timing info for the prompt."""
        segments = section.get("narration_segments", [])
        return json.dumps(segments, indent=2)


    def _format_segment_timings(self, section: Dict[str, Any]) -> str:
        """Format segment timings as readable text."""
        segments = section.get("narration_segments", [])
        lines: List[str] = []
        for i, s in enumerate(segments):
            text = s.get("text") or ""
            start_time = s.get("start_time", 0) or 0
            duration = s.get("duration", 5) or 5
            lines.append(
                f"- Segment {i+1} ({start_time:.1f}s - {start_time + duration:.1f}s): "
                f"{text[:60]}..."
            )
        return "\n".join(lines)

    def _format_section_data(self, section: Dict[str, Any]) -> str:
        """Format supporting data for animation prompts."""
        data = section.get("supporting_data") or []
        if not isinstance(data, list) or not data:
            return "None"

        lines: List[str] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            item_type = item.get("type", "data")
            label = item.get("label") or ""
            value = item.get("value")
            notes = item.get("notes") or ""

            if isinstance(value, (dict, list)):
                value_text = json.dumps(value)
            else:
                value_text = str(value) if value is not None else ""

            if label:
                line = f"- [{item_type}] {label}: {value_text}"
            else:
                line = f"- [{item_type}] {value_text}"
            if notes:
                line = f"{line} ({notes})"
            lines.append(line)

        return "\n".join(lines) if lines else "None"


    def _get_section_class_name(self, section: Dict[str, Any]) -> str:
        """Generate a valid Python class name from section ID."""
        section_index = section.get('index', 0)
        section_id = section.get("id", f"section_{section_index}")
        section_id = section_id.replace("-", "_").replace(" ", "_")
        return "".join(word.title() for word in section_id.split("_"))
