"""
Gemini TTS Engine - Text-to-Speech using Google Gemini 2.5 Flash TTS

Uses the Gemini API's native TTS capability with rate limiting
to respect the free-tier limits (100 RPD, 8 RPM).
"""

import asyncio
import os
import time
import wave
from typing import Optional

from app.core import get_logger

logger = get_logger(__name__, component="gemini_tts")

# ---------------------------------------------------------------------------
# Gemini TTS voice catalog
# ---------------------------------------------------------------------------
GEMINI_VOICES = {
    "Zephyr": "Bright",
    "Puck": "Upbeat",
    "Charon": "Informative",
    "Kore": "Firm",
    "Fenrir": "Excitable",
    "Leda": "Youthful",
    "Orus": "Firm",
    "Aoede": "Breezy",
    "Callirrhoe": "Easy-going",
    "Autonoe": "Bright",
    "Enceladus": "Breathy",
    "Iapetus": "Clear",
    "Umbriel": "Easy-going",
    "Algieba": "Smooth",
    "Despina": "Smooth",
    "Erinome": "Clear",
    "Algenib": "Gravelly",
    "Rasalgethi": "Informative",
    "Laomedeia": "Upbeat",
    "Achernar": "Soft",
    "Alnilam": "Firm",
    "Schedar": "Even",
    "Gacrux": "Mature",
    "Pulcherrima": "Forward",
    "Achird": "Friendly",
    "Zubenelgenubi": "Casual",
    "Vindemiatrix": "Gentle",
    "Sadachbia": "Lively",
    "Sadaltager": "Knowledgeable",
    "Sulafat": "Warm",
}

DEFAULT_GEMINI_VOICE = "Charon"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash-preview-tts"


class _RateLimiter:
    """Simple sliding-window rate limiter for RPM constraint.

    Ensures at most ``max_rpm`` calls within any rolling 60-second window.
    Callers ``await limiter.acquire()`` before making an API request.
    """

    def __init__(self, max_rpm: int = 8):
        self.max_rpm = max_rpm
        self._timestamps: list[float] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            # Evict timestamps older than 60 s
            self._timestamps = [t for t in self._timestamps if now - t < 60]

            if len(self._timestamps) >= self.max_rpm:
                oldest = self._timestamps[0]
                wait = 60.0 - (now - oldest) + 0.2  # small safety margin
                if wait > 0:
                    logger.info(
                        f"Rate limit: waiting {wait:.1f}s "
                        f"({len(self._timestamps)}/{self.max_rpm} RPM used)"
                    )
                    await asyncio.sleep(wait)
                    now = time.monotonic()
                    self._timestamps = [t for t in self._timestamps if now - t < 60]

            self._timestamps.append(time.monotonic())


# Module-level rate limiter shared across all GeminiTTSEngine instances
_rate_limiter = _RateLimiter(max_rpm=int(os.getenv("GEMINI_TTS_RPM", "8")))


class GeminiTTSEngine:
    """Text-to-Speech engine using Google Gemini 2.5 Flash TTS.

    The Gemini TTS API has strict free-tier rate limits:
      - 8 requests per minute (RPM)
      - 100 requests per day (RPD)

    This engine is designed for *whole-section* generation: instead of
    calling TTS per narration segment, callers should concatenate all
    segment texts and make a single call, then split the resulting audio
    proportionally.  This reduces API usage from ~N calls/section to 1.

    The engine outputs WAV (24 kHz, 16-bit, mono) as returned by the
    Gemini API, then optionally converts to MP3 via FFmpeg for
    compatibility with the rest of the pipeline.
    """

    # Expose voice list for the rest of the app
    VOICES = GEMINI_VOICES
    DEFAULT_VOICE = DEFAULT_GEMINI_VOICE

    def __init__(self, model: str = DEFAULT_GEMINI_MODEL):
        self.model = model
        self._client = None  # Lazy init

    # ----- lazy client -----
    def _get_client(self):
        if self._client is None:
            try:
                from google import genai

                api_key = os.getenv("GEMINI_API_KEY")
                if not api_key:
                    raise ValueError(
                        "GEMINI_API_KEY env var is required for Gemini TTS"
                    )
                self._client = genai.Client(api_key=api_key)
            except ImportError:
                raise ImportError(
                    "google-generativeai package is required for Gemini TTS. "
                    "Install with: pip install google-generativeai"
                )
        return self._client

    # ----- public interface (matches TTSEngine) -----

    async def synthesize(
        self,
        text: str,
        output_path: str,
        voice: Optional[str] = None,
        rate: str = "+0%",
        pitch: str = "+0Hz",
    ) -> float:
        """Synthesize *text* → audio file at *output_path*.

        Returns duration in seconds.
        """
        voice = voice or self.DEFAULT_VOICE
        # Validate / normalise voice name
        if voice not in GEMINI_VOICES:
            logger.warning(
                f"Unknown Gemini voice '{voice}', falling back to {self.DEFAULT_VOICE}"
            )
            voice = self.DEFAULT_VOICE

        await _rate_limiter.acquire()

        pcm_data = await self._call_gemini_tts(text, voice)
        if pcm_data is None:
            # Fallback: create silent placeholder
            return await self._create_placeholder_audio(text, output_path)

        # Write WAV then convert to MP3 for pipeline compatibility
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
        """Alias for ``synthesize`` (compat with TTSEngine interface)."""
        return await self.synthesize(text, output_path, voice, rate=rate)

    # ----- core API call -----

    async def _call_gemini_tts(
        self, text: str, voice: str
    ) -> Optional[bytes]:
        """Call Gemini TTS API, return raw PCM bytes or None on failure."""
        try:
            from google.genai import types

            client = self._get_client()

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

            # Run the synchronous SDK call in a thread to avoid blocking the
            # event loop (the google-genai SDK is not async-native).
            response = await asyncio.to_thread(
                client.models.generate_content,
                model=self.model,
                contents=text,
                config=config,
            )

            # Extract audio bytes from response
            data = (
                response.candidates[0].content.parts[0].inline_data.data
            )
            return data

        except Exception as e:
            logger.error(f"Gemini TTS API error: {e}", exc_info=True)
            return None

    # ----- helpers -----

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
        """Convert WAV to MP3 using ffmpeg."""
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
            logger.warning(f"WAV→MP3 conversion failed: {stderr.decode()[:300]}")

        # Clean up intermediary wav
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
        """Create silent audio as fallback when API call fails."""
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

    # ----- class methods for voice discovery -----

    @classmethod
    def get_available_voices(cls) -> dict:
        return cls.VOICES

    @classmethod
    def get_default_voice(cls) -> str:
        return cls.DEFAULT_VOICE
