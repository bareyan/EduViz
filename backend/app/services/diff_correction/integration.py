"""
Integration module for diff-based correction with the Manim renderer.

This module provides a drop-in replacement for correct_manim_code that uses
diff-based correction first, then falls back to full regeneration.

Features:
- Structured JSON output mode (guaranteed format via Gemini schema)
- Text-based SEARCH/REPLACE block mode (traditional)
- Automatic fallback between modes
- Progressive retry with stronger models
"""

import asyncio
import json
from typing import Optional, Dict, Any, List, TYPE_CHECKING

from .parser import extract_blocks_from_fenced, SearchReplaceBlock
from .applier import apply_all_blocks, validate_syntax
from .prompts import (
    DIFF_CORRECTION_SYSTEM, 
    DIFF_CORRECTION_SCHEMA,
    MANIM_CONTEXT,
    build_diff_correction_prompt,
    build_structured_prompt,
    parse_error_context
)

if TYPE_CHECKING:
    from app.services.manim_generator import ManimGenerator


# Configuration
USE_DIFF_CORRECTION = True  # Feature flag
MAX_DIFF_ATTEMPTS = 3  # How many diff attempts before falling back
USE_STRONG_MODEL_ON_RETRY = True  # Use stronger model on 2nd+ attempts
# Use text-based SEARCH/REPLACE format (standard format the model has seen more of)
USE_STRUCTURED_OUTPUT = False


async def correct_manim_code_with_diff(
    generator: "ManimGenerator",
    original_code: str,
    error_message: str,
    section: Dict[str, Any],
    attempt: int = 0
) -> Optional[str]:
    """
    Smart correction: Try diff-based first (fast/cheap), fallback to full regen.
    
    This is a drop-in replacement for correct_manim_code in renderer.py.
    
    Args:
        generator: ManimGenerator instance
        original_code: Code with errors
        error_message: Manim stderr output
        section: Section context
        attempt: Current attempt number (from outer loop)
        
    Returns:
        Fixed code if successful, None otherwise
    """
    if not USE_DIFF_CORRECTION:
        # Feature disabled, use original function
        from app.services.manim_generator.renderer import correct_manim_code as original_correct
        return await original_correct(generator, original_code, error_message, section, attempt)
    
    # Try diff-based correction with internal retry loop
    current_code = original_code
    for diff_attempt in range(MAX_DIFF_ATTEMPTS):
        print(f"[DiffCorrector] Diff attempt {diff_attempt + 1}/{MAX_DIFF_ATTEMPTS}...")
        
        result = await _try_diff_correction(generator, current_code, error_message, section, diff_attempt)
        if result:
            return result
        
        # If diff failed and no blocks found, try once more with the same code
        # If blocks were found but didn't apply, current_code is unchanged
    
    print(f"[DiffCorrector] All {MAX_DIFF_ATTEMPTS} diff attempts failed, falling back to full regeneration")
    
    # Fallback to original full regeneration
    from app.services.manim_generator.renderer import correct_manim_code as original_correct
    return await original_correct(generator, original_code, error_message, section, attempt)


async def _try_diff_correction(
    generator: "ManimGenerator",
    code: str,
    error_message: str,
    section: Dict[str, Any],
    attempt: int = 0
) -> Optional[str]:
    """
    Try to fix code using SEARCH/REPLACE blocks.
    
    Uses structured JSON output on first attempt (guaranteed format),
    falls back to text-based on retries if needed.
    
    Returns:
        Fixed code if successful, None otherwise
    """
    # Try structured output first (attempt 0), then text-based on retries
    if USE_STRUCTURED_OUTPUT and attempt == 0:
        result = await _try_structured_correction(generator, code, error_message, section)
        if result:
            return result
        print("[DiffCorrector] Structured output failed, will try text-based on retry")
        return None
    
    # Text-based SEARCH/REPLACE blocks
    return await _try_text_based_correction(generator, code, error_message, section, attempt)


