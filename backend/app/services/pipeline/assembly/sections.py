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
        # Using the NEW Animation Pipeline (Choreograph -> Implement -> Refine)
        manim_result = await manim_generator.generate_animation(
            section=section,
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

    # Join segments with a very long pause marker so Gemini TTS produces
    # an unmistakable ~3-5 s silence between segments.  Short dot sequences
    # (the old marker) sometimes cause Gemini to produce breathy "haaah"
    # artifacts instead of silence; a much longer marker guarantees a
    # reliably long pause that we detect and trim after generation.
    PAUSE_MARKER = (
        "...... ...... ...... ...... ...... "
        "...... ...... ...... ...... ......"
    )
    full_text = f" {PAUSE_MARKER} ".join(cleaned_texts)

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

    # ---- Find segment boundaries via energy-valley analysis ----
    # This always finds exactly N-1 boundaries regardless of whether
    # Gemini produced clean silence, breathing, or other artifacts.
    pause_regions = await _find_energy_valleys(
        str(section_audio_path),
        num_valleys=num_boundaries,
    )

    if len(pause_regions) >= num_boundaries:
        logger.info(
            f"Section {section_index}: Found {len(pause_regions)} energy valleys, "
            f"splitting into {len(narration_segments)} segments"
        )
        segment_audio_info = await _split_audio_at_pauses(
            section_audio_path=str(section_audio_path),
            pause_regions=pause_regions,
            narration_segments=narration_segments,
            cleaned_texts=cleaned_texts,
            section_dir=section_dir,
            total_duration=total_duration,
        )
        if segment_audio_info:
            cumulative_time = sum(s["duration"] for s in segment_audio_info)
            return segment_audio_info, cumulative_time

    # Last-resort fallback (should be very rare — only if the audio
    # file is corrupt or contains pure silence/noise).
    logger.warning(
        f"Section {section_index}: Energy-valley detection failed "
        f"({len(pause_regions)}/{num_boundaries} found), "
        f"using proportional timing"
    )
    return await _distribute_timing_proportionally(
        narration_segments=narration_segments,
        cleaned_texts=cleaned_texts,
        section_audio_path=str(section_audio_path),
        section_dir=section_dir,
        total_duration=total_duration,
    )


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
# Energy-valley segment boundary detection
# ---------------------------------------------------------------------------

_VALLEY_SAMPLE_RATE = 16000  # Hz — low is fine, we only need the energy envelope
_VALLEY_WINDOW_SEC = 0.05    # 50 ms windows for RMS computation
_VALLEY_SMOOTH_SEC = 0.5     # smoothing kernel


async def _find_energy_valleys(
    audio_path: str,
    num_valleys: int,
    window_sec: float = _VALLEY_WINDOW_SEC,
    smooth_sec: float = _VALLEY_SMOOTH_SEC,
    min_valley_sec: float = 0.3,
) -> List[tuple[float, float]]:
    """Find the *num_valleys* quietest regions in *audio_path*.

    Unlike threshold-based ``silencedetect``, this approach **always** finds
    exactly *num_valleys* boundaries regardless of absolute volume levels.
    It works reliably even when Gemini TTS inserts breathing artifacts
    ("haaah") instead of clean silence, because the energy in a breathy
    pause is still significantly lower than normal speech.

    Algorithm
    ---------
    1. Decode audio → raw mono 16-bit PCM via ffmpeg (cheap).
    2. Compute RMS energy per 50 ms window.
    3. Smooth with a ½-second rolling average.
    4. Find contiguous regions whose energy is below the median.
    5. Score each region by ``depth × width`` (wider & deeper = better).
    6. Return the top *num_valleys* regions sorted by time.

    Returns ``[(start_sec, end_sec), ...]``.
    """
    if num_valleys <= 0:
        return []

    try:
        energy, window_sec_actual = await _extract_energy_envelope(
            audio_path, window_sec, smooth_sec
        )
    except Exception as e:
        logger.error(f"Energy extraction failed: {e}")
        return []

    if len(energy) < 3:
        return []

    # --- Find valleys: contiguous regions below the median ---
    median_e = sorted(energy)[len(energy) // 2]
    min_valley_windows = max(1, int(min_valley_sec / window_sec_actual))

    regions: list[tuple[float, float, float]] = []  # (start_t, end_t, score)
    in_valley = False
    v_start = 0

    for i, e in enumerate(energy):
        if e < median_e and not in_valley:
            v_start = i
            in_valley = True
        elif (e >= median_e or i == len(energy) - 1) and in_valley:
            v_end = i if e >= median_e else i + 1
            width = v_end - v_start
            if width >= min_valley_windows:
                depth = median_e - min(energy[v_start:v_end])
                score = depth * (width ** 1.5)  # favour wider valleys
                t_start = v_start * window_sec_actual
                t_end = v_end * window_sec_actual
                regions.append((t_start, t_end, score))
            in_valley = False

    # Take top N by score, then sort chronologically
    regions.sort(key=lambda r: r[2], reverse=True)
    top = regions[:num_valleys]
    top.sort(key=lambda r: r[0])

    result = [(s, e) for s, e, _ in top]
    logger.info(
        f"Energy-valley: found {len(regions)} candidate valleys, "
        f"selected top {len(result)}: "
        f"{[(f'{s:.2f}', f'{e:.2f}') for s, e in result]}"
    )
    return result


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


async def _detect_silence_boundaries(
    audio_path: str,
    silence_thresh: str = "-35dB",
    min_silence_duration: float = 0.8,
    merge_gap: float = 1.0,
) -> List[tuple[float, float]]:
    """Detect silence/pause regions in audio using ffmpeg ``silencedetect``.

    Returns a list of ``(start, end)`` tuples marking each detected silence
    region.  Nearby silences separated by less than *merge_gap* seconds are
    merged into a single region — this handles intermittent breathing /
    "haaah" artifacts that Gemini TTS sometimes produces inside what should
    be a long pause.
    """
    cmd = [
        "ffmpeg",
        "-i", audio_path,
        "-af", f"silencedetect=noise={silence_thresh}:d={min_silence_duration}",
        "-f", "null",
        "-"
    ]

    try:
        result = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await result.communicate()
        output = stderr.decode('utf-8', errors='ignore')

        # Parse silence_start and silence_end from ffmpeg output
        silence_starts: list[float] = []
        silence_ends: list[float] = []

        for line in output.split('\n'):
            if 'silence_start:' in line:
                try:
                    time_str = line.split('silence_start:')[1].strip().split()[0]
                    silence_starts.append(float(time_str))
                except (IndexError, ValueError):
                    pass
            elif 'silence_end:' in line:
                try:
                    time_str = line.split('silence_end:')[1].strip().split()[0]
                    silence_ends.append(float(time_str))
                except (IndexError, ValueError):
                    pass

        raw_regions: list[tuple[float, float]] = list(zip(silence_starts, silence_ends))

        # ---- merge nearby silences ----
        # When Gemini inserts a breathy artifact inside a long pause the
        # silence detector sees two (or more) separate silence chunks with
        # a brief noisy gap between them.  Merging turns them back into one
        # contiguous pause region.
        if not raw_regions:
            return []

        merged: list[tuple[float, float]] = [raw_regions[0]]
        for start, end in raw_regions[1:]:
            prev_start, prev_end = merged[-1]
            if start - prev_end <= merge_gap:
                merged[-1] = (prev_start, end)  # extend
            else:
                merged.append((start, end))

        logger.debug(
            f"Detected {len(raw_regions)} raw silences, merged into "
            f"{len(merged)} pause regions: "
            f"{[(f'{s:.2f}', f'{e:.2f}') for s, e in merged]}"
        )
        return merged

    except Exception as e:
        logger.error(f"Error detecting silence: {e}")
        return []


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


async def _split_audio_at_pauses(
    section_audio_path: str,
    pause_regions: List[tuple[float, float]],
    narration_segments: List[Dict[str, Any]],
    cleaned_texts: List[str],
    section_dir: Path,
    total_duration: float,
) -> List[Dict[str, Any]]:
    """Split audio at detected pause regions, extracting speech-only segments.

    Each segment spans from the *end* of the previous pause to the *start*
    of the next pause, so the long Gemini pauses (and any breathy artifacts
    inside them) are excluded from the individual segment files.

    After extraction each segment's leading/trailing silence is trimmed to
    produce clean audio.
    """
    segment_audio_info = []
    num_segments = len(narration_segments)

    # Trim excess pause regions
    regions = pause_regions[:num_segments - 1] if len(pause_regions) >= num_segments else pause_regions

    if len(regions) < num_segments - 1:
        logger.warning(f"Insufficient pause regions: {len(regions)} for {num_segments} segments")
        return []

    # Build speech-only boundaries:
    #   seg 0  →  [0, regions[0].start]
    #   seg i  →  [regions[i-1].end, regions[i].start]
    #   seg N  →  [regions[-1].end, total_duration]
    speech_boundaries: list[tuple[float, float]] = []
    for seg_idx in range(num_segments):
        if seg_idx == 0:
            start = 0.0
            end = regions[0][0] if regions else total_duration
        elif seg_idx == num_segments - 1:
            start = regions[-1][1]
            end = total_duration
        else:
            start = regions[seg_idx - 1][1]
            end = regions[seg_idx][0]
        speech_boundaries.append((start, end))

    # Extract each segment
    for seg_idx, (start_time, end_time) in enumerate(speech_boundaries):
        seg_duration = end_time - start_time

        seg_dir = section_dir / f"seg_{seg_idx}"
        seg_dir.mkdir(exist_ok=True)
        raw_seg_path = seg_dir / "audio_raw.mp3"
        seg_audio_path = seg_dir / "audio.mp3"

        # Extract the speech region from the full audio
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

            # Trim any residual silence at segment edges
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
                f"(speech {start_time:.2f}s–{end_time:.2f}s)"
            )

        except Exception as e:
            logger.error(f"Error extracting segment {seg_idx}: {e}")
            # Fallback: use the full audio with estimated timing
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
    mode_label = "whole-section" if use_whole_section else "per-segment"
    logger.info(f"Section {section_index}: Processing {num_segments} segments (audio-first, {mode_label})")

    # Status: generating audio
    write_status(section_dir, "generating_audio")

    # Step 1 & 2: Generate audio — strategy depends on engine type
    if use_whole_section:
        segment_audio_info, total_duration = await _generate_audio_whole_section(
            tts_engine, narration_segments, section_dir, section_index, voice,
        )
        if not segment_audio_info:
            logger.warning(f"Section {section_index}: Whole-section TTS failed")
            return result
        # Audio file already at section_dir / "section_audio.mp3"
        section_audio_path = section_dir / "section_audio.mp3"
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
        "language": language,
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
