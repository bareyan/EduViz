"""
Section processor - handles individual section and segment processing
"""

import os
import re
import asyncio
import struct
import subprocess
import shutil
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from pathlib import Path

from .ffmpeg import (
    get_audio_duration,
    get_media_duration,
    concatenate_audio_files,
    concatenate_videos,
    build_retime_merge_cmd,
    build_merge_no_cut_cmd,
)
from app.utils.section_status import write_status
from app.core import get_logger

if TYPE_CHECKING:
    from app.services.pipeline.animation import ManimGenerator
    from app.services.pipeline.audio import TTSEngine
    from .video_generator import VideoGenerator

logger = get_logger(__name__, component="section_processor")

# ---------------------------------------------------------------------------
# Whole-section TTS configuration
# ---------------------------------------------------------------------------

PAUSE_MARKERS: tuple[str, str] = ("(pause)", "(pause)")
"""Marker pair inserted between segments.  Gemini TTS reads the literal word
'pause' and produces clean silence — unlike dot-sequences ('......') which
often trigger breathy 'haaah' artefacts."""

_ESTIMATE_WEIGHT = 0.35
"""Balance between silence-duration score (0.0) and proximity-to-estimate
score (1.0) when selecting boundary silences via DP."""

_BOUNDARY_KEEP_SEC = 0.5
"""Seconds of silence retained at each side of a boundary cut so that
individual segments don't start/end with an abrupt jump."""

LONG_COMPREHENSIVE_CHUNK_MIN_DURATION_SEC = 120.0
LONG_COMPREHENSIVE_TTS_CHUNKS = 2


def _count_words(text: str) -> int:
    """Count words in *text*."""
    return len(re.findall(r"\b[\w']+\b", text))


def clean_narration_for_tts(narration: str) -> str:
    """Clean narration text for TTS - remove pause markers that would be spoken"""

    # Remove [PAUSE] markers
    clean = re.sub(r'\[PAUSE\]', '', narration)

    # Remove standalone "..." (but keep as natural pause in speech)
    # Replace "..." with a comma for natural TTS pacing
    clean = re.sub(r'\s*\.\.\.\s*', ', ', clean)

    # Remove [CALCULATION] markers
    clean = re.sub(r'\[CALCULATION\]', '', clean)

    # Remove other bracket markers like [something]
    clean = re.sub(r'\[[^\]]*\]', '', clean)

    # Clean up multiple spaces and commas
    clean = re.sub(r',\s*,', ',', clean)
    clean = re.sub(r'\s+', ' ', clean)

    # Clean up leading/trailing commas in sentences
    clean = re.sub(r',\s*\.', '.', clean)
    clean = re.sub(r'^\s*,\s*', '', clean)

    return clean.strip()


def _resolve_language_code(*candidates: Optional[str], default: str = "en") -> str:
    """Resolve first concrete language code, skipping empty and 'auto'."""
    for candidate in candidates:
        if not candidate:
            continue
        code = str(candidate).strip().lower()
        if code and code != "auto":
            return code
    return default


def divide_into_subsections(
    narration: str,
    visual_description: str,
    target_duration: int = 20,
    max_duration: int = 30
) -> List[Dict[str, Any]]:
    """Divide narration into subsections at natural breakpoints for sync
    
    Uses sentence boundaries and pause markers to find optimal split points.
    """

    if not narration or len(narration) < 100:
        return [{"narration": narration, "visual_hint": visual_description, "index": 0}]

    # Estimate speaking rate: ~150 words per minute = 2.5 words/second
    CHARS_PER_SECOND = 12.5

    estimated_total_duration = len(narration) / CHARS_PER_SECOND

    if estimated_total_duration <= max_duration:
        return [{"narration": narration, "visual_hint": visual_description, "index": 0}]

    # Split into sentences first
    sentence_pattern = r'(?<=[.!?])\s+'
    sentences = re.split(sentence_pattern, narration)
    sentences = [s.strip() for s in sentences if s.strip()]

    if len(sentences) <= 1:
        return [{"narration": narration, "visual_hint": visual_description, "index": 0}]

    # Group sentences into subsections based on target duration
    subsections = []
    current_subsection = []
    current_length = 0
    target_chars = target_duration * CHARS_PER_SECOND
    max_chars = max_duration * CHARS_PER_SECOND

    for sentence in sentences:
        sentence_len = len(sentence)

        if current_length + sentence_len > max_chars and current_subsection:
            subsection_text = " ".join(current_subsection)
            subsections.append({
                "narration": subsection_text,
                "visual_hint": f"Part {len(subsections) + 1} of visual: {visual_description[:200]}",
                "index": len(subsections)
            })
            current_subsection = [sentence]
            current_length = sentence_len
        elif current_length + sentence_len > target_chars and current_subsection:
            subsection_text = " ".join(current_subsection)
            subsections.append({
                "narration": subsection_text,
                "visual_hint": f"Part {len(subsections) + 1} of visual: {visual_description[:200]}",
                "index": len(subsections)
            })
            current_subsection = [sentence]
            current_length = sentence_len
        else:
            current_subsection.append(sentence)
            current_length += sentence_len + 1

    if current_subsection:
        subsection_text = " ".join(current_subsection)
        subsections.append({
            "narration": subsection_text,
            "visual_hint": f"Part {len(subsections) + 1} of visual: {visual_description[:200]}",
            "index": len(subsections)
        })

    logger.info("Divided narration into subsections", extra={
        "char_count": len(narration),
        "estimated_seconds": round(estimated_total_duration),
        "subsection_count": len(subsections)
    })
    return subsections


