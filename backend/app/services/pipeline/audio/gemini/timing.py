"""Timing pipeline for Gemini TTS."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from .audio_payload import (
    decode_audio_payload,
    extract_inline_audio_payload,
    materialize_payload_file,
    require_pydub,
)
from .constants import DEFAULT_GEMINI_MODEL, PAUSE_MARKERS
from .text_utils import build_stitched_text, count_words, split_script_to_segments


@dataclass
class TTSTimingConfig:
    model: str = DEFAULT_GEMINI_MODEL
    voice: str = "Kore"
    target_segment_seconds: float = 10.0
    speech_wpm: float = 150.0
    min_silence_len_ms: int = 700
    silence_threshold_db: float | None = None
    estimate_weight: float = 0.35
    boundary_keep_ms: int = 500
    natural_gap_ms: int = 180


@dataclass
class SubtitleTimingItem:
    index: int
    start_ms: int
    end_ms: int
    start: str
    end: str
    text: str
    subtitle: str


@dataclass
class TTSTimingResult:
    segments: list[str]
    items: list[SubtitleTimingItem]
    metadata: dict[str, Any]
    output_dir: Path
    stitched_input_path: Path
    raw_payload_path: Path
    raw_full_audio_path: Path
    natural_audio_path: Path
    split_segments_dir: Path
    subtitles_path: Path
    timing_map_path: Path


def _synthesize_with_gemini(
    text: str,
    model: str,
    voice: str,
    output_dir: Path,
) -> tuple[Path, str | None]:
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency: google-genai. Install with: pip install -r requirements.txt"
        ) from exc

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY env var is required for Gemini TTS")

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=text,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
                )
            ),
        ),
    )

    audio_bytes, mime_type = extract_inline_audio_payload(response)
    payload_path = materialize_payload_file(audio_bytes, mime_type, output_dir)
    return payload_path, mime_type


def _estimate_boundary_positions_ms(segments: Sequence[str], audio_ms: int) -> list[int]:
    if len(segments) <= 1:
        return []
    weights = [max(1, count_words(seg)) for seg in segments]
    total = sum(weights)
    cumulative = 0
    output: list[int] = []
    for weight in weights[:-1]:
        cumulative += weight
        output.append(int((cumulative / total) * max(1, audio_ms)))
    return output


def _candidate_score(
    span: list[int],
    expected_ms: int,
    max_duration_ms: int,
    proximity_window_ms: int,
    estimate_weight: float,
) -> float:
    start, end = span
    duration_score = max(1, end - start) / max(1, max_duration_ms)
    center = (start + end) // 2
    proximity_score = max(0.0, 1.0 - (abs(center - expected_ms) / max(1, proximity_window_ms)))
    weight = min(1.0, max(0.0, estimate_weight))
    return (1.0 - weight) * duration_score + weight * proximity_score


def _assign_boundaries_with_dp(
    candidates: list[list[int]],
    expected_positions_ms: list[int],
    max_duration_ms: int,
    proximity_window_ms: int,
    estimate_weight: float,
) -> list[list[int]]:
    n = len(expected_positions_ms)
    m = len(candidates)
    if n == 0:
        return []
    if m < n:
        raise RuntimeError(
            f"Detected {m} silence candidates, but need at least {n} boundaries."
        )

    neg_inf = float("-inf")
    dp = [[neg_inf] * m for _ in range(n)]
    parent = [[-1] * m for _ in range(n)]

    for i in range(m):
        dp[0][i] = _candidate_score(
            candidates[i],
            expected_positions_ms[0],
            max_duration_ms,
            proximity_window_ms,
            estimate_weight,
        )

    for j in range(1, n):
        best_prev = neg_inf
        best_prev_idx = -1
        for i in range(m):
            prev_i = i - 1
            if prev_i >= 0 and dp[j - 1][prev_i] > best_prev:
                best_prev = dp[j - 1][prev_i]
                best_prev_idx = prev_i
            if best_prev_idx == -1:
                continue
            score = _candidate_score(
                candidates[i],
                expected_positions_ms[j],
                max_duration_ms,
                proximity_window_ms,
                estimate_weight,
            )
            dp[j][i] = best_prev + score
            parent[j][i] = best_prev_idx

    end_i = max(range(m), key=lambda i: dp[n - 1][i])
    if dp[n - 1][end_i] == neg_inf:
        raise RuntimeError("Unable to assign ordered boundary silences.")

    picked_indices = [0] * n
    j = n - 1
    i = end_i
    while j >= 0:
        picked_indices[j] = i
        i = parent[j][i]
        j -= 1

    return [candidates[i] for i in picked_indices]


def _select_boundary_silences(
    all_silences: list[list[int]],
    expected_positions_ms: list[int],
    audio_ms: int,
    estimate_weight: float,
) -> list[list[int]]:
    expected_count = len(expected_positions_ms)
    if expected_count == 0:
        return []
    if len(all_silences) < expected_count:
        raise RuntimeError(
            f"Detected {len(all_silences)} silence candidates, expected at least {expected_count}."
        )

    candidates = sorted(all_silences, key=lambda span: (span[0] + span[1]) // 2)
    max_duration_ms = max(max(1, span[1] - span[0]) for span in candidates)
    proximity_window_ms = max(600, audio_ms // max(2, expected_count + 1))
    selected = _assign_boundaries_with_dp(
        candidates=candidates,
        expected_positions_ms=expected_positions_ms,
        max_duration_ms=max_duration_ms,
        proximity_window_ms=proximity_window_ms,
        estimate_weight=estimate_weight,
    )
    return sorted(selected, key=lambda span: span[0])


def _derive_segment_ranges(
    audio_ms: int,
    boundaries: list[list[int]],
    boundary_keep_ms: int,
) -> list[tuple[int, int]]:
    if not boundaries:
        return [(0, audio_ms)]

    ranges: list[tuple[int, int]] = []
    cursor = 0
    for start, end in boundaries:
        b_start = max(cursor, start)
        b_end = max(b_start, end)
        silence_len = b_end - b_start
        keep = min(max(0, boundary_keep_ms), silence_len)
        keep_left = keep // 2
        keep_right = keep - keep_left

        seg_end = max(cursor, min(b_start + keep_left, audio_ms))
        next_cursor = max(seg_end, min(b_end - keep_right, audio_ms))
        ranges.append((cursor, seg_end))
        cursor = next_cursor
    ranges.append((cursor, audio_ms))
    return ranges


def _build_timing_map(
    segments: Sequence[str],
    raw_ranges: Sequence[tuple[int, int]],
    natural_gap_ms: int,
) -> list[dict[str, Any]]:
    if len(segments) != len(raw_ranges):
        raise RuntimeError(f"Segment mismatch: {len(segments)} text segments vs {len(raw_ranges)} audio segments")

    output: list[dict[str, Any]] = []
    natural_cursor = 0
    for idx, (text, (raw_start, raw_end)) in enumerate(zip(segments, raw_ranges, strict=True)):
        duration = max(0, raw_end - raw_start)
        natural_start = natural_cursor
        natural_end = natural_start + duration
        output.append(
            {
                "index": idx,
                "text": text,
                "raw_start_ms": raw_start,
                "raw_end_ms": raw_end,
                "natural_start_ms": natural_start,
                "natural_end_ms": natural_end,
            }
        )
        natural_cursor = natural_end + (natural_gap_ms if idx < len(raw_ranges) - 1 else 0)
    return output


def _format_clock_from_ms(ms: int) -> str:
    total_seconds = max(0, ms // 1000)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def _build_subtitle_items(timing_map: Sequence[dict[str, Any]], timeline: str = "natural") -> list[SubtitleTimingItem]:
    output: list[SubtitleTimingItem] = []
    for item in timing_map:
        if timeline == "raw":
            start_ms = int(item["raw_start_ms"])
            end_ms = int(item["raw_end_ms"])
        else:
            start_ms = int(item["natural_start_ms"])
            end_ms = int(item["natural_end_ms"])
        start = _format_clock_from_ms(start_ms)
        end = _format_clock_from_ms(end_ms)
        text = str(item["text"])
        output.append(
            SubtitleTimingItem(
                index=int(item["index"]),
                start_ms=start_ms,
                end_ms=end_ms,
                start=start,
                end=end,
                text=text,
                subtitle=f"[{start}-{end}] {text}",
            )
        )
    return output


def _render_natural_audio(raw_audio: Any, raw_ranges: Sequence[tuple[int, int]], natural_gap_ms: int) -> Any:
    audio_segment_cls, _ = require_pydub()
    output = audio_segment_cls.empty()
    gap = audio_segment_cls.silent(duration=natural_gap_ms)
    for idx, (start, end) in enumerate(raw_ranges):
        output += raw_audio[start:end]
        if idx < len(raw_ranges) - 1:
            output += gap
    return output


class GeminiTTSTimingComponent:
    def __init__(self, config: TTSTimingConfig | None = None):
        self.config = config or TTSTimingConfig()

    def run(
        self,
        script_text: str,
        output_dir: str | Path,
        *,
        explicit_segments: Sequence[str] | None = None,
        mock_audio_path: str | Path | None = None,
    ) -> TTSTimingResult:
        segments = self._resolve_segments(script_text, explicit_segments)
        if not segments:
            raise ValueError("No segments to synthesize.")

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        split_dir = output_path / "segments"
        split_dir.mkdir(parents=True, exist_ok=True)

        stitched_input_path = output_path / "stitched_input.txt"
        stitched_text = build_stitched_text(segments)
        stitched_input_path.write_text(stitched_text, encoding="utf-8")

        mime_type: str | None = None
        if mock_audio_path is not None:
            payload_path = Path(mock_audio_path)
            if not payload_path.exists():
                raise FileNotFoundError(f"Mock audio does not exist: {payload_path}")
        else:
            payload_path, mime_type = _synthesize_with_gemini(
                text=stitched_text,
                model=self.config.model,
                voice=self.config.voice,
                output_dir=output_path,
            )

        audio_segment_cls, silence_module = require_pydub()
        raw_audio, decode_mode = decode_audio_payload(payload_path, mime_type, audio_segment_cls)

        raw_full_audio_path = output_path / "raw_full.wav"
        raw_audio.export(raw_full_audio_path, format="wav")

        estimated_boundaries_ms = _estimate_boundary_positions_ms(segments, len(raw_audio))
        silence_threshold = (
            self.config.silence_threshold_db
            if self.config.silence_threshold_db is not None
            else (raw_audio.dBFS - 18 if raw_audio.dBFS != float("-inf") else -40)
        )
        all_silences = silence_module.detect_silence(
            raw_audio,
            min_silence_len=self.config.min_silence_len_ms,
            silence_thresh=silence_threshold,
            seek_step=10,
        )
        selected_boundaries = _select_boundary_silences(
            all_silences=all_silences,
            expected_positions_ms=estimated_boundaries_ms,
            audio_ms=len(raw_audio),
            estimate_weight=self.config.estimate_weight,
        )
        raw_ranges = _derive_segment_ranges(
            audio_ms=len(raw_audio),
            boundaries=selected_boundaries,
            boundary_keep_ms=self.config.boundary_keep_ms,
        )

        for idx, (start, end) in enumerate(raw_ranges):
            raw_audio[start:end].export(split_dir / f"segment_{idx:03d}.wav", format="wav")

        natural_audio = _render_natural_audio(raw_audio, raw_ranges, self.config.natural_gap_ms)
        natural_audio_path = output_path / "natural_full.wav"
        natural_audio.export(natural_audio_path, format="wav")

        timing_map = _build_timing_map(segments, raw_ranges, self.config.natural_gap_ms)
        items = _build_subtitle_items(timing_map, timeline="natural")

        subtitles_path = output_path / "timing_subtitles.txt"
        subtitles_path.write_text(
            "\n".join(item.subtitle for item in items) + ("\n" if items else ""),
            encoding="utf-8",
        )

        metadata = {
            "timeline": "natural",
            "subtitle_format": "[MM:SS-MM:SS] text",
            "segments_count": len(items),
            "boundary_debug": {
                "estimate_weight": self.config.estimate_weight,
                "boundary_keep_ms": self.config.boundary_keep_ms,
                "estimated_boundaries_ms": estimated_boundaries_ms,
                "selected_boundaries_ms": selected_boundaries,
                "detected_silences_ms": all_silences,
            },
            "items": [
                {
                    "index": item.index,
                    "start_ms": item.start_ms,
                    "end_ms": item.end_ms,
                    "start": item.start,
                    "end": item.end,
                    "text": item.text,
                    "subtitle": item.subtitle,
                }
                for item in items
            ],
            "payload_mime_type": mime_type,
            "payload_path": str(payload_path),
            "decode_mode": decode_mode,
            "pause_markers": list(PAUSE_MARKERS),
        }

        timing_map_path = output_path / "timing_map.json"
        timing_map_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=True), encoding="utf-8")

        return TTSTimingResult(
            segments=list(segments),
            items=items,
            metadata=metadata,
            output_dir=output_path,
            stitched_input_path=stitched_input_path,
            raw_payload_path=payload_path,
            raw_full_audio_path=raw_full_audio_path,
            natural_audio_path=natural_audio_path,
            split_segments_dir=split_dir,
            subtitles_path=subtitles_path,
            timing_map_path=timing_map_path,
        )

    def _resolve_segments(
        self,
        script_text: str,
        explicit_segments: Sequence[str] | None,
    ) -> list[str]:
        if explicit_segments is not None:
            return [s.strip() for s in explicit_segments if s and s.strip()]

        if re.search(r"(?m)^\s*---\s*$", script_text):
            return [s.strip() for s in re.split(r"(?m)^\s*---\s*$", script_text) if s.strip()]

        return split_script_to_segments(
            script_text=script_text,
            target_segment_seconds=self.config.target_segment_seconds,
            speech_wpm=self.config.speech_wpm,
        )


def generate_tts_timing(
    script_text: str,
    output_dir: str | Path,
    *,
    config: TTSTimingConfig | None = None,
    explicit_segments: Sequence[str] | None = None,
    mock_audio_path: str | Path | None = None,
) -> TTSTimingResult:
    component = GeminiTTSTimingComponent(config=config)
    return component.run(
        script_text=script_text,
        output_dir=output_dir,
        explicit_segments=explicit_segments,
        mock_audio_path=mock_audio_path,
    )
