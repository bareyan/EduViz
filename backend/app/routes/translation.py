"""
Translation routes
"""

import os
import json
import asyncio
import shutil
from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from ..config import OUTPUT_DIR
from ..services.features.translation import get_translation_service
from ..services.pipeline.audio import TTSEngine
from ..services.pipeline.animation import ManimGenerator
from ..core import (
    get_media_duration,
    load_script,
    load_script_raw,
    job_intermediate_artifacts_available,
    job_is_final_only,
    assert_runtime_tools_available,
)
from ..core.voice_catalog import (
    get_translation_default_voice,
    get_translation_languages as list_translation_languages,
)

router = APIRouter(tags=["translation"])


class TranslationRequest(BaseModel):
    target_language: str
    voice: Optional[str] = None


class TranslationResponse(BaseModel):
    job_id: str
    translation_id: str
    target_language: str
    status: str
    message: str


def get_voice_for_language(language: str) -> str:
    """Get appropriate TTS voice for a language"""
    return get_translation_default_voice(language)


@router.get("/translation/languages")
async def get_translation_languages():
    """Get supported target languages for video translation."""
    return {"languages": list_translation_languages()}


def _cleanup_translation_artifacts(translation_dir: str) -> None:
    """
    Keep only final_video.mp4 in a translation output directory.
    """
    path = os.path.abspath(translation_dir)
    if not os.path.isdir(path):
        return

    for name in os.listdir(path):
        if name == "final_video.mp4":
            continue

        entry = os.path.join(path, name)
        if os.path.isdir(entry):
            shutil.rmtree(entry, ignore_errors=True)
        else:
            try:
                os.remove(entry)
            except FileNotFoundError:
                pass


@router.get("/job/{job_id}/translations")
async def get_job_translations(job_id: str):
    """Get all available translations for a job"""
    job_dir = OUTPUT_DIR / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail="Job not found")

    translations = []

    translations_dir = job_dir / "translations"
    if translations_dir.exists():
        for lang_dir in os.listdir(translations_dir):
            lang_path = translations_dir / lang_dir
            if lang_path.is_dir():
                script_path = lang_path / "script.json"
                video_path = lang_path / "final_video.mp4"

                translations.append({
                    "language": lang_dir,
                    "has_script": script_path.exists(),
                    "has_video": video_path.exists(),
                    "video_url": f"/outputs/{job_id}/translations/{lang_dir}/final_video.mp4" if video_path.exists() else None
                })

    original_language = "en"
    script_path = job_dir / "script.json"
    if script_path.exists():
        with open(script_path, "r") as f:
            script = json.load(f)
        original_language = script.get("source_language", script.get("language", "en"))

    return {
        "job_id": job_id,
        "original_language": original_language,
        "translations": translations
    }


@router.post("/job/{job_id}/translate", response_model=TranslationResponse)
async def create_translation(job_id: str, request: TranslationRequest, background_tasks: BackgroundTasks):
    """Start translation of a completed video to a new language"""
    assert_runtime_tools_available(("manim", "ffmpeg", "ffprobe"), context="translation generation")

    job_dir = OUTPUT_DIR / job_id
    if not job_dir.exists():
        raise HTTPException(status_code=404, detail="Job not found")

    final_video = job_dir / "final_video.mp4"
    if not final_video.exists():
        raise HTTPException(status_code=400, detail="Original video not yet generated")

    if not job_intermediate_artifacts_available(job_id):
        if job_is_final_only(job_id):
            raise HTTPException(
                status_code=409,
                detail=(
                    "This job was cleaned to final-video-only retention. "
                    "Translation requires script and section artifacts."
                ),
            )
        raise HTTPException(status_code=400, detail="Job artifacts are incomplete for translation")

    script_path = job_dir / "script.json"
    if not script_path.exists():
        raise HTTPException(status_code=400, detail="Script not found for this job")

    target_language = request.target_language
    translation_id = f"{job_id}_{target_language}"

    translation_dir = job_dir / "translations" / target_language
    translation_dir.mkdir(parents=True, exist_ok=True)

    async def run_translation():
        try:
            translation_service = get_translation_service()

            # Load script using the centralized loader that handles unwrapping
            original_script = load_script(job_id)
            
            # For source language, try to get from raw script metadata first
            try:
                raw_script = load_script_raw(job_id)
                source_language = raw_script.get("output_language", raw_script.get("detected_language", "en"))
            except:
                source_language = original_script.get("source_language", original_script.get("language", "en"))

            print(f"[Translation] Starting translation from {source_language} to {target_language}")

            translated_script = await translation_service.translate_script(
                original_script,
                target_language,
                source_language
            )

            translated_script_path = translation_dir / "script.json"
            with open(translated_script_path, "w", encoding="utf-8") as f:
                json.dump(translated_script, f, indent=2, ensure_ascii=False)

            print("[Translation] Script translated, now generating video...")

            voice = request.voice if request.voice else get_voice_for_language(target_language)

            await generate_translated_video(
                job_id,
                translated_script,
                str(translation_dir),
                target_language,
                voice
            )

            print(f"[Translation] Translation complete for {target_language}")

        except Exception as e:
            print(f"[Translation] Error: {e}")
            import traceback
            traceback.print_exc()

    background_tasks.add_task(run_translation)

    return TranslationResponse(
        job_id=job_id,
        translation_id=translation_id,
        target_language=target_language,
        status="processing",
        message=f"Translation to {target_language} started"
    )


