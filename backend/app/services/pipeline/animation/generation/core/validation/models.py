"""
Validation Issue Models

Structured, classified validation issues that enable smart triage:
- Deterministic auto-fix for high-confidence issues
- LLM escalation for complex issues
- Low-confidence verification via lightweight LLM probe

Architecture:
    ValidationIssue carries severity, confidence, category, and auto-fix metadata.
    The Refiner uses this to route: auto-fix → verify → LLM-fix → done.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


class IssueSeverity(Enum):
    """Impact level on final animation quality."""

    CRITICAL = "critical"  # Must fix: text unreadable, object invisible/off-screen
    WARNING = "warning"  # Should investigate: partial occlusion, edge case
    INFO = "info"  # Likely acceptable: decorative overlap, effect animation


class IssueConfidence(Enum):
    """Certainty that this is a genuine problem (not a false positive)."""

    HIGH = "high"  # Definitely wrong (text-on-text, far off-screen)
    MEDIUM = "medium"  # Likely wrong (partial overlap, near edge)
    LOW = "low"  # Uncertain — needs verification (effect overlay, container)


class IssueCategory(Enum):
    """Classification of the validation problem type."""

    # Spatial issues (from runtime spatial checks)
    OUT_OF_BOUNDS = "out_of_bounds"
    TEXT_OVERLAP = "text_overlap"
    OBJECT_OCCLUSION = "object_occlusion"
    VISIBILITY = "visibility"

    # Static analysis issues (from AST / Ruff)
    SYNTAX = "syntax"
    SECURITY = "security"
    LINT = "lint"

    # Runtime issues (from Manim dry-run)
    RUNTIME = "runtime"

    # Visual QC issues (post-render)
    VISUAL_QUALITY = "visual_quality"

    # System / internal errors
    SYSTEM = "system"


@dataclass(frozen=True)
class ValidationIssue:
    """
    A single classified validation issue with routing metadata.
    
    - **Certain Issue**: We are confident this is broken.
      Action: Route directly to Fixer (Deterministic or LLM).
      Examples: Text > 1 unit off-screen, Overlap > 40%, HIGH confidence issues.
      
    - **Uncertain Issue**: It might be broken, but we're not sure.
      Action: Route to Visual QC first. Let the "eyes" decide.
      Examples: Small overlap (5-15%), Flash effect on top of text, LOW confidence.
    """

    severity: IssueSeverity
    confidence: IssueConfidence
    category: IssueCategory
    message: str
    auto_fixable: bool = False
    fix_hint: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    line: Optional[int] = None

    # ── Core routing: Certain vs. Uncertain ──────────────────────────────

    @property
    def is_certain(self) -> bool:
        """Whether we're confident this is a real issue that needs fixing.
        
        Certain issues route directly to the fixer (deterministic or LLM).
        """
        # HIGH confidence issues are always certain
        if self.confidence == IssueConfidence.HIGH:
            return True
        # CRITICAL severity with MEDIUM confidence is also certain
        if self.severity == IssueSeverity.CRITICAL and self.confidence == IssueConfidence.MEDIUM:
            return True
        return False

    @property
    def is_uncertain(self) -> bool:
        """Whether this issue needs visual verification before acting.
        
        Uncertain issues are routed to Visual QC first to determine if real.
        """
        return not self.is_certain and self.is_spatial

    # ── Fix routing ──────────────────────────────────────────────────────

    @property
    def should_auto_fix(self) -> bool:
        """Whether this issue should be handled by the deterministic fixer."""
        return self.auto_fixable and self.is_certain

    @property
    def requires_llm(self) -> bool:
        """Whether this issue needs LLM intervention (can't be auto-fixed)."""
        return self.is_certain and not self.auto_fixable

    # ── Deprecated: kept for backward compatibility ──────────────────────

    @property
    def needs_verification(self) -> bool:
        """DEPRECATED: Use is_uncertain instead."""
        return self.is_uncertain

    # ── Whitelist support ────────────────────────────────────────────────

    @property
    def whitelist_key(self) -> str:
        """Generate a stable key for false positive whitelist.
        
        The key format: (category, subject_id, details_hash)
        Used to track issues that Visual QC confirmed as non-problems.
        """
        import hashlib
        # Build a stable details signature
        # Include key identifying fields: object types, overlap ratios, positions
        detail_parts = []
        for key in sorted(self.details.keys()):
            if key in ("time_sec", "frame_file", "frame_path", "source_message"):
                # Skip time-varying fields
                continue
            val = self.details[key]
            # Round floats for stable matching
            if isinstance(val, float):
                val = round(val, 1)
            detail_parts.append(f"{key}={val}")
        details_str = "|".join(detail_parts)
        details_hash = hashlib.md5(details_str.encode()).hexdigest()[:8]
        
        return f"{self.category.value}:{details_hash}"

    @property
    def is_spatial(self) -> bool:
        """Whether this is a spatial/visual issue."""
        return self.category in (
            IssueCategory.OUT_OF_BOUNDS,
            IssueCategory.TEXT_OVERLAP,
            IssueCategory.OBJECT_OCCLUSION,
            IssueCategory.VISIBILITY,
        )

    def to_fixer_context(self) -> str:
        """Format as context for the LLM fixer, including fix hints."""
        tag = f"{self.category.value}/{self.severity.value}"
        parts = [f"[{tag}] {self.message}"]
        if self.line:
            parts[0] += f" (Line {self.line})"
        if self.fix_hint:
            parts.append(f"Suggested approach: {self.fix_hint}")
        traceback_excerpt = self.details.get("traceback_excerpt")
        if isinstance(traceback_excerpt, str) and traceback_excerpt.strip():
            parts.append(f"Traceback excerpt:\n{traceback_excerpt[:1400]}")
        code_context = self.details.get("code_context")
        if isinstance(code_context, str) and code_context.strip():
            parts.append(f"Code context:\n{code_context[:1200]}")
        return "\n".join(parts)

    def to_verification_prompt(self) -> str:
        """Format as a concise question for the LLM verification probe."""
        return (
            f"In the Manim animation code, the validator flagged: {self.message}\n"
            f"Category: {self.category.value}, Confidence: {self.confidence.value}\n"
            f"Details: {self.details}\n"
            f"Is this a REAL problem that would make the animation look bad, "
            f"or is it acceptable / intentional? Reply with ONLY 'REAL' or 'FALSE_POSITIVE' "
            f"followed by a one-sentence reason."
        )