async def process_single_subsection(
    manim_generator: "ManimGenerator",
    tts_engine: "TTSEngine",
    section: Dict[str, Any],
    narration: str,
    section_dir: Path,
    section_index: int,
    voice: str,
    style: str,
    language: str = "en",
    job_id: Optional[str] = None
) -> Dict[str, Any]:
    """Process a section with a single subsection (original flow)"""
    result = {
        "video_path": None,
        "audio_path": None,
        "duration": 30
    }

    audio_path = section_dir / "audio.mp3"
    audio_duration = section.get("duration_seconds", 60)

    # Status: generating audio
    write_status(section_dir, "generating_audio")

    try:
        await tts_engine.generate_speech(
            text=narration,
            output_path=str(audio_path),
            voice=voice
        )
        audio_duration = await get_audio_duration(str(audio_path))
        section["actual_duration"] = audio_duration
        result["duration"] = audio_duration
        result["audio_path"] = str(audio_path)
        logger.info(f"Section {section_index} audio duration: {audio_duration:.1f}s")
    except Exception as e:
        logger.error(f"TTS error for section {section_index}: {e}")
        write_status(section_dir, "fixing_error", str(e))
        audio_path = None

    # Status: generating manim (code generation + refinement)
    write_status(section_dir, "generating_manim")

    try:
        section_payload = dict(section)
        section_payload["language"] = _resolve_language_code(section.get("language"), language)

        # Using the NEW Animation Pipeline (Choreograph -> Implement -> Refine)
        manim_result = await manim_generator.generate_animation(
            section=section_payload,
            output_dir=str(section_dir),
            section_index=section_index,
            audio_duration=audio_duration,
            style=style,
            job_id=job_id
        )
        video_path = manim_result.get("video_path") if isinstance(manim_result, dict) else manim_result
        if video_path and os.path.exists(video_path):
            result["video_path"] = video_path
            write_status(section_dir, "completed")
        else:
            logger.warning(f"Manim returned no video for section {section_index}: {video_path}")
        if isinstance(manim_result, dict):
            if manim_result.get("manim_code_path"):
                result["manim_code_path"] = manim_result["manim_code_path"]
            if manim_result.get("choreography_plan_path"):
                result["choreography_plan_path"] = manim_result["choreography_plan_path"]
    except Exception as e:
        import traceback
        logger.error(f"Manim error for section {section_index}: {e}")
        traceback.print_exc()
        write_status(section_dir, "fixing_error", str(e))

    return result


def _is_whole_section_tts(tts_engine: "TTSEngine") -> bool:
    """Check if the TTS engine prefers whole-section generation (e.g. Gemini with strict rate limits)."""
    return getattr(tts_engine, "_whole_section_tts", False)


def _safe_duration(value: Any, default: float = 0.0) -> float:
    """Coerce duration-like value to a non-negative float."""
    try:
        parsed = float(value)
        if parsed > 0:
            return parsed
    except (TypeError, ValueError):
        pass
    return default


def _estimate_segment_duration(segment: Dict[str, Any]) -> float:
    """Estimate duration for splitting decisions when precise timing is unavailable."""
    from_estimated = _safe_duration(segment.get("estimated_duration"))
    if from_estimated > 0:
        return from_estimated

    from_actual = _safe_duration(segment.get("duration"))
    if from_actual > 0:
        return from_actual

    text = str(segment.get("text", ""))
    return max(0.5, len(text) / 12.5)


def _effective_section_duration(
    section: Dict[str, Any],
    narration_segments: List[Dict[str, Any]],
) -> float:
    """Resolve duration used to decide whether chunked TTS should be enabled."""
    explicit_duration = _safe_duration(section.get("duration_seconds"))
    if explicit_duration > 0:
        return explicit_duration
    return sum(_estimate_segment_duration(seg) for seg in narration_segments)


def _should_use_chunked_whole_section_tts(
    section: Dict[str, Any],
    narration_segments: List[Dict[str, Any]],
    tts_engine: "TTSEngine",
) -> bool:
    """Enable 2-request chunked whole-section TTS for long comprehensive Gemini sections."""
    if not _is_whole_section_tts(tts_engine):
        return False
    if len(narration_segments) < 2:
        return False

    video_mode = str(section.get("video_mode", "comprehensive")).strip().lower()
    if video_mode != "comprehensive":
        return False

    duration = _effective_section_duration(section, narration_segments)
    return duration >= LONG_COMPREHENSIVE_CHUNK_MIN_DURATION_SEC


def _split_segments_into_contiguous_chunks(
    narration_segments: List[Dict[str, Any]],
    chunk_count: int = LONG_COMPREHENSIVE_TTS_CHUNKS,
) -> List[List[Dict[str, Any]]]:
    """Split segments into contiguous chunks while preserving order."""
    if not narration_segments:
        return []
    if chunk_count <= 1 or len(narration_segments) <= 1:
        return [list(narration_segments)]

    if chunk_count != 2:
        # Current rollout only needs 2 chunks; keep behavior deterministic.
        chunk_count = 2

    if len(narration_segments) == 2:
        return [[narration_segments[0]], [narration_segments[1]]]

    durations = [_estimate_segment_duration(seg) for seg in narration_segments]
    total_duration = sum(durations)
    target_left = total_duration / 2.0

    best_split = 1
    best_gap = float("inf")
    running = 0.0
    for idx in range(1, len(narration_segments)):
        running += durations[idx - 1]
        gap = abs(running - target_left)
        if gap < best_gap:
            best_gap = gap
            best_split = idx

    return [narration_segments[:best_split], narration_segments[best_split:]]


def _normalize_segment_timings_to_total(
    segment_audio_info: List[Dict[str, Any]],
    stitched_total_duration: float,
) -> List[Dict[str, Any]]:
    """Rebuild monotonic segment timings so they exactly match total duration."""
    if not segment_audio_info:
        return []

    ordered_segments = sorted(segment_audio_info, key=lambda s: int(s.get("segment_index", 0)))

    durations: List[float] = []
    for seg in ordered_segments:
        duration = _safe_duration(seg.get("duration"))
        if duration <= 0:
            start_time = _safe_duration(seg.get("start_time"))
            end_time = _safe_duration(seg.get("end_time"))
            duration = max(0.001, end_time - start_time)
        durations.append(max(0.001, duration))

    source_total = sum(durations)
    target_total = _safe_duration(stitched_total_duration, default=source_total)
    if source_total <= 0:
        source_total = target_total if target_total > 0 else float(len(ordered_segments))
        durations = [source_total / len(ordered_segments)] * len(ordered_segments)

    scale = target_total / source_total if source_total > 0 else 1.0

    normalized: List[Dict[str, Any]] = []
    cursor = 0.0
    for idx, (seg, duration) in enumerate(zip(ordered_segments, durations)):
        adjusted_duration = max(0.001, duration * scale)
        start_time = cursor
        end_time = start_time + adjusted_duration
        if idx == len(ordered_segments) - 1:
            end_time = target_total

        updated = dict(seg)
        updated["start_time"] = start_time
        updated["end_time"] = end_time
        updated["duration"] = max(0.0, end_time - start_time)
        normalized.append(updated)
        cursor = end_time

    return normalized