async def generate_translated_video(
    job_id: str,
    translated_script: Dict[str, Any],
    output_dir: str,
    target_language: str,
    voice: str
):
    """Generate video from translated script with translated Manim animations"""
    from ..services.features.translation import TranslationService

    tts_engine = TTSEngine()
    manim_gen = ManimGenerator()
    translation_service = TranslationService()

    source_language = translated_script.get("translated_from", "en")

    sections = translated_script.get("sections", [])
    section_videos = []

    for i, section in enumerate(sections):
        print(f"[Translation] Processing section {i+1}/{len(sections)}")

        section_dir = os.path.join(output_dir, f"section_{i}")
        os.makedirs(section_dir, exist_ok=True)

        narration = section.get("tts_narration", section.get("narration", ""))
        if not narration:
            continue

        audio_path = os.path.join(section_dir, "audio.mp3")

        try:
            await tts_engine.generate_speech(
                text=narration,
                output_path=audio_path,
                voice=voice
            )
        except Exception as e:
            print(f"[Translation] TTS error for section {i}: {e}")
            continue

        audio_duration = await get_media_duration(audio_path)

        # Find original section directory
        original_section_dir = None
        section_video_path = section.get("video", "")
        section_audio_path = section.get("audio", "")

        if section_video_path and os.path.exists(section_video_path):
            original_section_dir = os.path.dirname(section_video_path)
        elif section_audio_path and os.path.exists(section_audio_path):
            original_section_dir = os.path.dirname(section_audio_path)

        if not original_section_dir or not os.path.isdir(original_section_dir):
            section_id_dir = section.get("id")
            possible_dirs = []
            if section_id_dir:
                possible_dirs.append(os.path.join(str(OUTPUT_DIR), job_id, "sections", section_id_dir))
            possible_dirs.append(os.path.join(str(OUTPUT_DIR), job_id, "sections", f"section_{i}"))

            for sd in possible_dirs:
                if os.path.isdir(sd):
                    original_section_dir = sd
                    break

        if not original_section_dir:
            original_section_dir = os.path.join(str(OUTPUT_DIR), job_id, "sections", section.get("id", f"section_{i}"))

        original_manim_path = ""
        if os.path.isdir(original_section_dir):
            for f in os.listdir(original_section_dir):
                if f.startswith("scene") and f.endswith(".py"):
                    original_manim_path = os.path.join(original_section_dir, f)
                    break

        original_manim = section.get("manim_code", "")

        if not original_manim and original_manim_path and os.path.exists(original_manim_path):
            with open(original_manim_path, "r") as f:
                original_manim = f.read()

        video_path = None

        if original_manim:
            try:
                translated_manim = await translation_service.translate_manim_code(
                    original_manim,
                    target_language,
                    source_language
                )

                translated_manim_path = os.path.join(section_dir, "scene.py")
                with open(translated_manim_path, "w", encoding="utf-8") as f:
                    f.write(translated_manim)

                video_path = await manim_gen.render_from_code(
                    translated_manim,
                    section_dir,
                    section_index=i
                )

            except Exception as e:
                print(f"[Translation] Manim translation/render error: {e}")
                video_path = None

        if not video_path or not os.path.exists(video_path):
            original_section_video = os.path.join(original_section_dir, "final_section.mp4") if original_section_dir else ""
            if not os.path.exists(original_section_video):
                original_section_video = section.get("video", "")

            if os.path.exists(original_section_video):
                video_path = original_section_video
            else:
                continue

        video_duration = await get_media_duration(video_path)
        output_video = os.path.join(section_dir, "translated_section.mp4")

        if audio_duration > video_duration * 0.9 and audio_duration < video_duration * 1.5:
            speed_factor = video_duration / audio_duration
            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-i", audio_path,
                "-filter_complex", f"[0:v]setpts={1/speed_factor}*PTS[v]",
                "-map", "[v]",
                "-map", "1:a",
                "-c:v", "libx264",
                "-c:a", "aac",
                "-shortest",
                output_video
            ]
        elif audio_duration > video_duration * 1.5:
            extend_duration = audio_duration - video_duration
            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-i", audio_path,
                "-filter_complex", f"[0:v]tpad=stop_mode=clone:stop_duration={extend_duration}[v]",
                "-map", "[v]",
                "-map", "1:a",
                "-c:v", "libx264",
                "-c:a", "aac",
                output_video
            ]
        else:
            silence_duration = video_duration - audio_duration
            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-i", audio_path,
                "-filter_complex", f"[1:a]apad=pad_dur={silence_duration}[a]",
                "-map", "0:v",
                "-map", "[a]",
                "-c:v", "libx264",
                "-c:a", "aac",
                "-t", str(video_duration),
                output_video
            ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await asyncio.wait_for(process.communicate(), timeout=300)

            if process.returncode == 0 and os.path.exists(output_video):
                section_videos.append(output_video)
            else:
                print(f"[Translation] FFmpeg error: {stderr.decode()[:500]}")
        except Exception as e:
            print(f"[Translation] Error processing section {i}: {e}")

    if section_videos:
        final_video = os.path.join(output_dir, "final_video.mp4")

        concat_file = os.path.join(output_dir, "concat.txt")
        with open(concat_file, "w", encoding="utf-8") as f:
            for video in section_videos:
                f.write(f"file '{video}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_file,
            "-c", "copy",
            final_video
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()

        if os.path.exists(final_video):
            _cleanup_translation_artifacts(output_dir)
            print(f"[Translation] Final video created: {final_video}")
