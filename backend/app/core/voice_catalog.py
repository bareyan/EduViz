"""
Central voice/language catalog for TTS and translation.

This module is the single source of truth for:
- Interactive TTS language -> voices (used by /voices and generation UI)
- Translation target language -> default narration voice
"""

from __future__ import annotations

from typing import Any, Dict, List

from .constants import get_language_name

# Interactive TTS catalog (used by /voices and generation flow)
TTS_VOICES_BY_LANGUAGE: Dict[str, Dict[str, Any]] = {
    "en": {
        "name": "English",
        "voices": {
            "en-GB-RyanNeural": {"name": "Ryan (UK)", "gender": "male"},
            "en-GB-SoniaNeural": {"name": "Sonia (UK)", "gender": "female"},
        },
        "default": "en-GB-RyanNeural",
    },
    "fr": {
        "name": "French",
        "voices": {
            "fr-CH-FabriceNeural": {"name": "Fabrice (Swiss)", "gender": "male"},
            "fr-FR-DeniseNeural": {"name": "Denise (France)", "gender": "female"},
        },
        "default": "fr-CH-FabriceNeural",
    },
    "ru": {
        "name": "Russian",
        "voices": {
            "ru-RU-DmitryNeural": {"name": "Dmitry (Russia)", "gender": "male"},
            "ru-RU-SvetlanaNeural": {"name": "Svetlana (Russia)", "gender": "female"},
        },
        "default": "ru-RU-DmitryNeural",
    },
    "ua": {
        "name": "Ukrainian",
        "voices": {
            "uk-UA-OstapNeural": {"name": "Ostap (Ukraine)", "gender": "male"},
            "uk-UA-PolinaNeural": {"name": "Polina (Ukraine)", "gender": "female"},
        },
        "default": "uk-UA-OstapNeural",
    },
    "hy": {
        "name": "Armenian",
        "voices": {
            "en-US-EmmaMultilingualNeural": {"name": "Emma (Multilingual)", "gender": "female"},
            "fr-FR-VivienneMultilingualNeural": {"name": "Vivienne (Multilingual)", "gender": "female"},
            "en-US-BrianMultilingualNeural": {"name": "Brian (Multilingual)", "gender": "male"},
        },
        "default": "en-US-EmmaMultilingualNeural",
        "note": "Armenian not natively supported - using multilingual voices",
    },
    "auto": {
        "name": "Multilingual (Auto-detect)",
        "voices": {
            "en-US-EmmaMultilingualNeural": {"name": "Emma (Multilingual)", "gender": "female"},
            "fr-FR-VivienneMultilingualNeural": {"name": "Vivienne (Multilingual)", "gender": "female"},
            "en-US-BrianMultilingualNeural": {"name": "Brian (Multilingual)", "gender": "male"},
        },
        "default": "en-US-EmmaMultilingualNeural",
        "note": "Multilingual voices that can speak multiple languages naturally",
    },
}

DEFAULT_TTS_LANGUAGE = "en"
DEFAULT_TRANSLATION_VOICE = "en-US-GuyNeural"

# ---------------------------------------------------------------------------
# Gemini TTS voice catalog (used when TTS_ENGINE=gemini)
# ---------------------------------------------------------------------------
GEMINI_TTS_VOICES: Dict[str, Dict[str, Any]] = {
    "en": {
        "name": "English",
        "voices": {
            "Charon": {"name": "Charon (Informative)", "gender": "neutral"},
            "Kore": {"name": "Kore (Firm)", "gender": "neutral"},
            "Puck": {"name": "Puck (Upbeat)", "gender": "neutral"},
            "Zephyr": {"name": "Zephyr (Bright)", "gender": "neutral"},
            "Fenrir": {"name": "Fenrir (Excitable)", "gender": "neutral"},
            "Aoede": {"name": "Aoede (Breezy)", "gender": "neutral"},
            "Sulafat": {"name": "Sulafat (Warm)", "gender": "neutral"},
        },
        "default": "Charon",
    },
}

DEFAULT_GEMINI_TTS_VOICE = "Charon"


def get_gemini_tts_default_voice(language: str = "en") -> str:
    """Get default Gemini TTS voice for a language (Gemini voices are multilingual)."""
    lang_data = GEMINI_TTS_VOICES.get(language, GEMINI_TTS_VOICES.get("en"))
    if lang_data and "default" in lang_data:
        return lang_data["default"]
    return DEFAULT_GEMINI_TTS_VOICE


def get_gemini_tts_voices() -> Dict[str, str]:
    """Return flat Gemini voice_name -> description map."""
    return {
        voice_id: info["name"]
        for lang_data in GEMINI_TTS_VOICES.values()
        for voice_id, info in lang_data["voices"].items()
    }

# Translation defaults by target language.
TRANSLATION_DEFAULT_VOICE_BY_LANGUAGE: Dict[str, str] = {
    "en": "en-US-GuyNeural",
    "fr": "fr-FR-HenriNeural",
    "es": "es-ES-AlvaroNeural",
    "de": "de-DE-ConradNeural",
    "it": "it-IT-DiegoNeural",
    "pt": "pt-BR-AntonioNeural",
    "zh": "zh-CN-YunxiNeural",
    "ja": "ja-JP-KeitaNeural",
    "ko": "ko-KR-InJoonNeural",
    "ar": "ar-SA-HamedNeural",
    "ru": "ru-RU-DmitryNeural",
    "hy": "hy-AM-HaykNeural",
    "hi": "hi-IN-MadhurNeural",
    "tr": "tr-TR-AhmetNeural",
    "pl": "pl-PL-MarekNeural",
    "nl": "nl-NL-MaartenNeural",
    "ua": "uk-UA-OstapNeural",
}


def get_tts_default_voice_for_language(language: str) -> str:
    """Get interactive TTS default voice for language; fall back to multilingual."""
    lang_data = TTS_VOICES_BY_LANGUAGE.get(language)
    if lang_data and "default" in lang_data:
        return lang_data["default"]
    return TTS_VOICES_BY_LANGUAGE["auto"]["default"]


def get_tts_available_voices_flat() -> Dict[str, str]:
    """Return flattened voice_id -> display_name map."""
    return {
        voice_id: info["name"]
        for lang_data in TTS_VOICES_BY_LANGUAGE.values()
        for voice_id, info in lang_data["voices"].items()
    }


def get_tts_available_languages() -> List[Dict[str, str]]:
    """Return interactive TTS language list."""
    return [
        {"code": code, "name": data["name"]}
        for code, data in TTS_VOICES_BY_LANGUAGE.items()
    ]


def get_tts_voices_for_language(language: str) -> List[Dict[str, str]]:
    """Return voice options for a language (falls back to English)."""
    lang_data = TTS_VOICES_BY_LANGUAGE.get(language, TTS_VOICES_BY_LANGUAGE["en"])
    return [
        {"id": voice_id, "name": info["name"], "gender": info["gender"]}
        for voice_id, info in lang_data["voices"].items()
    ]


def get_translation_default_voice(language: str) -> str:
    """Get default voice for a translation target language."""
    return TRANSLATION_DEFAULT_VOICE_BY_LANGUAGE.get(language, DEFAULT_TRANSLATION_VOICE)


def get_translation_languages() -> List[Dict[str, str]]:
    """Return supported translation target languages."""
    return [
        {"code": code, "name": get_language_name(code)}
        for code in sorted(TRANSLATION_DEFAULT_VOICE_BY_LANGUAGE.keys())
    ]
