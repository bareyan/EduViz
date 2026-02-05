"""
Issue Verifier

Lightweight LLM probe that checks whether low-confidence validation issues
are REAL problems or false positives.

Instead of blindly skipping uncertain issues, we send a cheap, focused
question to the LLM: "Is this a real problem?" — and act on the answer.

Token cost: ~200-400 tokens per verification (vs. ~2000-4000 for a full fix).
Latency: ~1-3 seconds per probe.

Usage:
    verifier = IssueVerifier(engine)
    verified = await verifier.verify(code, uncertain_issues)
    # verified.real    → issues confirmed as real problems → route to fixer
    # verified.false_positives → confirmed harmless → discard
"""

from dataclasses import dataclass, field
from typing import List

from app.core import get_logger
from app.services.infrastructure.llm import PromptingEngine, PromptConfig

from ...config import (
    VERIFICATION_BATCH_SIZE,
    VERIFICATION_TEMPERATURE,
    VERIFICATION_TIMEOUT,
    VERIFICATION_MAX_RETRIES,
)
from ...prompts import VERIFIER_SYSTEM
from ..core.validation.models import (
    IssueConfidence,
    IssueSeverity,
    ValidationIssue,
)

logger = get_logger(__name__, component="issue_verifier")


@dataclass
class VerificationResult:
    """Outcome of verifying a batch of uncertain issues."""

    real: List[ValidationIssue] = field(default_factory=list)
    false_positives: List[ValidationIssue] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.real) + len(self.false_positives)


class IssueVerifier:
    """Verifies uncertain validation issues via lightweight LLM probe."""

    def __init__(self, engine: PromptingEngine):
        self.engine = engine

    async def verify(
        self,
        code: str,
        issues: List[ValidationIssue],
    ) -> VerificationResult:
        """Verify a list of uncertain issues.

        Args:
            code: The Manim source code being validated.
            issues: Issues with low confidence / INFO severity.

        Returns:
            VerificationResult with issues split into real vs false_positive.
        """
        result = VerificationResult()

        if not issues:
            return result

        # Process in batches to keep prompts focused
        for batch_start in range(0, len(issues), VERIFICATION_BATCH_SIZE):
            batch = issues[batch_start : batch_start + VERIFICATION_BATCH_SIZE]
            batch_result = await self._verify_batch(code, batch)
            result.real.extend(batch_result.real)
            result.false_positives.extend(batch_result.false_positives)

        logger.info(
            f"Verification complete: {len(result.real)} real, "
            f"{len(result.false_positives)} false positives "
            f"(out of {result.total} checked)"
        )
        return result

    async def _verify_batch(
        self,
        code: str,
        issues: List[ValidationIssue],
    ) -> VerificationResult:
        """Verify a single batch of issues."""
        result = VerificationResult()

        # Build the verification prompt
        prompt = self._build_prompt(code, issues)

        try:
            llm_result = await self.engine.generate(
                prompt=prompt,
                system_prompt=VERIFIER_SYSTEM.template,
                config=PromptConfig(
                    temperature=VERIFICATION_TEMPERATURE,
                    max_output_tokens=500,
                    response_format="json",
                    require_json_valid=True,
                    timeout=VERIFICATION_TIMEOUT,
                    max_retries=VERIFICATION_MAX_RETRIES,
                ),
                context={"stage": "issue_verification"},
            )

            if not llm_result.get("success"):
                logger.warning(
                    f"Verification LLM call failed: {llm_result.get('error')}. "
                    "Treating all as real (conservative)."
                )
                result.real.extend(issues)
                return result

            verdicts = self._parse_verdicts(llm_result, issues)
            for issue, is_real in verdicts:
                if is_real:
                    # Promote confidence since LLM confirmed it
                    promoted = ValidationIssue(
                        severity=issue.severity if issue.severity != IssueSeverity.INFO else IssueSeverity.WARNING,
                        confidence=IssueConfidence.MEDIUM,
                        category=issue.category,
                        message=issue.message + " [verified]",
                        auto_fixable=issue.auto_fixable,
                        fix_hint=issue.fix_hint,
                        details=issue.details,
                        line=issue.line,
                    )
                    result.real.append(promoted)
                else:
                    result.false_positives.append(issue)

        except Exception as e:
            logger.warning(
                f"Verification failed ({e}). Treating all as real (conservative)."
            )
            result.real.extend(issues)

        return result

    @staticmethod
    def _build_prompt(code: str, issues: List[ValidationIssue]) -> str:
        """Build a concise verification prompt."""
        # Show only relevant code snippet (first 150 lines max)
        code_lines = code.splitlines()
        if len(code_lines) > 150:
            code_snippet = "\n".join(code_lines[:150]) + "\n# ... (truncated)"
        else:
            code_snippet = code

        issue_list = []
        for i, issue in enumerate(issues):
            issue_list.append(
                f"{i}. [{issue.category.value}] {issue.message}"
                + (f" (details: {issue.details})" if issue.details else "")
            )

        return (
            f"Here is the Manim code:\n```python\n{code_snippet}\n```\n\n"
            f"The spatial validator flagged these uncertain issues:\n"
            + "\n".join(issue_list)
            + "\n\nFor each issue (by index), is it REAL or FALSE_POSITIVE?"
        )

    @staticmethod
    def _parse_verdicts(
        llm_result: dict,
        issues: List[ValidationIssue],
    ) -> List[tuple[ValidationIssue, bool]]:
        """Parse LLM verdicts and pair with original issues.

        Falls back to treating issues as real on parse failure.
        """
        verdicts: List[tuple[ValidationIssue, bool]] = []
        parsed = llm_result.get("parsed_json")

        if not isinstance(parsed, list):
            # Try extracting from response text
            text = llm_result.get("response", "")
            # Fallback: count REAL/FALSE_POSITIVE occurrences
            for i, issue in enumerate(issues):
                is_real = "REAL" in text  # Conservative
                verdicts.append((issue, is_real))
            return verdicts

        # Map index → verdict
        verdict_map: dict[int, bool] = {}
        for item in parsed:
            if isinstance(item, dict):
                idx = item.get("index", -1)
                v = str(item.get("verdict", "")).upper()
                verdict_map[idx] = v == "REAL"

        for i, issue in enumerate(issues):
            is_real = verdict_map.get(i, True)  # Default to real if missing
            verdicts.append((issue, is_real))

        return verdicts
