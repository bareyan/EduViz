from app.core.voice_catalog import (
    get_translation_default_voice,
    get_translation_languages,
    get_tts_available_languages,
    get_tts_default_voice_for_language,
    get_tts_voices_for_language,
)


def test_tts_default_voice_known_and_unknown():
    assert get_tts_default_voice_for_language("en") == "en-GB-RyanNeural"
    assert "Multilingual" in get_tts_default_voice_for_language("klingon")


def test_tts_voices_for_language_shape():
    voices = get_tts_voices_for_language("en")
    assert len(voices) >= 1
    assert {"id", "name", "gender"}.issubset(voices[0].keys())


def test_tts_available_languages_contains_auto():
    languages = get_tts_available_languages()
    assert any(item["code"] == "auto" for item in languages)


def test_translation_catalog_basics():
    languages = get_translation_languages()
    assert any(item["code"] == "en" for item in languages)
    assert get_translation_default_voice("fr") == "fr-FR-HenriNeural"
    assert get_translation_default_voice("unknown-lang") == "en-US-GuyNeural"
