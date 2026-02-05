"""
Refiner Stage

Coordinates validation and fixing iterations.

Single Responsibility: Orchestrate refinement cycle
"""

from typing import Dict, Any, Optional, Tuple

from app.core import get_logger

from ...config import (
    ENABLE_REFINEMENT_CYCLE,
    MAX_SURGICAL_FIX_ATTEMPTS
)
from ..core.validation import StaticValidator, RuntimeValidator
from ..refinement import AdaptiveFixerAgent


logger = get_logger(__name__, component="animation_refiner")


class Refiner:
    """Manages iterative validation and fixing cycle."""
    
    def __init__(
        self,
        fixer: AdaptiveFixerAgent,
        max_attempts: int = MAX_SURGICAL_FIX_ATTEMPTS
    ):
        """Initialize refiner with dependencies.
        
        Args:
            fixer: Adaptive fixer agent for intelligent code corrections
            max_attempts: Maximum refinement iterations
        """
        self.fixer = fixer
        self.max_attempts = max_attempts
        self.static_validator = StaticValidator()
        self.runtime_validator = RuntimeValidator()
    
    async def refine(
        self,
        code: str,
        section_title: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Tuple[str, bool]:
        """Execute refinement cycle with validation.
        
        Args:
            code: Initial code to refine
            section_title: Section title for logging
            context: Optional context
            
        Returns:
            Tuple of (refined_code, stabilized_bool)
        """
        if not ENABLE_REFINEMENT_CYCLE:
            logger.info(f"Refinement disabled for '{section_title}'")
            return code, True
        
        # Reset fixer state for new session
        self.fixer.reset()
        
        current_code = code
        stats = {
            "attempts": 0,
            "static_failures": 0,
            "runtime_failures": 0
        }
        
        logger.info(
            f"Starting refinement for '{section_title}'",
            extra={
                "section_title": section_title,
                "max_attempts": self.max_attempts,
                "refinement_stage": "start"
            }
        )
        
        for turn_idx in range(1, self.max_attempts + 1):
            stats["attempts"] += 1
            
            # Validate static structure
            static_result = await self.static_validator.validate(current_code)
            
            if not static_result.valid:
                stats["static_failures"] += 1
                error_data = "\n".join(static_result.errors)
                self._log_validation_failure(
                    "static",
                    turn_idx,
                    static_result.errors,
                    section_title
                )
                
                # Fix errors
                current_code = await self._apply_fix(
                    current_code,
                    error_data,
                    turn_idx,
                    context
                )
                continue
            
            # Static passed, check runtime
            logger.info(f"✅ Static validation PASSED (Turn {turn_idx})")
            runtime_result = await self.runtime_validator.validate(current_code)
            
            if runtime_result.valid:
                logger.info(
                    f"Refinement successful for '{section_title}' (Turn {turn_idx})",
                    extra={**stats, "refinement_stage": "success"}
                )
                return current_code, True
            
            # Runtime failed
            stats["runtime_failures"] += 1
            error_data = "\n".join(runtime_result.errors)
            self._log_validation_failure(
                "runtime",
                turn_idx,
                runtime_result.errors,
                section_title
            )
            
            # Fix errors
            current_code = await self._apply_fix(
                current_code,
                error_data,
                turn_idx,
                context
            )
        
        logger.warning(
            f"Refinement exhausted for '{section_title}'",
            extra={**stats, "refinement_stage": "exhausted"}
        )
        return current_code, False
    
    async def _apply_fix(
        self,
        code: str,
        errors: str,
        turn_idx: int,
        context: Optional[Dict[str, Any]]
    ) -> str:
        """Apply fix using fixer agent.
        
        Args:
            code: Current code
            errors: Error messages
            turn_idx: Current iteration number
            context: Optional context
            
        Returns:
            Fixed code (or original if fix failed)
        """
        logger.info(f"🔧 Applying fix (Turn {turn_idx})...")
        
        code_before = code
        new_code, meta = await self.fixer.run_turn(code, errors, context)
        
        if new_code != code_before:
            logger.info(
                f"✅ Fix applied (length: {len(code_before)} → {len(new_code)})"
            )
        else:
            logger.warning(f"⚠️  Fix returned unchanged code")
        
        return new_code
    
    def _log_validation_failure(
        self,
        validation_type: str,
        turn_idx: int,
        errors: list,
        section_title: str
    ) -> None:
        """Log validation failure details.
        
        Args:
            validation_type: "static" or "runtime"
            turn_idx: Current iteration number
            errors: List of error messages
            section_title: Section title
        """
        logger.warning(
            f"❌ {validation_type.title()} validation FAILED "
            f"(Turn {turn_idx}/{self.max_attempts})",
            extra={
                "turn": turn_idx,
                "validation_type": validation_type,
                "error_count": len(errors),
                "section_title": section_title
            }
        )
        
        # Log first few errors
        for i, error in enumerate(errors[:5], 1):
            logger.warning(f"  Error {i}: {error}")
        
        if len(errors) > 5:
            logger.warning(f"  ... and {len(errors) - 5} more errors")
