"""
Refiner Stage

Orchestrates the validate → triage → fix cycle with the
"Certain vs. Uncertain" routing model:

1. **Certain Issues**: We are confident this is broken.
   → Route directly to Fixer (Deterministic or LLM).
   
2. **Uncertain Issues**: It might be broken, but we're not sure.
   → Check whitelist first (skip if known false positive).
   → If not whitelisted → verify with IssueVerifier (Vision LLM).
   → If verified as real:
      - auto-fixable → deterministic fixer
      - non-auto-fixable → LLM fixer
   → If false positive → add to whitelist (skip next time).

The whitelist is session-scoped and resets between section generations,
so we don't "learn" bad habits.

All issues are typed ``ValidationIssue`` objects with severity, confidence, and category.
"""

from typing import Dict, Any, List, Optional, Tuple, Callable
import tempfile
from pathlib import Path

from app.core import get_logger
from app.utils.section_status import SectionState

from ...config import (
    ENABLE_REFINEMENT_CYCLE,
    MAX_LLM_FIX_ISSUES_PER_TURN,
    MAX_SURGICAL_FIX_ATTEMPTS,
)
from ..core.validation import StaticValidator, RuntimeValidator
from ..core.validation.models import (
    ValidationIssue,
)
from ..refinement import (
    AdaptiveFixerAgent,
    CSTFixer,
    FalsePositiveWhitelist,
    IssueRouter,
    IssueVerifier,
)

logger = get_logger(__name__, component="animation_refiner")