async def _generate_audio_per_segment(
    tts_engine: "TTSEngine",
    narration_segments: List[Dict[str, Any]],
    section_dir: Path,
    section_index: int,
    voice: str,
) -> tuple[List[Dict[str, Any]], float]:
    """Original per-segment TTS: generate audio for each segment individually.

    Returns (segment_audio_info, total_duration).
    """
    segment_audio_info = []
    cumulative_time = 0.0

    for seg_idx, segment in enumerate(narration_segments):
        seg_dir = section_dir / f"seg_{seg_idx}"
        seg_dir.mkdir(exist_ok=True)

        seg_text = segment.get("text", "")
        clean_text = clean_narration_for_tts(seg_text)

        audio_path = seg_dir / "audio.mp3"
        audio_duration = segment.get("estimated_duration", 10.0)

        try:
            await tts_engine.generate_speech(
                text=clean_text,
                output_path=str(audio_path),
                voice=voice
            )
            audio_duration = await get_audio_duration(str(audio_path))
        except Exception as e:
            logger.error(f"TTS error for section {section_index} segment {seg_idx}: {e}")
            audio_path = None

        segment_info = {
            "segment_index": seg_idx,
            "text": clean_text,
            "audio_path": str(audio_path) if audio_path else None,
            "duration": audio_duration,
            "start_time": cumulative_time,
            "end_time": cumulative_time + audio_duration,
            "seg_dir": str(seg_dir)
        }
        segment_audio_info.append(segment_info)
        cumulative_time += audio_duration

        logger.debug(f"Segment {seg_idx}: {audio_duration:.1f}s (starts at {segment_info['start_time']:.1f}s)")

    return segment_audio_info, cumulative_time


async def _generate_audio_whole_section(
    tts_engine: "TTSEngine",
    narration_segments: List[Dict[str, Any]],
    section_dir: Path,
    section_index: int,
    voice: str,
) -> tuple[List[Dict[str, Any]], float]:
    """Whole-section TTS: ONE API call for the entire section, then detect
    pause markers to extract exact segment timings.

    This is designed for rate-limited engines like Gemini TTS (8 RPM / 100 RPD).
    Reduces API calls from N-per-section to 1-per-section.
    
    Strategy:
    1. Insert long pause markers between segments
    2. Generate full audio with Gemini TTS (1 API call)
    3. Detect pauses in the output audio
    4. Split audio at pause points to get exact segment boundaries
    5. Measure actual duration for each segment

    Returns (segment_audio_info, total_duration).
    """
    # Build cleaned texts for each segment
    cleaned_texts = []
    for seg in narration_segments:
        cleaned_texts.append(clean_narration_for_tts(seg.get("text", "")))

    boundary = f" {PAUSE_MARKERS[0]}\n\n{PAUSE_MARKERS[1]} "
    full_text = boundary.join(cleaned_texts)

    section_audio_path = section_dir / "section_audio.mp3"

    try:
        await tts_engine.generate_speech(
            text=full_text,
            output_path=str(section_audio_path),
            voice=voice,
        )
        total_duration = await get_audio_duration(str(section_audio_path))
    except Exception as e:
        logger.error(f"TTS error for section {section_index} (whole-section): {e}")
        return [], 0.0

    logger.info(
        f"Section {section_index}: Generated whole-section audio "
        f"({total_duration:.1f}s) with 1 API call for {len(narration_segments)} segments"
    )

    num_boundaries = len(narration_segments) - 1

    if num_boundaries == 0:
        # Single segment — no splitting needed
        seg_dir = section_dir / "seg_0"
        seg_dir.mkdir(exist_ok=True)
        shutil.copy2(str(section_audio_path), str(seg_dir / "audio.mp3"))
        return [
            {
                "segment_index": 0,
                "text": cleaned_texts[0] if cleaned_texts else "",
                "audio_path": str(seg_dir / "audio.mp3"),
                "duration": total_duration,
                "start_time": 0.0,
                "end_time": total_duration,
                "seg_dir": str(seg_dir),
            }
        ], total_duration

    # ---- Boundary detection: energy-valley candidates + DP assignment ----
    # 1. Find ALL candidate valleys via energy-envelope analysis.
    all_candidates = await _find_valley_candidates(str(section_audio_path))

    # 2. Estimate where boundaries *should* fall from word counts.
    estimated_positions = _estimate_boundary_positions(cleaned_texts, total_duration)

    # 3. Use dynamic programming to select the optimal N-1 boundaries
    #    that balance silence quality with proximity to estimates.
    try:
        boundaries = _select_boundary_silences(
            candidates=all_candidates,
            expected_positions=estimated_positions,
            total_duration=total_duration,
        )
    except Exception as e:
        logger.warning(
            f"Section {section_index}: DP boundary selection failed ({e}), "
            f"falling back to proportional timing"
        )
        return await _distribute_timing_proportionally(
            narration_segments=narration_segments,
            cleaned_texts=cleaned_texts,
            section_audio_path=str(section_audio_path),
            section_dir=section_dir,
            total_duration=total_duration,
        )

    if len(boundaries) < num_boundaries:
        logger.warning(
            f"Section {section_index}: Only {len(boundaries)}/{num_boundaries} "
            f"boundaries found from {len(all_candidates)} candidates, "
            f"using proportional timing"
        )
        return await _distribute_timing_proportionally(
            narration_segments=narration_segments,
            cleaned_texts=cleaned_texts,
            section_audio_path=str(section_audio_path),
            section_dir=section_dir,
            total_duration=total_duration,
        )

    # 4. Derive segment ranges keeping some silence at edges for naturalness.
    segment_ranges = _derive_segment_ranges(total_duration, boundaries)

    logger.info(
        f"Section {section_index}: Selected {len(boundaries)} boundaries "
        f"from {len(all_candidates)} candidates, "
        f"splitting into {len(narration_segments)} segments"
    )

    # 5. Split audio at computed ranges, trim edges.
    segment_audio_info = await _split_audio_at_ranges(
        section_audio_path=str(section_audio_path),
        segment_ranges=segment_ranges,
        narration_segments=narration_segments,
        cleaned_texts=cleaned_texts,
        section_dir=section_dir,
    )
    if segment_audio_info:
        cumulative_time = sum(s["duration"] for s in segment_audio_info)
        return segment_audio_info, cumulative_time

    # Last-resort fallback (should be very rare — only if ffmpeg extraction fails).
    logger.warning(
        f"Section {section_index}: Audio splitting failed, "
        f"using proportional timing"
    )
    return await _distribute_timing_proportionally(
        narration_segments=narration_segments,
        cleaned_texts=cleaned_texts,
        section_audio_path=str(section_audio_path),
        section_dir=section_dir,
        total_duration=total_duration,
    )


