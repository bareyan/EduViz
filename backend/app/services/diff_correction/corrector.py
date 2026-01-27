"""
Diff-based Code Corrector

Main orchestrator that uses SEARCH/REPLACE blocks for efficient error correction.
Falls back to full regeneration if diff approach fails.
"""

import asyncio
from typing import Optional, Dict, Any, TYPE_CHECKING

from .parser import extract_blocks_from_fenced
from .applier import apply_all_blocks, validate_syntax
from .prompts import DIFF_CORRECTION_SYSTEM, build_diff_correction_prompt

if TYPE_CHECKING:
    from app.services.manim_generator import ManimGenerator


class DiffCorrector:
    """
    Diff-based code corrector using SEARCH/REPLACE blocks.
    
    Attributes:
        generator: The ManimGenerator instance for API access
        max_diff_attempts: Max attempts using diff approach before fallback
        enable_fallback: Whether to fallback to full regeneration
    """

    def __init__(
        self,
        generator: "ManimGenerator",
        max_diff_attempts: int = 5,
        enable_fallback: bool = True
    ):
        self.generator = generator
        self.max_diff_attempts = max_diff_attempts
        self.enable_fallback = enable_fallback

        # Stats tracking
        self.stats = {
            'diff_attempts': 0,
            'diff_successes': 0,
            'fallback_attempts': 0,
            'fallback_successes': 0,
        }

    async def correct_code(
        self,
        original_code: str,
        error_message: str,
        section: Optional[Dict[str, Any]] = None,
        attempt: int = 0
    ) -> Optional[str]:
        """
        Correct code errors using diff-based approach.
        
        Args:
            original_code: The code with errors
            error_message: Error message from Manim
            section: Optional section info for context
            attempt: Current attempt number
            
        Returns:
            Fixed code if successful, None otherwise
        """
        # Try diff-based correction
        if attempt < self.max_diff_attempts:
            result = await self._try_diff_correction(original_code, error_message, section)
            if result:
                self.stats['diff_successes'] += 1
                return result

        # Fallback to full regeneration if enabled
        if self.enable_fallback:
            print(f"[DiffCorrector] Diff approach failed after {attempt} attempts, falling back...")
            return await self._fallback_full_correction(original_code, error_message, section)

        return None

    async def _try_diff_correction(
        self,
        code: str,
        error_message: str,
        section: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Try to fix code using SEARCH/REPLACE blocks.
        
        Returns:
            Fixed code if successful, None otherwise
        """
        # Use generator's types module (supports both API and Vertex AI)
        types = self.generator.types

        self.stats['diff_attempts'] += 1

        # Build prompt
        prompt = build_diff_correction_prompt(code, error_message, section)

        try:
            from app.services.prompting_engine import PromptConfig
            correction_config = PromptConfig(
                temperature=0.1,
                max_output_tokens=2048,
                timeout=60
            )
            
            response_text = await self.generator.correction_engine.generate(
                prompt=prompt,
                config=correction_config
            )

            if not response_text:
                print("[DiffCorrector] Empty response from LLM")
                return None

            # Parse SEARCH/REPLACE blocks
            blocks = extract_blocks_from_fenced(response_text)

            if not blocks:
                # Log preview to help debug why no blocks were found
                preview = response_text[:300].replace('\n', ' ')
                print("[DiffCorrector] No SEARCH/REPLACE blocks found in response")
                print(f"[DiffCorrector] Response preview: {preview}...")

                # Check if response contains the markers at all
                has_search = "<<<" in response_text and "SEARCH" in response_text.upper()
                has_replace = ">>>" in response_text and "REPLACE" in response_text.upper()
                if has_search or has_replace:
                    print("[DiffCorrector] Response has markers but parsing failed - check format")

                return None

            print(f"[DiffCorrector] Found {len(blocks)} SEARCH/REPLACE block(s)")

            # Apply blocks
            new_code, successes, errors = apply_all_blocks(code, blocks)

            for msg in successes:
                print(f"[DiffCorrector] ✓ {msg}")
            for msg in errors:
                print(f"[DiffCorrector] ✗ {msg}")

            # Check if any blocks applied
            if not successes:
                print("[DiffCorrector] No blocks applied successfully")
                return None

            # Validate syntax
            syntax_error = validate_syntax(new_code)
            if syntax_error:
                print(f"[DiffCorrector] Syntax error after applying fixes: {syntax_error}")
                return None

            print(f"[DiffCorrector] ✓ Code fixed successfully ({len(successes)} changes)")
            return new_code

        except Exception as e:
            print(f"[DiffCorrector] Error during correction: {e}")
            return None

    async def _fallback_full_correction(
        self,
        code: str,
        error_message: str,
        section: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Fallback to full code regeneration.
        
        Uses the existing correct_manim_code function from renderer.
        """
        self.stats['fallback_attempts'] += 1

        # Import here to avoid circular dependency
        from app.services.manim_generator.renderer import correct_manim_code

        result = await correct_manim_code(
            self.generator,
            code,
            error_message,
            section or {},
            attempt=0  # Reset attempt for full correction
        )

        if result:
            self.stats['fallback_successes'] += 1

        return result

    def get_stats(self) -> Dict[str, Any]:
        """Get correction statistics"""
        total_attempts = self.stats['diff_attempts'] + self.stats['fallback_attempts']
        total_successes = self.stats['diff_successes'] + self.stats['fallback_successes']

        return {
            **self.stats,
            'total_attempts': total_attempts,
            'total_successes': total_successes,
            'diff_success_rate': (
                self.stats['diff_successes'] / self.stats['diff_attempts']
                if self.stats['diff_attempts'] > 0 else 0
            ),
            'overall_success_rate': (
                total_successes / total_attempts
                if total_attempts > 0 else 0
            ),
        }

    def print_stats(self):
        """Print correction statistics"""
        stats = self.get_stats()
        print("\n" + "="*50)
        print("DIFF CORRECTION STATISTICS")
        print("="*50)
        print(f"Diff Attempts:      {stats['diff_attempts']}")
        print(f"Diff Successes:     {stats['diff_successes']} ({stats['diff_success_rate']:.1%})")
        print(f"Fallback Attempts:  {stats['fallback_attempts']}")
        print(f"Fallback Successes: {stats['fallback_successes']}")
        print(f"Overall Success:    {stats['total_successes']}/{stats['total_attempts']} ({stats['overall_success_rate']:.1%})")
        print("="*50 + "\n")
