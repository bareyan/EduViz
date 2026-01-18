"""
TTS Engine - Text-to-Speech using Edge TTS (free, high quality)
"""

import asyncio
import os
from typing import Optional

try:
    import edge_tts
except ImportError:
    edge_tts = None


class TTSEngine:
    """Text-to-Speech engine using Microsoft Edge TTS"""
    
    # Available voices for math/educational content
    VOICES = {
        "en-US-GuyNeural": "Guy (US Male)",
        "en-US-JennyNeural": "Jenny (US Female)",
        "en-GB-RyanNeural": "Ryan (UK Male)",
        "en-GB-SoniaNeural": "Sonia (UK Female)",
        "en-AU-WilliamNeural": "William (AU Male)",
        "en-AU-NatashaNeural": "Natasha (AU Female)",
        "en-IN-PrabhatNeural": "Prabhat (India Male)",
        "en-IN-NeerjaNeural": "Neerja (India Female)",
    }
    
    DEFAULT_VOICE = "en-US-GuyNeural"
    
    def __init__(self):
        if not edge_tts:
            print("Warning: edge-tts not installed. TTS will use placeholder audio.")
    
    async def synthesize(
        self,
        text: str,
        output_path: str,
        voice: Optional[str] = None,
        rate: str = "+0%",
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
                '-i', f'anullsrc=r=44100:cl=mono',
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
            with open(output_path, 'wb') as f:
                pass
        
        return duration
    
    @classmethod
    def get_available_voices(cls) -> dict:
        """Get list of available voices"""
        return cls.VOICES
    
    async def generate_speech(
        self,
        text: str,
        output_path: str,
        voice: Optional[str] = None
    ) -> float:
        """
        Generate speech audio file from text.
        Alias for synthesize() for compatibility.
        """
        return await self.synthesize(text, output_path, voice)