async def _generate_audio_whole_section_chunked(
    tts_engine: "TTSEngine",
    narration_segments: List[Dict[str, Any]],
    section_dir: Path,
    section_index: int,
    voice: str,
) -> tuple[List[Dict[str, Any]], float]:
    """Generate long-section whole TTS in two contiguous chunks and stitch results."""
    chunks = _split_segments_into_contiguous_chunks(
        narration_segments,
        chunk_count=LONG_COMPREHENSIVE_TTS_CHUNKS,
    )
    if len(chunks) < 2:
        return await _generate_audio_whole_section(
            tts_engine=tts_engine,
            narration_segments=narration_segments,
            section_dir=section_dir,
            section_index=section_index,
            voice=voice,
        )

    chunk_audio_paths: List[str] = []
    remapped_segments: List[Dict[str, Any]] = []
    segment_offset = 0

    for chunk_idx, chunk_segments in enumerate(chunks):
        chunk_dir = section_dir / f"tts_chunk_{chunk_idx}"
        chunk_dir.mkdir(parents=True, exist_ok=True)

        chunk_info, _ = await _generate_audio_whole_section(
            tts_engine=tts_engine,
            narration_segments=chunk_segments,
            section_dir=chunk_dir,
            section_index=section_index,
            voice=voice,
        )
        if not chunk_info:
            logger.warning(
                f"Section {section_index}: Chunked whole-section TTS failed at chunk {chunk_idx}"
            )
            return [], 0.0

        chunk_section_audio_path = chunk_dir / "section_audio.mp3"
        if not chunk_section_audio_path.exists():
            logger.warning(
                f"Section {section_index}: Missing chunk audio file at {chunk_section_audio_path}"
            )
            return [], 0.0
        chunk_audio_paths.append(str(chunk_section_audio_path))

        for local_idx, seg_info in enumerate(chunk_info):
            remapped = dict(seg_info)
            remapped["segment_index"] = segment_offset + local_idx
            remapped_segments.append(remapped)
        segment_offset += len(chunk_segments)

    section_audio_path = section_dir / "section_audio.mp3"
    stitched_ok = await concatenate_audio_files(chunk_audio_paths, str(section_audio_path))
    if not stitched_ok:
        logger.warning(f"Section {section_index}: Failed to stitch chunk audios")
        return [], 0.0

    stitched_total_duration = await get_audio_duration(str(section_audio_path))
    normalized_segments = _normalize_segment_timings_to_total(
        remapped_segments,
        stitched_total_duration,
    )

    # Unified path for downstream consumers (final section audio source).
    for seg in normalized_segments:
        seg["audio_path"] = str(section_audio_path)

    logger.info(
        f"Section {section_index}: Chunked whole-section TTS complete "
        f"({stitched_total_duration:.1f}s, {len(normalized_segments)} segments, "
        f"{len(chunk_audio_paths)} requests)"
    )
    return normalized_segments, stitched_total_duration


async def _distribute_timing_proportionally(
    narration_segments: List[Dict[str, Any]],
    cleaned_texts: List[str],
    section_audio_path: str,
    section_dir: Path,
    total_duration: float
) -> tuple[List[Dict[str, Any]], float]:
    """Fallback: distribute timing proportionally by character count."""
    char_counts = [max(1, len(t)) for t in cleaned_texts]
    total_chars = sum(char_counts)
    cumulative_time = 0.0
    segment_audio_info = []

    for seg_idx, (segment, clean_text, chars) in enumerate(
        zip(narration_segments, cleaned_texts, char_counts)
    ):
        seg_duration = total_duration * (chars / total_chars)

        segment_info = {
            "segment_index": seg_idx,
            "text": clean_text,
            "audio_path": section_audio_path,
            "duration": seg_duration,
            "start_time": cumulative_time,
            "end_time": cumulative_time + seg_duration,
            "seg_dir": str(section_dir / f"seg_{seg_idx}"),
        }
        segment_audio_info.append(segment_info)
        cumulative_time += seg_duration

        logger.debug(
            f"Segment {seg_idx}: ~{seg_duration:.1f}s "
            f"(proportional, starts at {segment_info['start_time']:.1f}s)"
        )

    return segment_audio_info, cumulative_time


# ---------------------------------------------------------------------------
# Energy-valley candidate detection
# ---------------------------------------------------------------------------

_VALLEY_SAMPLE_RATE = 16000  # Hz — low is fine, we only need the energy envelope
_VALLEY_WINDOW_SEC = 0.05    # 50 ms windows for RMS computation
_VALLEY_SMOOTH_SEC = 0.5     # smoothing kernel
_MIN_VALLEY_SEC = 0.3        # minimum width for a valid valley candidate


