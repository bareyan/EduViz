import asyncio
import os
import sys
from pathlib import Path

# Add backend to sys.path to import app modules
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.core.voice_catalog import TTS_VOICES_BY_LANGUAGE, GEMINI_TTS_VOICES
from app.services.pipeline.audio.tts_engine import TTSEngine
from app.services.pipeline.audio.gemini.engine import GeminiTTSEngine

STATIC_DIR = Path('backend/static/voice_previews')

async def generate_previews():
    STATIC_DIR.mkdir(parents=True, exist_ok=True)
    
    edge_engine = TTSEngine()
    gemini_engine = GeminiTTSEngine()
    
    # Process Edge TTS voices
    print("Generating Edge TTS previews...")
    for lang_code, lang_data in TTS_VOICES_BY_LANGUAGE.items():
        if lang_code == "auto":
            continue
            
        for voice_id, voice_info in lang_data["voices"].items():
            output_path = STATIC_DIR / f"{voice_id}.mp3"
            if output_path.exists():
                print(f"  Skipping {voice_id} (already exists)")
                continue
                
            text = f"Hello! This is a preview of the {voice_info['name']} voice."
            print(f"  Generating {voice_id}...")
            try:
                await edge_engine.synthesize(text, str(output_path), voice=voice_id)
            except Exception as e:
                print(f"  Failed to generate {voice_id}: {e}")

    # Process Gemini TTS voices
    print("\nGenerating Gemini TTS previews...")
    # Gemini voices are multilingual, so we just iterate through them once
    # We can use the English catalog as a base
    en_gemini = GEMINI_TTS_VOICES.get("en", {})
    for voice_id, voice_info in en_gemini.get("voices", {}).items():
        output_path = STATIC_DIR / f"{voice_id}.mp3"
        if output_path.exists():
            print(f"  Skipping {voice_id} (already exists)")
            continue
            
        text = f"Hello! This is a preview of the {voice_info['name']} voice."
        print(f"  Generating {voice_id}...")
        try:
            # Note: Gemini requires GEMINI_API_KEY
            await gemini_engine.synthesize(text, str(output_path), voice=voice_id)
        except Exception as e:
            print(f"  Failed to generate {voice_id}: {e}")

if __name__ == "__main__":
    asyncio.run(generate_previews())
