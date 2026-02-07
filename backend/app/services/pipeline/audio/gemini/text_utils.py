"""Text utilities for Gemini TTS."""

from __future__ import annotations

import re
from typing import Sequence

from .constants import PAUSE_MARKERS


def count_words(text: str) -> int:
    return len(re.findall(r"\b[\w']+\b", text))


def split_script_to_segments(
    script_text: str,
    target_segment_seconds: float,
    speech_wpm: float,
) -> list[str]:
    normalized = re.sub(r"\s+", " ", script_text.strip())
    if not normalized:
        return []

    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", normalized) if s.strip()]
    if not sentences:
        return [normalized]

    target_words = max(8, int(target_segment_seconds * max(1.0, speech_wpm) / 60.0))
    soft_cap = max(target_words, int(target_words * 1.25))

    segments: list[str] = []
    bucket: list[str] = []
    bucket_words = 0
    for sentence in sentences:
        words = max(1, count_words(sentence))
        if bucket and (bucket_words + words > soft_cap):
            segments.append(" ".join(bucket))
            bucket = [sentence]
            bucket_words = words
        else:
            bucket.append(sentence)
            bucket_words += words

    if bucket:
        segments.append(" ".join(bucket))
    return [s.strip() for s in segments if s.strip()]


def build_stitched_text(segments: Sequence[str]) -> str:
    boundary = f"{PAUSE_MARKERS[0]}\n\n{PAUSE_MARKERS[1]}"
    return f"\n\n{boundary}\n\n".join(segments)
