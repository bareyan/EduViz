"""Gemini TTS engine."""

from __future__ import annotations

import asyncio
import os
import time
import wave
from typing import Optional

from app.core import get_logger

from .audio_payload import extract_inline_audio_payload
from .constants import DEFAULT_GEMINI_MODEL, DEFAULT_GEMINI_VOICE, GEMINI_VOICES

logger = get_logger(__name__, component="gemini_tts")


class _RateLimiter:
    """Simple sliding-window rate limiter for RPM constraint."""

    def __init__(self, max_rpm: int = 8):
        self.max_rpm = max_rpm
        self._timestamps: list[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            self._timestamps = [t for t in self._timestamps if now - t < 60]

            if len(self._timestamps) >= self.max_rpm:
                oldest = self._timestamps[0]
                wait = 60.0 - (now - oldest) + 0.2
                if wait > 0:
                    logger.info(
                        f"Rate limit: waiting {wait:.1f}s "
                        f"({len(self._timestamps)}/{self.max_rpm} RPM used)"
                    )
                    await asyncio.sleep(wait)
                    now = time.monotonic()
                    self._timestamps = [t for t in self._timestamps if now - t < 60]

            self._timestamps.append(time.monotonic())


_rate_limiter = _RateLimiter(max_rpm=int(os.getenv("GEMINI_TTS_RPM", "8")))


class GeminiTTSEngine:
    """Text-to-Speech engine using Google Gemini 2.5 Flash TTS."""

    VOICES = GEMINI_VOICES
    DEFAULT_VOICE = DEFAULT_GEMINI_VOICE

    def __init__(self, model: str = DEFAULT_GEMINI_MODEL):
        self.model = model

    async def synthesize(
        self,
        text: str,
        output_path: str,
        voice: Optional[str] = None,
        rate: str = "+0%",
        pitch: str = "+0Hz",
    ) -> float:
        voice = voice or self.DEFAULT_VOICE
        if voice not in GEMINI_VOICES:
            logger.warning(
                f"Unknown Gemini voice '{voice}', falling back to {self.DEFAULT_VOICE}"
            )
            voice = self.DEFAULT_VOICE

        await _rate_limiter.acquire()

        pcm_data = await self._call_gemini_tts(text, voice)
        if pcm_data is None:
            return await self._create_placeholder_audio(text, output_path)

        wav_path = output_path.rsplit(".", 1)[0] + ".wav"
        self._write_wav(wav_path, pcm_data)
        await self._convert_wav_to_mp3(wav_path, output_path)

        duration = await self._get_audio_duration(output_path)
        logger.info(f"Gemini TTS: generated {duration:.1f}s audio ({len(text)} chars)")
        return duration

    async def generate_speech(
        self,
        text: str,
        output_path: str,
        voice: Optional[str] = None,
        rate: str = "+0%",
    ) -> float:
        return await self.synthesize(text, output_path, voice, rate=rate)

    async def _call_gemini_tts(
        self, text: str, voice: str
    ) -> Optional[bytes]:
        try:
            from google import genai
            from google.genai import types

            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("GEMINI_API_KEY env var is required for Gemini TTS")

            client = genai.Client(api_key=api_key)

            config = types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice,
                        )
                    )
                ),
            )

            response = await asyncio.to_thread(
                client.models.generate_content,
                model=self.model,
                contents=text,
                config=config,
            )

            audio_bytes, _mime_type = extract_inline_audio_payload(response)
            return audio_bytes

        except Exception as e:
            logger.error(f"Gemini TTS API error: {e}", exc_info=True)
            return None

    @staticmethod
    def _write_wav(
        path: str,
        pcm: bytes,
        channels: int = 1,
        rate: int = 24000,
        sample_width: int = 2,
    ) -> None:
        with wave.open(path, "wb") as wf:
            wf.setnchannels(channels)
            wf.setsampwidth(sample_width)
            wf.setframerate(rate)
            wf.writeframes(pcm)

    @staticmethod
    async def _convert_wav_to_mp3(wav_path: str, mp3_path: str) -> None:
        cmd = [
            "ffmpeg", "-y",
            "-i", wav_path,
            "-acodec", "libmp3lame",
            "-ab", "192k",
            mp3_path,
        ]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        if process.returncode != 0:
            logger.warning(f"WAV->MP3 conversion failed: {stderr.decode()[:300]}")

        try:
            os.remove(wav_path)
        except OSError:
            pass

    @staticmethod
    async def _get_audio_duration(audio_path: str) -> float:
        try:
            cmd = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                audio_path,
            ]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await process.communicate()
            return float(stdout.decode().strip())
        except Exception:
            return 30.0

    async def _create_placeholder_audio(
        self, text: str, output_path: str
    ) -> float:
        word_count = len(text.split())
        duration = max(3.0, word_count / 2.5)
        try:
            cmd = [
                "ffmpeg", "-y",
                "-f", "lavfi",
                "-i", "anullsrc=r=44100:cl=mono",
                "-t", str(duration),
                "-acodec", "libmp3lame",
                output_path,
            ]
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            await process.communicate()
        except Exception as e:
            logger.error(f"Failed to create placeholder audio: {e}")
            with open(output_path, "wb"):
                pass
        return duration

    @classmethod
    def get_available_voices(cls) -> dict:
        return cls.VOICES

    @classmethod
    def get_default_voice(cls) -> str:
        return cls.DEFAULT_VOICE