async def _find_valley_candidates(
    audio_path: str,
    window_sec: float = _VALLEY_WINDOW_SEC,
    smooth_sec: float = _VALLEY_SMOOTH_SEC,
    min_valley_sec: float = _MIN_VALLEY_SEC,
) -> List[tuple[float, float]]:
    """Find **all** energy-valley regions in *audio_path*.

    This is the candidate generation step.  It returns every contiguous
    region whose smoothed RMS energy is below the median — sorted
    chronologically.  The DP boundary assignment step later picks the
    optimal subset.

    The approach is threshold-free: it works even when Gemini TTS inserts
    breathing artefacts ('haaah') instead of clean silence, because the
    energy in a breathy pause is still significantly lower than speech.

    Returns ``[(start_sec, end_sec), ...]``.
    """
    try:
        energy, window_sec_actual = await _extract_energy_envelope(
            audio_path, window_sec, smooth_sec
        )
    except Exception as e:
        logger.error(f"Energy extraction failed: {e}")
        return []

    if len(energy) < 3:
        return []

    median_e = sorted(energy)[len(energy) // 2]
    min_valley_windows = max(1, int(min_valley_sec / window_sec_actual))

    candidates: List[tuple[float, float]] = []
    in_valley = False
    v_start = 0

    for i, e in enumerate(energy):
        if e < median_e and not in_valley:
            v_start = i
            in_valley = True
        elif (e >= median_e or i == len(energy) - 1) and in_valley:
            v_end = i if e >= median_e else i + 1
            if v_end - v_start >= min_valley_windows:
                t_start = v_start * window_sec_actual
                t_end = v_end * window_sec_actual
                candidates.append((t_start, t_end))
            in_valley = False

    logger.info(
        f"Energy-valley: found {len(candidates)} candidate regions: "
        f"{[(f'{s:.2f}', f'{e:.2f}') for s, e in candidates]}"
    )
    return candidates


async def _extract_energy_envelope(
    audio_path: str,
    window_sec: float = _VALLEY_WINDOW_SEC,
    smooth_sec: float = _VALLEY_SMOOTH_SEC,
) -> tuple[list[float], float]:
    """Decode *audio_path* to mono PCM and return a smoothed energy envelope.

    Returns ``(energy_list, actual_window_sec)``.
    """
    cmd = [
        "ffmpeg", "-i", audio_path,
        "-ac", "1",
        "-ar", str(_VALLEY_SAMPLE_RATE),
        "-f", "s16le",
        "-acodec", "pcm_s16le",
        "pipe:1",
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    raw_pcm, _ = await proc.communicate()

    if not raw_pcm:
        raise RuntimeError("ffmpeg returned no PCM data")

    num_samples = len(raw_pcm) // 2
    samples = struct.unpack(f"<{num_samples}h", raw_pcm)

    # --- RMS per window ---
    win_samples = max(1, int(_VALLEY_SAMPLE_RATE * window_sec))
    num_windows = num_samples // win_samples

    energy: list[float] = []
    for i in range(num_windows):
        start = i * win_samples
        chunk = samples[start : start + win_samples]
        rms = (sum(s * s for s in chunk) / len(chunk)) ** 0.5
        energy.append(rms)

    if not energy:
        raise RuntimeError("Audio too short to analyse")

    # --- Smooth with rolling average ---
    smooth_w = max(1, int(smooth_sec / window_sec))
    half = smooth_w // 2
    smoothed: list[float] = []
    for i in range(len(energy)):
        lo = max(0, i - half)
        hi = min(len(energy), i + half + 1)
        smoothed.append(sum(energy[lo:hi]) / (hi - lo))

    return smoothed, window_sec


# ---------------------------------------------------------------------------
# DP-based boundary assignment (adapted from the TTS-timing POC)
# ---------------------------------------------------------------------------


def _estimate_boundary_positions(
    segment_texts: List[str],
    total_duration: float,
) -> List[float]:
    """Estimate where segment boundaries should fall from word-count proportions.

    Returns ``N-1`` positions (in seconds) for ``N`` segments.
    """
    if len(segment_texts) <= 1:
        return []
    weights = [max(1, _count_words(t)) for t in segment_texts]
    total = sum(weights)
    cumulative = 0
    positions: List[float] = []
    for w in weights[:-1]:
        cumulative += w
        positions.append((cumulative / total) * max(0.001, total_duration))
    return positions


def _candidate_score(
    start: float,
    end: float,
    expected: float,
    max_duration: float,
    proximity_window: float,
    estimate_weight: float,
) -> float:
    """Score a silence candidate by duration and proximity to an estimate.

    Higher is better.  *estimate_weight* in ``[0, 1]`` trades off silence
    duration (longer = better) vs closeness to the word-count estimate.
    """
    duration_score = max(0.001, end - start) / max(0.001, max_duration)
    centre = (start + end) / 2.0
    proximity_score = max(0.0, 1.0 - abs(centre - expected) / max(0.001, proximity_window))
    w = min(1.0, max(0.0, estimate_weight))
    return (1.0 - w) * duration_score + w * proximity_score


def _assign_boundaries_dp(
    candidates: List[tuple[float, float]],
    expected_positions: List[float],
    max_duration: float,
    proximity_window: float,
    estimate_weight: float,
) -> List[tuple[float, float]]:
    """Pick *N* ordered boundaries from *M* candidates (``M >= N``) via DP.

    Maximises the sum of :func:`_candidate_score` across all selected
    boundaries, subject to the constraint that selected indices are strictly
    increasing (so boundaries remain chronological).

    Raises ``RuntimeError`` when no valid assignment exists.
    """
    n = len(expected_positions)
    m = len(candidates)
    if n == 0:
        return []
    if m < n:
        raise RuntimeError(
            f"Not enough candidates ({m}) for {n} boundaries"
        )

    neg_inf = float("-inf")
    dp = [[neg_inf] * m for _ in range(n)]
    parent = [[-1] * m for _ in range(n)]

    # Base case: first boundary
    for i in range(m):
        dp[0][i] = _candidate_score(
            candidates[i][0], candidates[i][1],
            expected_positions[0], max_duration, proximity_window, estimate_weight,
        )

    # Fill remaining rows
    for j in range(1, n):
        best_prev = neg_inf
        best_prev_idx = -1
        for i in range(m):
            if i > 0 and dp[j - 1][i - 1] > best_prev:
                best_prev = dp[j - 1][i - 1]
                best_prev_idx = i - 1
            if best_prev_idx == -1:
                continue
            score = _candidate_score(
                candidates[i][0], candidates[i][1],
                expected_positions[j], max_duration, proximity_window, estimate_weight,
            )
            dp[j][i] = best_prev + score
            parent[j][i] = best_prev_idx

    # Backtrack to find optimal assignment
    end_i = max(range(m), key=lambda i: dp[n - 1][i])
    if dp[n - 1][end_i] == neg_inf:
        raise RuntimeError("Unable to assign ordered boundary silences")

    picked_indices = [0] * n
    j, i = n - 1, end_i
    while j >= 0:
        picked_indices[j] = i
        i = parent[j][i]
        j -= 1

    return [candidates[idx] for idx in picked_indices]


def _select_boundary_silences(
    candidates: List[tuple[float, float]],
    expected_positions: List[float],
    total_duration: float,
    estimate_weight: float = _ESTIMATE_WEIGHT,
) -> List[tuple[float, float]]:
    """Select *N* boundary silences from candidates using DP assignment.

    Combines silence quality (duration) with word-count estimated positions
    so that even when some pauses are imperfect, boundaries land close to
    where they are expected.

    Returns selected boundaries sorted chronologically.
    """
    n = len(expected_positions)
    if n == 0:
        return []
    if len(candidates) < n:
        return candidates  # not enough — caller will fallback

    sorted_cands = sorted(candidates, key=lambda c: (c[0] + c[1]) / 2.0)
    max_dur = max(max(0.001, c[1] - c[0]) for c in sorted_cands)
    prox_window = max(0.6, total_duration / max(2, n + 1))

    selected = _assign_boundaries_dp(
        sorted_cands, expected_positions, max_dur, prox_window, estimate_weight,
    )
    return sorted(selected, key=lambda c: c[0])


def _derive_segment_ranges(
    total_duration: float,
    boundaries: List[tuple[float, float]],
    boundary_keep: float = _BOUNDARY_KEEP_SEC,
) -> List[tuple[float, float]]:
    """Derive speech segment ranges, keeping some silence at edges.

    Each boundary silence region is split: a small *boundary_keep* portion
    is left on each neighbouring segment so that the cut doesn't land on
    an abrupt consonant.

    Returns ``N`` ranges for ``N-1`` boundaries.
    """
    if not boundaries:
        return [(0.0, total_duration)]

    ranges: List[tuple[float, float]] = []
    cursor = 0.0
    for start, end in boundaries:
        b_start = max(cursor, start)
        b_end = max(b_start, end)
        silence_len = b_end - b_start
        keep = min(max(0.0, boundary_keep), silence_len)
        keep_left = keep / 2.0
        keep_right = keep - keep_left

        seg_end = max(cursor, min(b_start + keep_left, total_duration))
        next_cursor = max(seg_end, min(b_end - keep_right, total_duration))
        ranges.append((cursor, seg_end))
        cursor = next_cursor

    ranges.append((cursor, total_duration))
    return ranges


async def _trim_segment_edges(
    input_path: str,
    output_path: str,
    threshold: str = "-35dB",
    min_silence: float = 0.1,
) -> None:
    """Trim leading and trailing silence from an audio segment.

    Uses ffmpeg's ``silenceremove`` filter with the *reverse* trick so
    that both the head and tail of the file are cleaned in one pass.
    Falls back to a raw copy if the filter fails.
    """
    af_filter = (
        f"silenceremove=start_periods=1:start_silence={min_silence}:start_threshold={threshold},"
        f"areverse,"
        f"silenceremove=start_periods=1:start_silence={min_silence}:start_threshold={threshold},"
        f"areverse"
    )
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-af", af_filter,
        "-acodec", "libmp3lame", "-ab", "192k",
        output_path,
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()
        if proc.returncode != 0:
            logger.warning(f"Edge trim failed, using raw segment: {stderr.decode()[:200]}")
            shutil.copy2(input_path, output_path)
    except Exception as e:
        logger.warning(f"Edge trim error, using raw: {e}")
        shutil.copy2(input_path, output_path)
    finally:
        # Clean up the raw intermediate file
        try:
            if os.path.abspath(input_path) != os.path.abspath(output_path):
                os.remove(input_path)
        except OSError:
            pass


async def _split_audio_at_ranges(
    section_audio_path: str,
    segment_ranges: List[tuple[float, float]],
    narration_segments: List[Dict[str, Any]],
    cleaned_texts: List[str],
    section_dir: Path,
) -> List[Dict[str, Any]]:
    """Split audio into segments using pre-computed time ranges.

    *segment_ranges* are ``(start_sec, end_sec)`` pairs produced by
    :func:`_derive_segment_ranges`.  Each range already accounts for the
    boundary-keep adjustment, so we extract verbatim and then trim any
    residual leading/trailing silence from each segment.
    """
    segment_audio_info: List[Dict[str, Any]] = []

    for seg_idx, (start_time, end_time) in enumerate(segment_ranges):
        seg_duration = end_time - start_time

        seg_dir = section_dir / f"seg_{seg_idx}"
        seg_dir.mkdir(exist_ok=True)
        raw_seg_path = seg_dir / "audio_raw.mp3"
        seg_audio_path = seg_dir / "audio.mp3"

        cmd = [
            "ffmpeg", "-y",
            "-i", section_audio_path,
            "-ss", str(start_time),
            "-to", str(end_time),
            "-c", "copy",
            str(raw_seg_path),
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await proc.communicate()

            await _trim_segment_edges(str(raw_seg_path), str(seg_audio_path))

            actual_duration = await get_audio_duration(str(seg_audio_path))

            segment_info = {
                "segment_index": seg_idx,
                "text": cleaned_texts[seg_idx] if seg_idx < len(cleaned_texts) else "",
                "audio_path": str(seg_audio_path),
                "duration": actual_duration,
                "start_time": start_time,
                "end_time": end_time,
                "seg_dir": str(seg_dir),
            }
            segment_audio_info.append(segment_info)

            logger.debug(
                f"Segment {seg_idx}: {actual_duration:.2f}s "
                f"(range {start_time:.2f}s\u2013{end_time:.2f}s)"
            )

        except Exception as e:
            logger.error(f"Error extracting segment {seg_idx}: {e}")
            segment_info = {
                "segment_index": seg_idx,
                "text": cleaned_texts[seg_idx] if seg_idx < len(cleaned_texts) else "",
                "audio_path": section_audio_path,
                "duration": seg_duration,
                "start_time": start_time,
                "end_time": end_time,
                "seg_dir": str(seg_dir),
            }
            segment_audio_info.append(segment_info)

    return segment_audio_info


async def process_segments_audio_first(
    manim_generator: "ManimGenerator",
    tts_engine: "TTSEngine",
    section: Dict[str, Any],
    narration_segments: List[Dict[str, Any]],
    section_dir: Path,
    section_index: int,
    voice: str,
    style: str,
    language: str = "en",
    job_id: Optional[str] = None
) -> Dict[str, Any]:
    """Process segments using audio-first approach for precise sync
    
    WORKFLOW:
    1. Generate audio for ALL segments first
    2. Get actual audio durations for each segment
    3. Concatenate all audio into one section audio file
    4. Pass ALL segment timing info to Gemini for ONE cohesive video
    5. Generate ONE video for the entire section
    6. Merge audio with video

    When a whole-section TTS engine (e.g. Gemini TTS) is detected, steps 1-3
    are replaced with a single API call that generates audio for the entire
    section narration at once, dramatically reducing API usage.
    """
    result = {
        "video_path": None,
        "audio_path": None,
        "duration": 0
    }

    num_segments = len(narration_segments)
    use_whole_section = _is_whole_section_tts(tts_engine)
    use_chunked_whole_section = (
        use_whole_section
        and _should_use_chunked_whole_section_tts(section, narration_segments, tts_engine)
    )
    if use_chunked_whole_section:
        mode_label = "chunked-whole-section"
    elif use_whole_section:
        mode_label = "whole-section"
    else:
        mode_label = "per-segment"
    logger.info(f"Section {section_index}: Processing {num_segments} segments (audio-first, {mode_label})")

    # Status: generating audio
    write_status(section_dir, "generating_audio")

    # Step 1 & 2: Generate audio — strategy depends on engine type
    if use_whole_section:
        if use_chunked_whole_section:
            segment_audio_info, total_duration = await _generate_audio_whole_section_chunked(
                tts_engine, narration_segments, section_dir, section_index, voice,
            )
            if not segment_audio_info:
                logger.warning(
                    f"Section {section_index}: Chunked whole-section TTS failed, falling back to single request"
                )
                segment_audio_info, total_duration = await _generate_audio_whole_section(
                    tts_engine, narration_segments, section_dir, section_index, voice,
                )
        else:
            segment_audio_info, total_duration = await _generate_audio_whole_section(
                tts_engine, narration_segments, section_dir, section_index, voice,
            )
        if not segment_audio_info:
            logger.warning(f"Section {section_index}: Whole-section TTS failed")
            return result
    else:
        segment_audio_info, total_duration = await _generate_audio_per_segment(
            tts_engine, narration_segments, section_dir, section_index, voice,
        )

    logger.info(f"Section {section_index}: Total audio duration = {total_duration:.1f}s")

    # Step 3: Handle audio concatenation (per-segment only OR whole-section with split segments)
    section_audio_path = section_dir / "section_audio.mp3"
    
    if not use_whole_section:
        # Per-segment mode: Concatenate all audio segments
        valid_audio_paths = [s["audio_path"] for s in segment_audio_info if s["audio_path"]]

        if len(valid_audio_paths) > 1:
            await concatenate_audio_files(valid_audio_paths, str(section_audio_path))
        elif len(valid_audio_paths) == 1:
            shutil.copy(valid_audio_paths[0], str(section_audio_path))
        else:
            logger.warning(f"Section {section_index}: No valid audio segments")
            return result
    # else: whole-section mode - section_audio.mp3 already exists from _generate_audio_whole_section

    result["audio_path"] = str(section_audio_path)
    result["duration"] = total_duration

    # Get original narration segments for visual descriptions
    original_segments = narration_segments  # Has text, estimated_duration, possibly visual hints

    # Build unified section with all segment timing, including FULL text and visual descriptions
    segment_timing_data = []
    for i, s in enumerate(segment_audio_info):
        # Get original segment data if available for visual_description
        orig_seg = original_segments[i] if i < len(original_segments) else {}

        segment_timing_data.append({
            "index": s["segment_index"],
            "text": s["text"],  # Full text, not truncated
            "start_time": s["start_time"],
            "end_time": s["end_time"],
            "duration": s["duration"],
            "visual_description": orig_seg.get("visual_description", orig_seg.get("visual_hint", ""))
        })

    unified_section = {
        "id": section.get('id', 'section'),
        "title": section.get('title', 'Section'),
        "narration": "\n\n".join([s["text"] for s in segment_audio_info]),
        "tts_narration": "\n\n".join([s["text"] for s in segment_audio_info]),
        "visual_description": section.get("visual_description", ""),
        "key_concepts": section.get("key_concepts", []),
        "animation_type": section.get("animation_type", "mixed"),
        "style": style,
        "language": _resolve_language_code(section.get("language"), language),
        "total_duration": total_duration,
        "is_unified_section": True,
        "num_segments": num_segments,
        "segment_timing": segment_timing_data,
        # Also pass the original narration_segments for compatibility
        "narration_segments": [
            {
                "text": s["text"],
                "estimated_duration": s["duration"],
                "duration": s["duration"],
                "start_time": s["start_time"],
                "end_time": s["end_time"],
                "segment_index": s["segment_index"],
                "visual_description": segment_timing_data[i].get("visual_description", "") if i < len(segment_timing_data) else ""
            }
            for i, s in enumerate(segment_audio_info)
        ]
    }

    logger.info(f"Section {section_index}: Generating unified video using NEW Pipeline ({total_duration:.1f}s total)")

    # Status: generating manim (code generation + refinement)
    write_status(section_dir, "generating_manim")

    video_path = None
    try:
        manim_result = await manim_generator.generate_animation(
            section=unified_section,
            output_dir=str(section_dir),
            section_index=section_index,
            audio_duration=total_duration,
            style=style,
            job_id=job_id
        )
        video_path = manim_result.get("video_path")
        if isinstance(manim_result, dict) and manim_result.get("manim_code_path"):
            result["manim_code_path"] = manim_result["manim_code_path"]
        if isinstance(manim_result, dict) and manim_result.get("choreography_plan_path"):
            result["choreography_plan_path"] = manim_result["choreography_plan_path"]
    except Exception as e:
        logger.error(f"Manim error for unified section {section_index}: {e}")
        import traceback
        traceback.print_exc()
        write_status(section_dir, "fixing_error", str(e))
        return result

    if not video_path:
        logger.error(f"Section {section_index}: Failed to process unified video")
        write_status(section_dir, "fixing_error", "No video generated")
        return result

    # Step 4: Finalize audio
    final_audio_path = section_audio_path

    # Step 5: Merge video with audio (extend shorter to match longer, never cut)
    merged_path = section_dir / "final_section.mp4"

    audio_duration_actual = await get_media_duration(str(final_audio_path))
    video_duration_actual = await get_media_duration(video_path)

    logger.info(f"Section {section_index}: Merging video ({video_duration_actual:.1f}s) with audio ({audio_duration_actual:.1f}s)")

    cmd = build_merge_no_cut_cmd(
        video_path=video_path,
        audio_path=str(final_audio_path),
        video_duration=video_duration_actual,
        audio_duration=audio_duration_actual,
        output_path=str(merged_path)
    )

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await asyncio.wait_for(process.communicate(), timeout=300)

        if process.returncode == 0 and merged_path.exists():
            result["video_path"] = str(merged_path)
            result["duration"] = total_duration
            logger.info(f"Section {section_index}: Successfully created unified video")
            write_status(section_dir, "completed")
        else:
            logger.error(f"Section {section_index}: FFmpeg merge failed: {stderr.decode()[:500]}")
            write_status(section_dir, "fixing_error", "FFmpeg merge failed")
    except Exception as e:
        logger.error(f"Section {section_index}: Error merging video and audio: {e}")
        write_status(section_dir, "fixing_error", str(e))

    return result


async def merge_segments(
    generator: "VideoGenerator",
    segment_results: List[Dict[str, Any]],
    output_dir: Path,
    section_index: int
) -> Dict[str, Any]:
    """Merge multiple segments into a single section video"""
    merged_clips = []

    for seg in segment_results:
        seg_idx = seg["segment_index"]
        video_path = seg.get("video_path")
        audio_path = seg.get("audio_path")
        merged_path = output_dir / f"merged_seg_{seg_idx}.mp4"

        audio_duration = await get_media_duration(audio_path)
        video_duration = await get_media_duration(video_path)

        cmd = build_retime_merge_cmd(
            video_path=video_path,
            audio_path=audio_path,
            video_duration=video_duration,
            audio_duration=audio_duration,
            output_path=str(merged_path)
        )

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode == 0 and merged_path.exists():
                merged_clips.append(str(merged_path))
        except Exception as e:
            logger.error(f"Error merging segment {seg_idx}: {e}")

    if not merged_clips:
        return {"video_path": None, "audio_path": None}

    # Concatenate all merged clips
    final_video = output_dir / "final_section.mp4"
    final_audio = output_dir / "audio.mp3"

    try:
        await concatenate_videos(merged_clips, str(final_video))
    except Exception as e:
        logger.error(f"Error concatenating segments: {e}")
        if merged_clips:
            shutil.copy(merged_clips[0], str(final_video))

    # Extract audio
    if final_video.exists():
        cmd = [
            "ffmpeg", "-y",
            "-i", str(final_video),
            "-vn",
            "-acodec", "libmp3lame",
            str(final_audio)
        ]
        try:
            await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                timeout=120
            )
        except Exception:
            pass

    return {
        "video_path": str(final_video) if final_video.exists() else None,
        "audio_path": str(final_audio) if final_audio.exists() else None
    }


async def merge_subsections(
    generator: "VideoGenerator",
    subsection_results: List[Dict[str, Any]],
    output_dir: Path,
    section_index: int
) -> Dict[str, Any]:
    """Merge subsection videos+audios into a single section video"""
    merged_clips = []

    for sub_idx, sub_result in enumerate(subsection_results):
        video_path = sub_result["video_path"]
        audio_path = sub_result["audio_path"]
        merged_path = output_dir / f"merged_sub_{sub_idx}.mp4"

        audio_duration = await get_media_duration(audio_path)
        video_duration = await get_media_duration(video_path)

        cmd = build_retime_merge_cmd(
            video_path=video_path,
            audio_path=audio_path,
            video_duration=video_duration,
            audio_duration=audio_duration,
            output_path=str(merged_path)
        )

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode == 0 and merged_path.exists():
                merged_clips.append(str(merged_path))
            else:
                logger.error(f"FFmpeg error merging subsection {sub_idx}: {result.stderr}")
        except Exception as e:
            logger.error(f"Error merging subsection {sub_idx}: {e}")

    if not merged_clips:
        return {"video_path": None, "audio_path": None}

    final_video = output_dir / "final_section.mp4"
    final_audio = output_dir / "audio.mp3"

    try:
        await concatenate_videos(merged_clips, str(final_video))
    except Exception as e:
        logger.error(f"Error concatenating subsections: {e}")
        if merged_clips:
            shutil.copy(merged_clips[0], str(final_video))

    # Extract audio from final video
    if final_video.exists():
        cmd = [
            "ffmpeg", "-y",
            "-i", str(final_video),
            "-vn",
            "-acodec", "libmp3lame",
            str(final_audio)
        ]
        try:
            await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                timeout=120
            )
        except Exception as e:
            logger.error(f"Error extracting audio: {e}")

    return {
        "video_path": str(final_video) if final_video.exists() else None,
        "audio_path": str(final_audio) if final_audio.exists() else None
    }
