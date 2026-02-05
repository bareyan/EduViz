"""
Section processor - handles individual section and segment processing
"""

import os
import re
import asyncio
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
        "duration": 30,
        "manim_code": None
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
            if manim_result.get("manim_code"):
                result["manim_code"] = manim_result["manim_code"]
    except Exception as e:
        import traceback
        logger.error(f"Manim error for section {section_index}: {e}")
        traceback.print_exc()
        write_status(section_dir, "fixing_error", str(e))

    return result


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
    """
    result = {
        "video_path": None,
        "audio_path": None,
        "duration": 0,
        "manim_code": None
    }

    num_segments = len(narration_segments)
    logger.info(f"Section {section_index}: Processing {num_segments} segments (audio-first, unified video)")

    # Status: generating audio
    write_status(section_dir, "generating_audio")

    # Step 1: Generate audio for ALL segments first
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

    total_duration = cumulative_time
    logger.info(f"Section {section_index}: Total audio duration = {total_duration:.1f}s")

    # Step 2: Concatenate all audio segments
    section_audio_path = section_dir / "section_audio.mp3"
    valid_audio_paths = [s["audio_path"] for s in segment_audio_info if s["audio_path"]]

    if len(valid_audio_paths) > 1:
        await concatenate_audio_files(valid_audio_paths, str(section_audio_path))
    elif len(valid_audio_paths) == 1:
        shutil.copy(valid_audio_paths[0], str(section_audio_path))
    else:
        logger.warning(f"Section {section_index}: No valid audio segments")
        return result

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
    manim_code = None

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
        if isinstance(manim_result, dict) and manim_result.get("manim_code"):
            manim_code = manim_result["manim_code"]
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

    result["manim_code"] = manim_code

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
