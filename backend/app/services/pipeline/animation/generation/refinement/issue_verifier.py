"""
Issue Verifier

Lightweight LLM probe that checks whether low-confidence validation issues
are REAL problems or false positives.

Instead of blindly skipping uncertain issues, we send a cheap, focused
question to the LLM: "Is this a real problem?" and act on the answer.
"""

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Dict, List

from app.core import get_logger
from app.services.infrastructure.llm import PromptingEngine, PromptConfig
from app.services.infrastructure.parsing import parse_json_array_response

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
        """Verify a list of uncertain issues."""
        result = VerificationResult()

        if not issues:
            return result

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

        prompt = self._build_prompt(code, issues)
        contents = [prompt]

        has_images = False
        for issue in issues:
            if issue.details and issue.details.get("frame_path"):
                frame_path = Path(issue.details["frame_path"])
                if frame_path.exists():
                    try:
                        contents.append(self._build_image_part(frame_path.read_bytes()))
                        has_images = True
                    except Exception as e:
                        logger.warning(f"Failed to read frame {frame_path}: {e}")

        try:
            llm_result = await self.engine.generate(
                prompt=prompt if not has_images else None,
                contents=contents if has_images else None,
                system_prompt=VERIFIER_SYSTEM.template,
                config=PromptConfig(
                    temperature=VERIFICATION_TEMPERATURE,
                    max_output_tokens=500,
                    response_format="json",
                    # Verifier should recover malformed JSON instead of hard-failing.
                    require_json_valid=False,
                    timeout=VERIFICATION_TIMEOUT,
                    max_retries=VERIFICATION_MAX_RETRIES,
                ),
                context={"stage": "issue_verification"},
            )

            verdict_map = self._extract_verdict_map(llm_result)
            if not llm_result.get("success") and not verdict_map:
                logger.warning(
                    f"Verification LLM call failed: {llm_result.get('error')}. "
                    "Treating all as real (conservative)."
                )
                result.real.extend(issues)
                return result
            if not llm_result.get("success") and verdict_map:
                logger.warning(
                    f"Verification LLM call failed: {llm_result.get('error')}. "
                    f"Recovered {len(verdict_map)} verdict(s) from raw response."
                )

            verdicts = self._parse_verdicts(issues, verdict_map)
            for issue, is_real in verdicts:
                if is_real:
                    promoted = ValidationIssue(
                        severity=issue.severity
                        if issue.severity != IssueSeverity.INFO
                        else IssueSeverity.WARNING,
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
            + (
                "\n(Screenshots attached)"
                if any(i.details.get("frame_path") for i in issues)
                else ""
            )
        )

    def _build_image_part(self, image_bytes: bytes):
        try:
            return self.engine.types.Part.from_data(
                data=image_bytes, mime_type="image/png"
            )
        except AttributeError:
            return self.engine.types.Part.from_bytes(
                data=image_bytes, mime_type="image/png"
            )

    @staticmethod
    def _parse_verdicts(
        issues: List[ValidationIssue],
        verdict_map: Dict[int, bool],
    ) -> List[tuple[ValidationIssue, bool]]:
        """Pair issues with verdict map (default unresolved -> REAL)."""
        verdicts: List[tuple[ValidationIssue, bool]] = []
        for i, issue in enumerate(issues):
            is_real = verdict_map.get(i, True)
            verdicts.append((issue, is_real))
        return verdicts

    @staticmethod
    def _extract_verdict_map(llm_result: dict) -> Dict[int, bool]:
        """Recover verdict map from parsed JSON or malformed response text."""
        verdict_map: Dict[int, bool] = {}

        parsed = llm_result.get("parsed_json")
        if isinstance(parsed, list):
            verdict_map.update(IssueVerifier._extract_verdict_entries(parsed))
            if verdict_map:
                return verdict_map

        text = str(llm_result.get("response") or "").strip()
        if not text:
            return verdict_map

        recovered = parse_json_array_response(text, default=[])
        if isinstance(recovered, list):
            verdict_map.update(IssueVerifier._extract_verdict_entries(recovered))
            if verdict_map:
                return verdict_map

        # Pattern: "0: REAL" / "1 - FALSE_POSITIVE"
        for match in re.finditer(
            r"(?im)\b(\d+)\s*[:=\-]\s*(REAL|FALSE_POSITIVE)\b",
            text,
        ):
            idx = int(match.group(1))
            verdict_map[idx] = match.group(2).upper() == "REAL"

        if verdict_map:
            return verdict_map

        # Malformed object blocks with unquoted keys:
        # {index: 0, verdict: "FALSE_POSITIVE"}
        for block in re.findall(r"\{[^{}]*\}", text, flags=re.S):
            idx_match = re.search(r"\bindex\b\s*:\s*(\d+)", block, flags=re.I)
            verdict_match = re.search(
                r"\bverdict\b\s*:\s*['\"]?(REAL|FALSE_POSITIVE)['\"]?",
                block,
                flags=re.I,
            )
            if not idx_match or not verdict_match:
                continue
            idx = int(idx_match.group(1))
            verdict_map[idx] = verdict_match.group(1).upper() == "REAL"

        return verdict_map

    @staticmethod
    def _extract_verdict_entries(items: List[dict]) -> Dict[int, bool]:
        """Normalize list[dict] verdict payload into index->bool map."""
        verdict_map: Dict[int, bool] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            idx = item.get("index", -1)
            verdict_raw = str(item.get("verdict", "")).upper()
            if not isinstance(idx, int):
                continue
            if verdict_raw not in {"REAL", "FALSE_POSITIVE"}:
                continue
            verdict_map[idx] = verdict_raw == "REAL"
        return verdict_map
