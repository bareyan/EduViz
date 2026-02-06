"""
Refiner Stage

Orchestrates the validate → triage → fix cycle with four tiers:

1. **Deterministic fixes** (no LLM) — pattern-based code transforms for
   high-confidence spatial issues and known bad patterns.
2. **Verification** — lightweight LLM probe for uncertain issues to
   determine if they're real or false positives.
3. **LLM surgical fixes** — AdaptiveFixerAgent for confirmed complex errors.
4. **Discard** — verified false positives are dropped.

Every issue is a typed ``ValidationIssue``. No legacy string errors.
"""

from typing import Dict, Any, List, Optional, Tuple, Callable

from app.core import get_logger
from app.utils.section_status import SectionState

from ...config import (
    ENABLE_REFINEMENT_CYCLE,
    MAX_SURGICAL_FIX_ATTEMPTS,
)
from ..core.validation import StaticValidator, RuntimeValidator
from ..core.validation.models import (
    ValidationIssue,
)
from ..refinement import AdaptiveFixerAgent
from ..refinement.deterministic_fixer import DeterministicFixer
from ..refinement.issue_verifier import IssueVerifier


logger = get_logger(__name__, component="animation_refiner")


class Refiner:
    """Manages the iterative validation and smart-triage fixing cycle."""

    def __init__(
        self,
        fixer: AdaptiveFixerAgent,
        max_attempts: int = MAX_SURGICAL_FIX_ATTEMPTS,
    ):
        self.fixer = fixer
        self.max_attempts = max_attempts
        self.static_validator = StaticValidator()
        self.runtime_validator = RuntimeValidator()
        self.deterministic_fixer = DeterministicFixer()
        self.verifier = IssueVerifier(fixer.engine)
        self.last_runtime_issues: List[ValidationIssue] = []

    async def refine(
        self,
        code: str,
        section_title: str,
        context: Optional[Dict[str, Any]] = None,
        status_callback: Optional[Callable[[SectionState], None]] = None,
    ) -> Tuple[str, bool]:
        """Execute the full refinement cycle with smart triage.

        Flow per iteration:
        1. Static validation → if fail → LLM fix → continue
        2. Known-pattern deterministic fix (always)
        3. Runtime validation (with spatial checks)
           → if pass → done
           → if fail → triage issues:
               a. Auto-fixable → DeterministicFixer (no LLM)
               b. Uncertain → IssueVerifier probe → real→fix / false→discard
               c. Critical + not auto-fixable → LLM fixer

        Returns:
            Tuple of (refined_code, stabilized_bool).
        """
        if not ENABLE_REFINEMENT_CYCLE:
            logger.info(f"Refinement disabled for '{section_title}'")
            self.last_runtime_issues = []
            return code, True

        self.fixer.reset()
        self.last_runtime_issues = []

        current_code = code
        stats = {
            "attempts": 0,
            "static_failures": 0,
            "runtime_failures": 0,
            "deterministic_fixes": 0,
            "llm_fixes": 0,
            "verified_real": 0,
            "verified_false_positives": 0,
        }

        logger.info(
            f"Starting refinement for '{section_title}'",
            extra={
                "section_title": section_title,
                "max_attempts": self.max_attempts,
                "refinement_stage": "start",
            },
        )

        for turn_idx in range(1, self.max_attempts + 1):
            stats["attempts"] += 1

            # ── Phase 1: Static validation ───────────────────────────
            static_result = await self.static_validator.validate(current_code)

            if not static_result.valid:
                stats["static_failures"] += 1
                self._log_issues("static", turn_idx, static_result.issues, section_title)
                error_context = static_result.error_summary()
                self._report_status(status_callback, "fixing_manim", section_title, turn_idx)
                current_code = await self._apply_llm_fix(
                    current_code, error_context, turn_idx, context
                )
                stats["llm_fixes"] += 1
                continue

            logger.info(f"Static validation PASSED (Turn {turn_idx})")

            # ── Phase 2: Known-pattern deterministic fixes ───────────
            current_code, pattern_fixes = (
                self.deterministic_fixer.fix_known_patterns(current_code)
            )
            stats["deterministic_fixes"] += pattern_fixes

            # ── Phase 3: Runtime validation (with spatial checks) ────
            runtime_result = await self.runtime_validator.validate(
                current_code, enable_spatial_checks=True
            )

            self.last_runtime_issues = runtime_result.issues

            if runtime_result.valid:
                logger.info(
                    f"Refinement successful for '{section_title}' "
                    f"(Turn {turn_idx})",
                    extra={**stats, "refinement_stage": "success"},
                )
                return current_code, True

            # ── Phase 4: Smart triage ────────────────────────────────
            stats["runtime_failures"] += 1
            self._log_issues(
                "runtime", turn_idx, runtime_result.issues, section_title
            )

            current_code, triage_stats = await self._triage_issues(
                current_code,
                runtime_result.issues,
                turn_idx,
                section_title,
                context,
                status_callback=status_callback,
            )
            stats["deterministic_fixes"] += triage_stats["deterministic"]
            stats["llm_fixes"] += triage_stats["llm"]
            stats["verified_real"] += triage_stats["verified_real"]
            stats["verified_false_positives"] += triage_stats["verified_false_positives"]

            # If triage resolved everything (only false positives left)
            if triage_stats["unresolved"] == 0:
                logger.info(
                    f"All issues resolved/discarded for '{section_title}' (Turn {turn_idx})",
                    extra={**stats, "refinement_stage": "triage_resolved"},
                )
                return current_code, True

        # ── Exhausted ────────────────────────────────────────────────
        logger.warning(
            f"Refinement exhausted for '{section_title}'",
            extra={**stats, "refinement_stage": "exhausted"},
        )

        # If only spatial issues remain, proceed to render
        if self._only_spatial_remaining(runtime_result.issues if 'runtime_result' in dir() else []):
            logger.warning(
                f"Only spatial issues remain — proceeding to render for '{section_title}'",
                extra={**stats, "refinement_stage": "spatial_proceed"},
            )
            return current_code, True

        return current_code, False

    async def apply_issues(
        self,
        code: str,
        issues: List[ValidationIssue],
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, Dict[str, int]]:
        """Apply fixes for externally supplied issues without re-validating."""
        if not issues:
            return code, {
                "deterministic": 0,
                "llm": 0,
                "verified_real": 0,
                "verified_false_positives": 0,
                "unresolved": 0,
            }

        self.fixer.reset()
        return await self._triage_issues(code, issues, 1, context)

    # ── Triage ───────────────────────────────────────────────────────────

    async def _triage_issues(
        self,
        code: str,
        issues: List[ValidationIssue],
        turn_idx: int,
        section_title: str,
        context: Optional[Dict[str, Any]],
        status_callback: Optional[Callable[[SectionState], None]] = None,
    ) -> Tuple[str, Dict[str, int]]:
        """Route issues through the four fix tiers.

        Returns:
            Tuple of (fixed_code, stats_dict).
        """
        triage_stats = {
            "deterministic": 0,
            "llm": 0,
            "verified_real": 0,
            "verified_false_positives": 0,
            "unresolved": 0,
        }

        # Partition issues by routing
        auto_fixable = [i for i in issues if i.should_auto_fix]
        uncertain = [i for i in issues if i.needs_verification]
        llm_needed = [i for i in issues if i.requires_llm]

        logger.info(
            f"Triage: {len(auto_fixable)} auto-fixable, "
            f"{len(uncertain)} need verification, "
            f"{len(llm_needed)} need LLM"
        )

        # Tier 1: Deterministic fixes
        if auto_fixable:
            code, remaining, fixes = self.deterministic_fixer.fix(
                code, auto_fixable
            )
            triage_stats["deterministic"] = fixes
            llm_needed.extend(remaining)

        # Tier 2: Verify uncertain issues
        if uncertain:
            verification = await self.verifier.verify(code, uncertain)
            triage_stats["verified_real"] = len(verification.real)
            triage_stats["verified_false_positives"] = len(verification.false_positives)

            # Verified-real issues that are auto-fixable get one more shot
            for confirmed in verification.real:
                if confirmed.should_auto_fix:
                    code_attempt, remaining, fixes = self.deterministic_fixer.fix(
                        code, [confirmed]
                    )
                    if fixes > 0:
                        code = code_attempt
                        triage_stats["deterministic"] += fixes
                    else:
                        llm_needed.extend(remaining)
                else:
                    llm_needed.append(confirmed)

            for fp in verification.false_positives:
                logger.debug(
                    f"Discarded false positive: {fp.message[:60]}"
                )

        # Tier 3: LLM fixes for everything that couldn't be resolved
        if llm_needed:
            error_context = "\n".join(
                issue.to_fixer_context() for issue in llm_needed
            )
            self._report_status(status_callback, "fixing_manim", section_title, turn_idx)
            code = await self._apply_llm_fix(
                code, error_context, turn_idx, context
            )
            triage_stats["llm"] = len(llm_needed)

        # Count truly unresolved (LLM might not fix everything)
        triage_stats["unresolved"] = len(llm_needed)

        return code, triage_stats

    # ── Fix helpers ──────────────────────────────────────────────────────

    async def _apply_llm_fix(
        self,
        code: str,
        errors: str,
        turn_idx: int,
        context: Optional[Dict[str, Any]],
    ) -> str:
        """Apply fix using the LLM fixer agent."""
        logger.info(f"Applying LLM fix (Turn {turn_idx})...")

        code_before = code
        new_code, meta = await self.fixer.run_turn(code, errors, context)

        if new_code != code_before:
            logger.info(
                f"LLM fix applied "
                f"(length: {len(code_before)} -> {len(new_code)})"
            )
        else:
            logger.warning("LLM fix returned unchanged code")

        return new_code

    # ── Classification helpers ───────────────────────────────────────────

    @staticmethod
    def _only_spatial_remaining(issues: List[ValidationIssue]) -> bool:
        """Check if only spatial issues remain (safe to proceed)."""
        if not issues:
            return True
        return all(issue.is_spatial for issue in issues)

    # ── Logging ──────────────────────────────────────────────────────────

    def _log_issues(
        self,
        validation_type: str,
        turn_idx: int,
        issues: List[ValidationIssue],
        section_title: str,
    ) -> None:
        """Log validation failure details from structured issues."""
        logger.warning(
            f"{validation_type.title()} validation FAILED "
            f"(Turn {turn_idx}/{self.max_attempts})",
            extra={
                "turn": turn_idx,
                "validation_type": validation_type,
                "issue_count": len(issues),
                "section_title": section_title,
            },
        )
        for i, issue in enumerate(issues[:5], 1):
            logger.warning(
                f"  Issue {i} [{issue.severity.value}/{issue.confidence.value}]: "
                f"{issue.message[:120]}"
            )
        if len(issues) > 5:
            logger.warning(f"  ... and {len(issues) - 5} more issues")

    def _report_status(
        self,
        status_callback: Optional[Callable[[SectionState], None]],
        status: SectionState,
        section_title: str,
        turn_idx: int,
    ) -> None:
        """Safely report status updates to the caller."""
        if not status_callback:
            return
        try:
            status_callback(status)
        except Exception as e:
            logger.warning(
                f"Failed to report status '{status}' for '{section_title}': {e}",
                extra={"section_title": section_title, "turn": turn_idx, "status": status},
            )
