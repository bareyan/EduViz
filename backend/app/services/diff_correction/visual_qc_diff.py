"""
Visual QC Diff-based Correction Module

Provides targeted SEARCH/REPLACE fixes for visual layout errors detected by QC.
Much cheaper than full code regeneration - only sends the code and error description.
"""

import asyncio
import json
from typing import Optional, Dict, Any, TYPE_CHECKING

from .parser import extract_blocks_from_fenced, SearchReplaceBlock
from .applier import apply_all_blocks, validate_syntax
from .prompts import (
    VISUAL_QC_DIFF_SYSTEM,
    VISUAL_QC_DIFF_SCHEMA,
    build_visual_qc_diff_prompt,
    build_visual_qc_structured_prompt,
)

if TYPE_CHECKING:
    from app.services.manim_generator import ManimGenerator


# Configuration
USE_VISUAL_QC_DIFF = True  # Feature flag for visual QC diff correction
MAX_VISUAL_DIFF_ATTEMPTS = 3  # How many diff attempts before falling back to full regen
# Use text-based SEARCH/REPLACE format (standard format the model has seen more of)
USE_STRUCTURED_OUTPUT = False


async def fix_visual_errors_with_diff(
    generator: "ManimGenerator",
    original_code: str,
    error_report: str,
    section: Dict[str, Any] = None
) -> Optional[str]:
    """
    Fix visual QC errors using diff-based SEARCH/REPLACE blocks.
    
    This is much cheaper than full regeneration because:
    1. Only sends code + error description (no video)
    2. Gets small targeted diffs back
    3. Falls back to full regen only if needed
    
    Args:
        generator: ManimGenerator instance
        original_code: Code with visual issues
        error_report: Visual QC error report from check_video_quality
        section: Section context for timing preservation
        
    Returns:
        Fixed code if successful, None to trigger fallback
    """
    if not USE_VISUAL_QC_DIFF:
        print("[VisualQCDiff] Feature disabled, using full regeneration")
        return None

    if not error_report:
        print("[VisualQCDiff] No error report provided")
        return None

    print("[VisualQCDiff] Attempting diff-based visual fix...")

    # Try diff-based correction with internal retry loop
    current_code = original_code
    for attempt in range(MAX_VISUAL_DIFF_ATTEMPTS):
        print(f"[VisualQCDiff] Attempt {attempt + 1}/{MAX_VISUAL_DIFF_ATTEMPTS}...")

        result = await _try_visual_diff_correction(
            generator, current_code, error_report, section, attempt
        )

        if result:
            return result

    print(f"[VisualQCDiff] All {MAX_VISUAL_DIFF_ATTEMPTS} attempts failed, falling back to full regeneration")
    return None


async def _try_visual_diff_correction(
    generator: "ManimGenerator",
    code: str,
    error_report: str,
    section: Dict[str, Any],
    attempt: int = 0
) -> Optional[str]:
    """
    Try to fix visual issues using SEARCH/REPLACE blocks.
    
    Uses structured JSON output on first attempt (guaranteed format),
    falls back to text-based on retries if needed.
    """
    # Try structured output first (attempt 0), then text-based on retries
    if USE_STRUCTURED_OUTPUT and attempt == 0:
        result = await _try_structured_visual_correction(
            generator, code, error_report, section
        )
        if result:
            return result
        print("[VisualQCDiff] Structured output failed, will try text-based on retry")
        return None

    # Text-based SEARCH/REPLACE blocks
    return await _try_text_based_visual_correction(
        generator, code, error_report, section, attempt
    )


