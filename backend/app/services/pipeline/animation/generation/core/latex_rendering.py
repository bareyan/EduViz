"""Heuristics for routing LaTeX-like strings to the right Manim constructor.

This module intentionally uses conservative detection to avoid false positives
on currency strings (for example: "$5", "$12.99", "$1,200").
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Literal, Optional


RenderableConstructor = Literal["Text", "Tex", "MathTex"]
SuggestionReason = Literal[
    "standalone_math_delimited",
    "mixed_inline_math",
    "bare_latex_expression",
]

_SUPPORTED_CONSTRUCTORS = {"Text", "Tex", "MathTex"}
_UNESCAPED_DOLLAR_RE = re.compile(r"(?<!\\)\$")
_INLINE_DOLLAR_SEGMENT_RE = re.compile(r"(?<!\\)\$(.+?)(?<!\\)\$")
_FULL_DOLLAR_SEGMENT_RE = re.compile(r"^\s*(?<!\\)(\${1,2})(.+?)(?<!\\)\1\s*$", re.DOTALL)
_CURRENCY_SEGMENT_RE = re.compile(
    r"^\s*[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?\s*(?:[kKmMbB]|[A-Za-z]{1,3})?\s*$"
)
_MATH_COMMAND_RE = re.compile(
    r"\\(?:alpha|beta|gamma|delta|epsilon|varepsilon|theta|lambda|mu|pi|sigma|phi|omega|"
    r"frac|sqrt|sum|prod|int|in|subset|supset|cup|cap|leq|geq|neq|approx|equiv|to|rightarrow|"
    r"cdot|times|forall|exists|infty|ldots|dots|cdots|nabla|partial|lim)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class LatexRenderingSuggestion:
    """Recommended constructor rewrite for a string literal."""

    target_constructor: RenderableConstructor
    normalized_text: str
    reason: SuggestionReason


def suggest_latex_rendering(
    constructor: str,
    text: str,
) -> Optional[LatexRenderingSuggestion]:
    """Suggest a safer rendering constructor for LaTeX-like strings.

    Rules are conservative:
    - Only balanced unescaped dollar delimiters are considered inline math.
    - Dollar segments must look like math (not currency).
    - Bare LaTeX commands (for example "\\in") are only promoted when the
      whole string looks expression-like.
    """

    normalized_constructor = str(constructor or "").strip()
    if normalized_constructor not in _SUPPORTED_CONSTRUCTORS:
        return None

    original_text = str(text or "")
    stripped = original_text.strip()
    if not stripped:
        return None

    # Text/Tex with balanced $...$ delimiters
    full_match = _FULL_DOLLAR_SEGMENT_RE.match(original_text)
    if full_match and _has_balanced_unescaped_dollars(original_text):
        inner = full_match.group(2).strip()
        if _looks_math_expression(inner):
            # "$...$" in Tex is usually better rendered as pure MathTex content.
            return LatexRenderingSuggestion(
                target_constructor="MathTex",
                normalized_text=inner,
                reason="standalone_math_delimited",
            )

    # Mixed prose + inline math should be Tex, not Text.
    if normalized_constructor == "Text":
        if _has_balanced_unescaped_dollars(original_text) and _has_math_inline_segment(original_text):
            return LatexRenderingSuggestion(
                target_constructor="Tex",
                normalized_text=original_text,
                reason="mixed_inline_math",
            )

    # Bare LaTeX commands without $ delimiters can still indicate math mode.
    if normalized_constructor == "Text" and _looks_bare_latex_expression(stripped):
        return LatexRenderingSuggestion(
            target_constructor="MathTex",
            normalized_text=stripped,
            reason="bare_latex_expression",
        )

    return None


def _has_balanced_unescaped_dollars(text: str) -> bool:
    count = len(_UNESCAPED_DOLLAR_RE.findall(text or ""))
    return count > 0 and count % 2 == 0


def _has_math_inline_segment(text: str) -> bool:
    for match in _INLINE_DOLLAR_SEGMENT_RE.finditer(text or ""):
        segment = match.group(1).strip()
        if _looks_math_expression(segment):
            return True
    return False


def _looks_math_expression(segment: str) -> bool:
    candidate = (segment or "").strip()
    if not candidate:
        return False

    # Reject plain numeric/currency-like fragments first.
    if _CURRENCY_SEGMENT_RE.fullmatch(candidate):
        return False

    if _MATH_COMMAND_RE.search(candidate):
        return True

    if re.search(r"[=<>^_{}]", candidate):
        return True

    # Variable/function-like compact forms.
    if re.fullmatch(r"[A-Za-z](?:_[A-Za-z0-9]+)?(?:\^\{?[A-Za-z0-9]+\}?)?", candidate):
        return True
    if re.fullmatch(r"[A-Za-z]\([A-Za-z0-9]+\)", candidate):
        return True

    # Expressions with operators become math only when variables are present.
    if re.search(r"[+\-*/]", candidate) and re.search(r"[A-Za-z]", candidate):
        return True

    return False


def _looks_bare_latex_expression(text: str) -> bool:
    candidate = (text or "").strip()
    if not candidate:
        return False

    if "$" in candidate:
        return False

    if len(candidate) > 80:
        return False

    if any(ch in candidate for ch in ".!?"):
        return False

    if _MATH_COMMAND_RE.fullmatch(candidate):
        return True

    if not _MATH_COMMAND_RE.search(candidate):
        return False

    # Keep prose-like strings out of auto-promotion.
    if len(candidate.split()) > 8:
        return False

    commandless = _MATH_COMMAND_RE.sub(" ", candidate)
    words = re.findall(r"[A-Za-z]+", commandless)
    if len(words) >= 3 and sum(1 for word in words if len(word) > 2) >= 3:
        return False

    if re.search(r"[=<>^_{}()]", commandless):
        return True

    # Typical compact membership/formula shape: "x \in A", "f \to g", etc.
    if re.search(r"\b[A-Za-z0-9]\b", commandless):
        return True

    return False