class Refiner:
    """Manages the iterative validation and smart-triage fixing cycle.
    
    Uses the "Certain vs. Uncertain" routing model:
    - Certain issues → fix directly
    - Uncertain issues → verify with IssueVerifier → if real, fix; if false, whitelist
    """

    def __init__(
        self,
        fixer: AdaptiveFixerAgent,
        verifier_engine=None,
        max_attempts: int = MAX_SURGICAL_FIX_ATTEMPTS,
    ):
        self.fixer = fixer
        self.max_attempts = max_attempts
        self.static_validator = StaticValidator()
        self.runtime_validator = RuntimeValidator()
        self.deterministic_fixer = CSTFixer()
        self.router = IssueRouter()
        
        # IssueVerifier for verifying uncertain issues with LLM
        self.issue_verifier = IssueVerifier(verifier_engine) if verifier_engine else None
        
        # Session-scoped whitelist for verified false positives
        self.whitelist = FalsePositiveWhitelist()
        
        # Track pending issues for Visual QC post-render
        self.last_runtime_issues: List[ValidationIssue] = []
        self.pending_uncertain_issues: List[ValidationIssue] = []

    async def refine(
        self,
        code: str,
        section_title: str,
        context: Optional[Dict[str, Any]] = None,
        status_callback: Optional[Callable[[SectionState], None]] = None,
    ) -> Tuple[str, bool]:
        """Execute the full refinement cycle with the Certain/Uncertain model.

        Flow per iteration:
        1. Static validation → if fail → LLM fix → continue
        2. Known-pattern deterministic fix (always)
        3. Runtime validation (with spatial checks)
           → if pass → done
           → if fail → triage issues:
               a. Certain + auto-fixable → CSTFixer (no LLM)
               b. Certain + requires LLM → LLM fixer
               c. Uncertain → verify with IssueVerifier:
                  - Real + auto-fixable → CSTFixer
                  - Real + non-auto-fixable → LLM fixer
                  - False positive → add to whitelist

        Returns:
            Tuple of (refined_code, stabilized_bool).
        """
        if not ENABLE_REFINEMENT_CYCLE:
            logger.info(f"Refinement disabled for '{section_title}'")
            self.last_runtime_issues = []
            self.pending_uncertain_issues = []
            return code, True

        self.fixer.reset()
        # Reset whitelist for new section (don't carry over bad habits)
        self.whitelist.reset()
        self.last_runtime_issues = []
        self.pending_uncertain_issues = []

        current_code = code
        stats = {
            "attempts": 0,
            "static_failures": 0,
            "runtime_failures": 0,
            "deterministic_fixes": 0,
            "llm_fixes": 0,
            "deferred_to_visual_qc": 0,
            "skipped_whitelisted": 0,
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
            frames_tmpdir = tempfile.TemporaryDirectory()
            frames_dir = Path(frames_tmpdir.name)

            try:
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
                if pattern_fixes:
                    logger.info(
                        f"Applied {pattern_fixes} known-pattern fixes",
                        extra={
                            "section_title": section_title,
                            "turn": turn_idx,
                            "refinement_stage": "pattern_fix",
                            "fixes": pattern_fixes,
                        },
                    )

                # ── Phase 3: Runtime validation (with spatial checks) ────
                runtime_result = await self.runtime_validator.validate(
                    current_code, enable_spatial_checks=True, frames_dir=frames_dir
                )

                # Resolve frame paths for verification
                for issue in runtime_result.issues:
                    if issue.details and issue.details.get("frame_file"):
                        frame_path = frames_dir / issue.details["frame_file"]
                        if frame_path.exists():
                            issue.details["frame_path"] = str(frame_path)

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
                stats["deferred_to_visual_qc"] += triage_stats.get("deferred_to_visual_qc", 0)
                stats["skipped_whitelisted"] += triage_stats.get("skipped_whitelisted", 0)

                # If triage resolved everything (only uncertain/whitelisted left)
                if triage_stats.get("unresolved", 0) == 0:
                    logger.info(
                        f"All issues resolved/discarded for '{section_title}' (Turn {turn_idx})",
                        extra={**stats, "refinement_stage": "triage_resolved"},
                    )
                    return current_code, True
            finally:
                frames_tmpdir.cleanup()

        # ── Exhausted ────────────────────────────────────────────────
        logger.warning(
            f"Refinement exhausted for '{section_title}'",
            extra={**stats, "refinement_stage": "exhausted"},
        )

        # If only spatial/uncertain issues remain, proceed to render
        # (Visual QC will verify uncertain issues post-render)
        if self.router.only_spatial_remaining(self.last_runtime_issues):
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
        section_title: str = "unknown",
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[str, Dict[str, int]]:
        """Apply fixes for externally supplied issues without re-validating."""
        if not issues:
            return code, {
                "deterministic": 0,
                "llm": 0,
                "deferred_to_visual_qc": 0,
                "skipped_whitelisted": 0,
                "unresolved": 0,
            }

        self.fixer.reset()
        return await self._triage_issues(code, issues, 1, section_title, context)

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
        """Route issues using the Certain/Uncertain model with inline verification."""
        
        # Use extracted router for partitioning
        partitions = self.router.triage_issues(
            issues, 
            whitelist_filter=self.whitelist.filter_uncertain
        )
        
        triage_stats = self.router.summarize_triage(partitions)
        triage_stats["unresolved"] = 0
        triage_stats["verified_real"] = 0
        triage_stats["verified_false_positive"] = 0
        triage_stats["deterministic"] = 0
        triage_stats["llm"] = 0
        triage_stats["deferred_to_visual_qc"] = 0
        triage_stats["skipped_whitelisted"] = len(partitions["whitelisted"])

        verified_real_auto_fixable: List[ValidationIssue] = []
        verified_real_llm_needed: List[ValidationIssue] = []

        # Tier 1: Verify uncertain issues first (if verifier available)
        if partitions["uncertain"]:
            if self.issue_verifier:
                logger.info(
                    f"Verifying {len(partitions['uncertain'])} uncertain issues with IssueVerifier"
                )
                verification_result = await self.issue_verifier.verify(
                    code, partitions["uncertain"]
                )
                
                # Real issues → route to LLM fixer
                if verification_result.real:
                    logger.info(
                        f"IssueVerifier confirmed {len(verification_result.real)} real issues"
                    )
                    triage_stats["verified_real"] = len(verification_result.real)
                    for verified_issue in verification_result.real:
                        if verified_issue.auto_fixable:
                            verified_real_auto_fixable.append(verified_issue)
                        else:
                            verified_real_llm_needed.append(verified_issue)
                
                # False positives → add to whitelist
                if verification_result.false_positives:
                    logger.info(
                        f"IssueVerifier identified {len(verification_result.false_positives)} false positives"
                    )
                    self.whitelist.add_all(verification_result.false_positives)
                    triage_stats["verified_false_positive"] = len(verification_result.false_positives)
            else:
                # No verifier available - defer all uncertain issues to Visual QC
                self.pending_uncertain_issues.extend(partitions["uncertain"])
                triage_stats["deferred_to_visual_qc"] = len(partitions["uncertain"])

        # Tier 2: Deterministic fixes for all auto-fixable real issues
        deterministic_batch = list(partitions["certain_auto_fixable"])
        deterministic_batch.extend(verified_real_auto_fixable)
        if deterministic_batch:
            code, remaining, fixes = self.deterministic_fixer.fix(
                code, deterministic_batch
            )
            triage_stats["deterministic"] = fixes
            # Any that couldn't be auto-fixed need LLM fallback.
            partitions["certain_llm_needed"].extend(remaining)

        # Tier 3: LLM fixes for non-auto-fixable real issues
        llm_batch = list(partitions["certain_llm_needed"])
        llm_batch.extend(verified_real_llm_needed)
        llm_batch = self._dedupe_issues(llm_batch)
        if len(llm_batch) > MAX_LLM_FIX_ISSUES_PER_TURN:
            logger.info(
                "Capping LLM fixer issue context",
                extra={
                    "requested": len(llm_batch),
                    "capped_to": MAX_LLM_FIX_ISSUES_PER_TURN,
                },
            )
            llm_batch = llm_batch[:MAX_LLM_FIX_ISSUES_PER_TURN]
        if llm_batch:
            error_context = "\n".join(
                issue.to_fixer_context() for issue in llm_batch
            )
            self._report_status(status_callback, "fixing_manim", section_title, turn_idx)
            code = await self._apply_llm_fix(
                code, error_context, turn_idx, context
            )
            triage_stats["llm"] = len(llm_batch)
            triage_stats["unresolved"] = len(llm_batch)

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

    # ── Visual QC Integration ────────────────────────────────────────────

    def get_pending_uncertain_issues(self) -> List[ValidationIssue]:
        """Get issues deferred to Visual QC for post-render verification."""
        return list(self.pending_uncertain_issues)

    def mark_as_false_positives(self, issues: List[ValidationIssue]) -> None:
        """Add issues to the whitelist (Visual QC confirmed as not problems)."""
        self.whitelist.add_all(issues)
        # Remove from pending list
        whitelisted_keys = {i.whitelist_key for i in issues}
        self.pending_uncertain_issues = [
            i for i in self.pending_uncertain_issues
            if i.whitelist_key not in whitelisted_keys
        ]

    def mark_as_real_issues(self, issues: List[ValidationIssue]) -> None:
        """Mark issues as confirmed real by Visual QC."""
        confirmed_keys = {i.whitelist_key for i in issues}
        self.pending_uncertain_issues = [
            i for i in self.pending_uncertain_issues
            if i.whitelist_key not in confirmed_keys
        ]

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
                "issue_samples": self._summarize_issues(issues),
            },
        )
        for i, issue in enumerate(issues[:5], 1):
            logger.warning(
                f"  Issue {i} [{issue.severity.value}/{issue.confidence.value}]: "
                f"{issue.message[:120]}"
            )
        if len(issues) > 5:
            logger.warning(f"  ... and {len(issues) - 5} more issues")

    @staticmethod
    def _issue_snapshot(issue: ValidationIssue) -> Dict[str, Any]:
        """Create a compact, log-friendly issue snapshot."""
        return {
            "category": issue.category.value,
            "severity": issue.severity.value,
            "confidence": issue.confidence.value,
            "auto_fixable": issue.auto_fixable,
            "line": issue.line,
            "is_certain": issue.is_certain,
            "is_uncertain": issue.is_uncertain,
            "whitelist_key": issue.whitelist_key,
            "message": issue.message[:160],
        }

    def _summarize_issues(self, issues: List[ValidationIssue], limit: int = 6) -> List[Dict[str, Any]]:
        """Summarize issues for logging (truncate to keep logs readable)."""
        return [self._issue_snapshot(i) for i in issues[:limit]]

    @staticmethod
    def _dedupe_issues(issues: List[ValidationIssue]) -> List[ValidationIssue]:
        """Dedupe issue list while preserving original order."""
        seen: set[str] = set()
        deduped: List[ValidationIssue] = []
        for issue in issues:
            key = f"{issue.category.value}:{issue.whitelist_key}:{issue.message}"
            if key in seen:
                continue
            seen.add(key)
            deduped.append(issue)
        return deduped

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