async def _try_structured_correction(
    generator: "ManimGenerator",
    code: str,
    error_message: str,
    section: Dict[str, Any]
) -> Optional[str]:
    """
    Try correction using Gemini's structured JSON output.
    
    This guarantees the response format matches our schema.
    """
    from google.genai import types
    
    # Build prompt for structured output
    prompt = build_structured_prompt(code, error_message, section)
    
    # System instruction with Manim context
    system_instruction = f"""You are a Manim code debugger. Analyze errors and provide fixes.

{MANIM_CONTEXT}

Provide fixes as search/replace pairs. The "search" field must EXACTLY match text in the code."""
    
    # Configure with JSON schema response
    config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=0.1,
        max_output_tokens=4096,
        response_mime_type="application/json",
        response_schema=DIFF_CORRECTION_SCHEMA,
    )
    
    try:
        print("[DiffCorrector] Using structured JSON output mode")
        
        response = await asyncio.to_thread(
            generator.client.models.generate_content,
            model=generator.CORRECTION_MODEL,
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
            generator.cost_tracker.track_usage(response, generator.CORRECTION_MODEL)
        except Exception:
            pass
        
        if not response or not response.text:
            print("[DiffCorrector] Empty response from LLM")
            return None
        
        # Parse JSON response
        try:
            result = json.loads(response.text)
            fixes = result.get("fixes", [])
        except json.JSONDecodeError as e:
            print(f"[DiffCorrector] Failed to parse JSON: {e}")
            print(f"[DiffCorrector] Response: {response.text[:300]}...")
            return None
        
        if not fixes:
            print("[DiffCorrector] No fixes in structured response")
            return None
        
        print(f"[DiffCorrector] Got {len(fixes)} fix(es) from structured output")
        
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
            print("[DiffCorrector] No valid blocks after filtering")
            return None
        
        # Log reasons if provided
        for i, fix in enumerate(fixes):
            if fix.get("reason"):
                print(f"[DiffCorrector] Fix {i+1}: {fix['reason']}")
        
        # Apply blocks
        new_code, successes, errors = apply_all_blocks(code, blocks)
        
        for msg in successes:
            print(f"[DiffCorrector] ✓ {msg}")
        for msg in errors:
            print(f"[DiffCorrector] ✗ {msg}")
        
        if not successes:
            print("[DiffCorrector] No blocks applied successfully")
            return None
        
        # Validate syntax
        syntax_error = validate_syntax(new_code)
        if syntax_error:
            print(f"[DiffCorrector] Syntax error after fixes: {syntax_error}")
            return None
        
        print(f"[DiffCorrector] ✓ Code fixed via structured output ({len(successes)} changes)")
        return new_code
        
    except Exception as e:
        print(f"[DiffCorrector] Structured output error: {e}")
        import traceback
        traceback.print_exc()
        return None


async def _try_text_based_correction(
    generator: "ManimGenerator",
    code: str,
    error_message: str,
    section: Dict[str, Any],
    attempt: int = 0
) -> Optional[str]:
    """
    Try correction using text-based SEARCH/REPLACE blocks.
    
    Traditional approach - parses blocks from free-form text response.
    """
    from google.genai import types
    
    # Build prompt with retry emphasis
    prompt = build_diff_correction_prompt(code, error_message, section)
    
    if attempt > 0:
        prompt = f"""RETRY {attempt + 1} - OUTPUT SEARCH/REPLACE BLOCKS ONLY.

Format:
<<<<<<< SEARCH
exact code to find
=======
replacement code
>>>>>>> REPLACE

{prompt}"""
    
    # Use stronger model on retries
    model = generator.CORRECTION_MODEL
    if attempt > 0 and USE_STRONG_MODEL_ON_RETRY:
        model = generator.STRONG_MODEL
        print(f"[DiffCorrector] Using stronger model: {model}")
    
    config = types.GenerateContentConfig(
        system_instruction=DIFF_CORRECTION_SYSTEM,
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
            print("[DiffCorrector] Empty response from LLM")
            return None
        
        response_text = response.text
        
        # Parse SEARCH/REPLACE blocks
        blocks = extract_blocks_from_fenced(response_text)
        
        if not blocks:
            print("[DiffCorrector] No SEARCH/REPLACE blocks found")
            preview = response_text[:300].replace('\n', ' ').strip()
            print(f"[DiffCorrector] Response preview: {preview}...")
            return None
        
        print(f"[DiffCorrector] Found {len(blocks)} block(s) in text response")
        
        # Apply blocks
        new_code, successes, errors = apply_all_blocks(code, blocks)
        
        for msg in successes:
            print(f"[DiffCorrector] ✓ {msg}")
        for msg in errors:
            print(f"[DiffCorrector] ✗ {msg}")
        
        if not successes:
            print("[DiffCorrector] No blocks applied successfully")
            return None
        
        # Validate syntax
        syntax_error = validate_syntax(new_code)
        if syntax_error:
            print(f"[DiffCorrector] Syntax error after fixes: {syntax_error}")
            return None
        
        print(f"[DiffCorrector] ✓ Code fixed via text blocks ({len(successes)} changes)")
        return new_code
        
    except Exception as e:
        print(f"[DiffCorrector] Text-based error: {e}")
        import traceback
        traceback.print_exc()
        return None