async def _try_structured_visual_correction(
    generator: "ManimGenerator",
    code: str,
    error_report: str,
    section: Dict[str, Any]
) -> Optional[str]:
    """
    Try visual correction using Gemini's structured JSON output.
    """
    # Use generator's types module (supports both API and Vertex AI)
    types = generator.types
    from app.config.models import get_model_config

    # Get correction model config
    correction_config = get_model_config("code_correction")
    model = correction_config.model_name

    # Build prompt
    prompt = build_visual_qc_structured_prompt(code, error_report, section)

    # System instruction with visual layout context
    system_instruction = VISUAL_QC_DIFF_SYSTEM

    # Configure with JSON schema response
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.1,
        max_output_tokens=4096,
        response_mime_type="application/json",
        response_schema=VISUAL_QC_DIFF_SCHEMA,
    )

    try:
        print(f"[VisualQCDiff] Using structured JSON output with {model}")

        response = await asyncio.to_thread(
            generator.client.models.generate_content,
            model=model,
            contents=[
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=prompt)]
                )
            ],
            config=config
        )

        # Track cost
        try:
            generator.cost_tracker.track_usage(response, model)
        except Exception:
            pass

        if not response or not response.text:
            print("[VisualQCDiff] Empty response from LLM")
            return None

        # Parse JSON response
        try:
            result = json.loads(response.text)
            fixes = result.get("fixes", [])
        except json.JSONDecodeError as e:
            print(f"[VisualQCDiff] Failed to parse JSON: {e}")
            return None

        if not fixes:
            print("[VisualQCDiff] No fixes in structured response")
            return None

        print(f"[VisualQCDiff] Got {len(fixes)} visual fix(es) from structured output")

        # Convert to SearchReplaceBlock objects
        blocks = [
            SearchReplaceBlock(
                search=fix.get("search", ""),
                replace=fix.get("replace", ""),
                line_number=None
            )
            for fix in fixes
            if fix.get("search")  # Filter out empty searches
        ]

        if not blocks:
            print("[VisualQCDiff] No valid blocks after filtering")
            return None

        # Log which issues are being fixed
        for i, fix in enumerate(fixes):
            if fix.get("issue_fixed"):
                print(f"[VisualQCDiff] Fix {i+1}: {fix['issue_fixed']}")

        # Apply blocks
        new_code, successes, errors = apply_all_blocks(code, blocks)

        for msg in successes:
            print(f"[VisualQCDiff] ✓ {msg}")
        for msg in errors:
            print(f"[VisualQCDiff] ✗ {msg}")

        if not successes:
            print("[VisualQCDiff] No blocks applied successfully")
            return None

        # Validate syntax
        syntax_error = validate_syntax(new_code)
        if syntax_error:
            print(f"[VisualQCDiff] Syntax error after fixes: {syntax_error}")
            return None

        print(f"[VisualQCDiff] ✓ Visual issues fixed ({len(successes)} changes)")
        return new_code

    except Exception as e:
        print(f"[VisualQCDiff] Structured output error: {e}")
        import traceback
        traceback.print_exc()
        return None


async def _try_text_based_visual_correction(
    generator: "ManimGenerator",
    code: str,
    error_report: str,
    section: Dict[str, Any],
    attempt: int = 0
) -> Optional[str]:
    """
    Try visual correction using text-based SEARCH/REPLACE blocks.
    """
    # Use generator's types module (supports both API and Vertex AI)
    types = generator.types
    from app.config.models import get_model_config

    # Get model - use stronger model on retries
    if attempt == 0:
        correction_config = get_model_config("code_correction")
        model = correction_config.model_name
    else:
        strong_config = get_model_config("code_correction_strong")
        model = strong_config.model_name
        print(f"[VisualQCDiff] Using stronger model: {model}")

    # Build prompt
    prompt = build_visual_qc_diff_prompt(code, error_report, section)

    if attempt > 0:
        prompt = f"""RETRY {attempt + 1} - OUTPUT SEARCH/REPLACE BLOCKS ONLY.

Format:
<<<<<<< SEARCH
exact code to find
=======
replacement code
>>>>>>> REPLACE

{prompt}"""

    config = types.GenerateContentConfig(
        system_instruction=VISUAL_QC_DIFF_SYSTEM,
        temperature=0.1 + (attempt * 0.15),  # Increase temp on retries
        max_output_tokens=4096,
    )

    try:
        response = await asyncio.to_thread(
            generator.client.models.generate_content,
            model=model,
            contents=[
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=prompt)]
                )
            ],
            config=config
        )

        # Track cost
        try:
            generator.cost_tracker.track_usage(response, model)
        except Exception:
            pass

        if not response or not response.text:
            print("[VisualQCDiff] Empty response from LLM")
            return None

        response_text = response.text

        # Parse SEARCH/REPLACE blocks
        blocks = extract_blocks_from_fenced(response_text)

        if not blocks:
            print("[VisualQCDiff] No SEARCH/REPLACE blocks found")
            preview = response_text[:300].replace('\n', ' ').strip()
            print(f"[VisualQCDiff] Response preview: {preview}...")
            return None

        print(f"[VisualQCDiff] Found {len(blocks)} block(s) in text response")

        # Apply blocks
        new_code, successes, errors = apply_all_blocks(code, blocks)

        for msg in successes:
            print(f"[VisualQCDiff] ✓ {msg}")
        for msg in errors:
            print(f"[VisualQCDiff] ✗ {msg}")

        if not successes:
            print("[VisualQCDiff] No blocks applied successfully")
            return None

        # Validate syntax
        syntax_error = validate_syntax(new_code)
        if syntax_error:
            print(f"[VisualQCDiff] Syntax error after fixes: {syntax_error}")
            return None

        print(f"[VisualQCDiff] ✓ Visual issues fixed via text blocks ({len(successes)} changes)")
        return new_code

    except Exception as e:
        print(f"[VisualQCDiff] Text-based error: {e}")
        import traceback
        traceback.print_exc()
        return None
