"""
Audio and video utilities for ffmpeg operations
"""

import asyncio
import subprocess
import shutil
from typing import List
from pathlib import Path


async def get_audio_duration(audio_path: str) -> float:
    """Get duration of audio file using ffprobe"""
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            audio_path
        ]
        result = await asyncio.to_thread(
            subprocess.run,
            cmd,
            capture_output=True,
            text=True
        )
        return float(result.stdout.strip())
    except Exception:
        return 30.0  # Default duration


async def get_media_duration(file_path: str) -> float:
    """Get duration of a media file using ffprobe"""
    try:
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path
        ]
        result = await asyncio.to_thread(
            subprocess.run,
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        return float(result.stdout.strip())
    except Exception as e:
        print(f"Error getting duration for {file_path}: {e}")
        return 0.0


async def generate_silence(output_path: str, duration: float) -> None:
    """Generate a silent audio file of specified duration"""
    try:
        cmd = [
            "ffmpeg",
            "-f", "lavfi",
            "-i", "anullsrc=r=44100:cl=stereo",
            "-t", str(duration),
            "-q:a", "9",
            "-y",
            output_path
        ]
        await asyncio.to_thread(
            subprocess.run,
            cmd,
            capture_output=True,
            check=True
        )
        print(f"Generated {duration:.1f}s silence: {output_path}")
    except Exception as e:
        print(f"Silence generation failed: {e}")
        raise


async def concatenate_audio_files(
    audio_paths: List[str],
    output_path: str
) -> bool:
    """Concatenate multiple audio files into one using ffmpeg"""
    if not audio_paths:
        return False

    if len(audio_paths) == 1:
        shutil.copy(audio_paths[0], output_path)
        return True

    # Create concat file list
    concat_list_path = Path(output_path).parent / "concat_audio_list.txt"
    with open(concat_list_path, 'w', encoding="utf-8") as f:
        for audio_path in audio_paths:
            f.write(f"file '{audio_path}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list_path),
        "-c", "copy",
        output_path
    ]

    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        _, stderr = await asyncio.wait_for(process.communicate(), timeout=120)

        if process.returncode != 0:
            print(f"Audio concatenation failed: {stderr.decode()[:500]}")
            return False

        return Path(output_path).exists()
    except Exception as e:
        print(f"Error concatenating audio: {e}")
        return False
    finally:
        # Cleanup
        if concat_list_path.exists():
            concat_list_path.unlink()


async def pad_audio_with_silence(
    audio_path: str,
    target_duration: float,
    output_path: str
) -> str:
    """Pad audio with silence to reach target duration (no trimming)."""
    try:
        current_duration = await get_media_duration(audio_path)
    except Exception:
        current_duration = 0.0

    if current_duration >= target_duration - 0.05:
        return audio_path

    silence_duration = max(0.0, target_duration - current_duration)
    silence_path = str(Path(output_path).with_suffix(".silence.mp3"))

    try:
        await generate_silence(silence_path, silence_duration)
        success = await concatenate_audio_files(
            [audio_path, silence_path],
            output_path
        )
        if success and Path(output_path).exists():
            return output_path
    finally:
        if Path(silence_path).exists():
            Path(silence_path).unlink()

    return audio_path


def build_retime_merge_cmd(
    video_path: str,
    audio_path: str,
    video_duration: float,
    audio_duration: float,
    output_path: str
) -> List[str]:
    """Build ffmpeg command to merge video with audio.
    
    Strategy:
    - If video is SHORTER than audio: Pad with frozen last frame (tpad)
    - If video is LONGER than audio: Trim video to audio length
    - Never slow down or speed up the video
    """
    if not video_duration or not audio_duration:
        return [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "libx264",
            "-c:a", "aac",
            output_path
        ]

    duration_diff = abs(video_duration - audio_duration)

    # If durations are close enough, just merge directly
    if duration_diff < 0.1:
        return [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-shortest",
            output_path
        ]

    if video_duration < audio_duration:
        # Video is SHORTER than audio - PAD with frozen last frame
        # tpad: stop_duration = how many seconds to add, stop_mode=clone freezes last frame
        pad_duration = audio_duration - video_duration
        print(f"[Merge] Video shorter by {pad_duration:.1f}s - padding with last frame")
        return [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            "-filter_complex", f"[0:v]tpad=stop_duration={pad_duration:.3f}:stop_mode=clone[v]",
            "-map", "[v]",
            "-map", "1:a:0",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-t", f"{audio_duration:.3f}",
            output_path
        ]
    else:
        # Video is LONGER than audio - TRIM video to match audio
        print(f"[Merge] Video longer by {duration_diff:.1f}s - trimming to audio length")
        return [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "libx264",
            "-c:a", "aac",
            "-t", f"{audio_duration:.3f}",
            output_path
        ]


def build_merge_no_cut_cmd(
    video_path: str,
    audio_path: str,
    video_duration: float,
    audio_duration: float,
    output_path: str
) -> List[str]:
    """Build ffmpeg command to merge video with audio WITHOUT cutting either.
    
    Strategy:
    - Pad VIDEO with frozen last frame to match the longer duration
    - Never pad audio (do not synthesize silence)
    - Never cut or trim either media
    """
    if not video_duration or not audio_duration:
        return [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "libx264",
            "-c:a", "aac",
            output_path
        ]

    duration_diff = abs(video_duration - audio_duration)

    # If durations are close enough, just merge directly
    if duration_diff < 0.1:
        return [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-c:v", "libx264",
            "-c:a", "aac",
            output_path
        ]

    # Always pad VIDEO to the longer duration (never pad audio)
    target_duration = max(video_duration, audio_duration)
    pad_duration = max(0.0, target_duration - video_duration)
    if pad_duration > 0:
        print(f"[Merge No-Cut] Video shorter by {pad_duration:.1f}s - padding video with last frame")
    else:
        print(f"[Merge No-Cut] Video is longer or equal; no padding needed")

    return [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", audio_path,
        "-filter_complex", f"[0:v]tpad=stop_duration={pad_duration:.3f}:stop_mode=clone[v]",
        "-map", "[v]",
        "-map", "1:a:0",
        "-c:v", "libx264",
        "-c:a", "aac",
        "-t", f"{target_duration:.3f}",
        output_path
    ]


async def combine_sections(
    videos: List[str],
    audios: List[str],  # May contain None for sections without audio
    output_path: str,
    sections_dir: str
):
    """Combine video sections with their audio
    
    IMPORTANT: Never trim video. Retiming is used to match audio length.
    """

    # First, merge each video with its audio
    merged_sections = []

    for i, (video, audio) in enumerate(zip(videos, audios)):
        merged_path = Path(sections_dir) / f"merged_{i}.mp4"

        if audio is None:
            # No audio for this section - just copy the video
            print(f"Section {i}: No audio, using video as-is")
            merged_sections.append(video)
            continue

        # Get audio duration first
        audio_duration = await get_media_duration(audio)
        video_duration = await get_media_duration(video)

        print(f"Section {i}: Video={video_duration:.1f}s, Audio={audio_duration:.1f}s")

        # CRITICAL: Never trim video. Retiming is used to match audio length.
        cmd = build_retime_merge_cmd(
            video_path=video,
            audio_path=audio,
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
            if result.returncode != 0:
                print(f"FFmpeg error section {i}: {result.stderr}")

            if merged_path.exists():
                merged_sections.append(str(merged_path))
            else:
                print(f"Merged file not created for section {i}, using video")
                merged_sections.append(video)
        except Exception as e:
            print(f"Error merging section {i}: {e}")
            # Use original video if merge fails
            merged_sections.append(video)

    # Now concatenate all merged sections
    if merged_sections:
        await concatenate_videos(merged_sections, output_path)


async def concatenate_videos(videos: List[str], output_path: str):
    """Concatenate multiple videos into one"""

    if not videos:
        return

    if len(videos) == 1:
        shutil.copy(videos[0], output_path)
        return

    # Create concat file
    concat_file = Path(output_path).parent / "concat_list.txt"
    with open(concat_file, "w", encoding="utf-8") as f:
        for video in videos:
            f.write(f"file '{video}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy",
        output_path
    ]

    try:
        result = await asyncio.to_thread(
            subprocess.run,
            cmd,
            capture_output=True,
            text=True,
            timeout=300
        )

        if result.returncode != 0:
            print(f"Concat error: {result.stderr}")
            # Try re-encoding
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_file),
                "-c:v", "libx264",
                "-c:a", "aac",
                output_path
            ]
            await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                timeout=300
            )
    except Exception as e:
        print(f"Concatenation error: {e}")
