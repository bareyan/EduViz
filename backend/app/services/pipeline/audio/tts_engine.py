"""
TTS Engine - Text-to-Speech using Edge TTS (free, high quality)
"""

import asyncio
from typing import Optional

try:
    import edge_tts
except ImportError:
    edge_tts = None


class TTSEngine:
    """Text-to-Speech engine using Microsoft Edge TTS"""

    # Simplified voice selection - only the best voices for each language
    VOICES_BY_LANGUAGE = {
        "en": {
            "name": "English",
            "voices": {
                "en-GB-RyanNeural": {"name": "Ryan (UK)", "gender": "male"},
                "en-GB-SoniaNeural": {"name": "Sonia (UK)", "gender": "female"},
            },
            "default": "en-GB-RyanNeural"
        },
        "fr": {
            "name": "French",
            "voices": {
                "fr-CH-FabriceNeural": {"name": "Fabrice (Swiss)", "gender": "male"},
                "fr-FR-DeniseNeural": {"name": "Denise (France)", "gender": "female"},
            },
            "default": "fr-CH-FabriceNeural"
        },
        "ru": {
            "name": "Russian",
            "voices": {
                "ru-RU-DmitryNeural": {"name": "Dmitry (Russia)", "gender": "male"},
                "ru-RU-SvetlanaNeural": {"name": "Svetlana (Russia)", "gender": "female"},
            },
            "default": "ru-RU-DmitryNeural"
        },
        "ua": {
            "name": "Ukrainian",
            "voices": {
                "uk-UA-OstapNeural": {"name": "Ostap (Ukraine)", "gender": "male"},
                "uk-UA-PolinaNeural": {"name": "Polina (Ukraine)", "gender": "female"},
            },
            "default": "uk-UA-OstapNeural"
        },
        # Armenian - Using multilingual voices
        "hy": {
            "name": "Armenian",
            "voices": {
                "en-US-EmmaMultilingualNeural": {"name": "Emma (Multilingual)", "gender": "female"},
                "fr-FR-VivienneMultilingualNeural": {"name": "Vivienne (Multilingual)", "gender": "female"},
                "en-US-BrianMultilingualNeural": {"name": "Brian (Multilingual)", "gender": "male"},
            },
            "default": "en-US-EmmaMultilingualNeural",
            "note": "Armenian not natively supported - using multilingual voices"
        },
        # Multilingual voices - for auto language detection or any other languages
        "auto": {
            "name": "Multilingual (Auto-detect)",
            "voices": {
                "en-US-EmmaMultilingualNeural": {"name": "Emma (Multilingual)", "gender": "female"},
                "fr-FR-VivienneMultilingualNeural": {"name": "Vivienne (Multilingual)", "gender": "female"},
                "en-US-BrianMultilingualNeural": {"name": "Brian (Multilingual)", "gender": "male"},
            },
            "default": "en-US-EmmaMultilingualNeural",
            "note": "Multilingual voices that can speak multiple languages naturally"
        }
    }

    # Flat dictionary for backwards compatibility
    VOICES = {
        voice_id: info["name"]
        for lang_data in VOICES_BY_LANGUAGE.values()
        for voice_id, info in lang_data["voices"].items()
    }

    DEFAULT_VOICE = "en-GB-RyanNeural"
    DEFAULT_LANGUAGE = "en"

    @classmethod
    def get_default_voice_for_language(cls, language: str) -> str:
        """Get the default voice for a specific language"""
        lang_data = cls.VOICES_BY_LANGUAGE.get(language)
        if lang_data and "default" in lang_data:
            return lang_data["default"]
        # Fallback to multilingual for unknown languages
        return cls.VOICES_BY_LANGUAGE["auto"]["default"]

    def __init__(self):
        if not edge_tts:
            print("Warning: edge-tts not installed. TTS will use placeholder audio.")

    async def synthesize(
        self,
        text: str,
        output_path: str,
        voice: Optional[str] = None,
        rate: str = "+12%",  # 12% faster for better pacing
        pitch: str = "+0Hz"
    ) -> float:
        """
        Synthesize text to speech and save as audio file.
        Returns the duration in seconds.
        """

        if not voice:
            voice = self.DEFAULT_VOICE

        if not edge_tts:
            # Create a silent placeholder audio
            return await self._create_placeholder_audio(text, output_path)

        try:
            # Create communicate object
            communicate = edge_tts.Communicate(
                text,
                voice,
                rate=rate,
                pitch=pitch
            )

            # Save audio file
            await communicate.save(output_path)

            # Get audio duration
            duration = await self._get_audio_duration(output_path)
            return duration

        except Exception as e:
            print(f"TTS synthesis failed: {e}")
            return await self._create_placeholder_audio(text, output_path)

    async def synthesize_with_timing(
        self,
        text: str,
        output_path: str,
        voice: Optional[str] = None
    ) -> dict:
        """
        Synthesize with word-level timing for animation sync.
        Returns audio duration and word timings.
        """

        if not voice:
            voice = self.DEFAULT_VOICE

        word_timings = []

        if not edge_tts:
            duration = await self._create_placeholder_audio(text, output_path)
            return {"duration": duration, "word_timings": []}

        try:
            communicate = edge_tts.Communicate(text, voice)

            # Collect word timings from subtitle events
            with open(output_path, "wb") as audio_file:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_file.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        word_timings.append({
                            "word": chunk["text"],
                            "start": chunk["offset"] / 10000000,  # Convert to seconds
                            "duration": chunk["duration"] / 10000000
                        })

            duration = await self._get_audio_duration(output_path)
            return {"duration": duration, "word_timings": word_timings}

        except Exception as e:
            print(f"TTS with timing failed: {e}")
            duration = await self._create_placeholder_audio(text, output_path)
            return {"duration": duration, "word_timings": []}

    async def _get_audio_duration(self, audio_path: str) -> float:
        """Get the duration of an audio file using ffprobe"""

        try:
            cmd = [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                audio_path
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, _ = await process.communicate()
            return float(stdout.decode().strip())

        except Exception:
            # Estimate based on audio path name length as fallback
            return 30.0  # Default 30 seconds

    async def _create_placeholder_audio(self, text: str, output_path: str) -> float:
        """Create a silent audio file as placeholder"""

        # Estimate duration: ~150 words per minute
        word_count = len(text.split())
        duration = word_count / 2.5  # 2.5 words per second

        # Create silent audio with ffmpeg
        try:
            cmd = [
                'ffmpeg', '-y',
                '-f', 'lavfi',
                '-i', 'anullsrc=r=44100:cl=mono',
                '-t', str(duration),
                '-acodec', 'libmp3lame',
                output_path
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()

        except Exception as e:
            print(f"Failed to create placeholder audio: {e}")
            # Create empty file
            with open(output_path, 'wb'):
                pass

        return duration

    @classmethod
    def get_available_voices(cls) -> dict:
        """Get list of available voices"""
        return cls.VOICES

    @classmethod
    def get_voices_by_language(cls) -> dict:
        """Get voices organized by language"""
        return cls.VOICES_BY_LANGUAGE

    @classmethod
    def get_available_languages(cls) -> list:
        """Get list of available languages"""
        return [
            {"code": code, "name": data["name"]}
            for code, data in cls.VOICES_BY_LANGUAGE.items()
        ]

    @classmethod
    def get_voices_for_language(cls, language: str) -> list:
        """Get voices for a specific language"""
        lang_data = cls.VOICES_BY_LANGUAGE.get(language, cls.VOICES_BY_LANGUAGE["en"])
        return [
            {"id": voice_id, "name": info["name"], "gender": info["gender"]}
            for voice_id, info in lang_data["voices"].items()
        ]

    async def generate_speech(
        self,
        text: str,
        output_path: str,
        voice: Optional[str] = None,
        rate: str = "+12%"  # 12% faster for better pacing
    ) -> float:
        """
        Generate speech audio file from text.
        Alias for synthesize() for compatibility.
        
        Args:
            text: Text to synthesize
            output_path: Path to save the audio file
            voice: Voice ID to use
            rate: Speech rate adjustment (default: +12% for snappier delivery)
        """
        return await self.synthesize(text, output_path, voice, rate=rate)
