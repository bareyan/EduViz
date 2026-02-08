"""Audio payload parsing and decoding helpers."""

from __future__ import annotations

import base64
import wave
from pathlib import Path
from typing import Any


def extract_inline_audio_payload(response: Any) -> tuple[bytes, str | None]:
    candidates = getattr(response, "candidates", None)
    if not candidates:
        raise RuntimeError("Gemini response has no candidates")

    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) if content else None
        if not parts:
            continue
        for part in parts:
            inline_data = getattr(part, "inline_data", None)
            if not inline_data:
                continue
            mime_type = getattr(inline_data, "mime_type", None)
            data = getattr(inline_data, "data", None)
            if isinstance(data, bytes):
                return data, mime_type
            if isinstance(data, str):
                try:
                    return base64.b64decode(data), mime_type
                except Exception as exc:  # noqa: BLE001
                    raise RuntimeError("Unable to decode base64 audio payload") from exc

    raise RuntimeError("No inline audio bytes found in Gemini response")


def parse_mime(mime_type: str | None) -> tuple[str | None, dict[str, str]]:
    if not mime_type:
        return None, {}
    parts = [part.strip() for part in mime_type.split(";") if part.strip()]
    mime_base = parts[0].lower() if parts else None
    params: dict[str, str] = {}
    for part in parts[1:]:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        params[key.strip().lower()] = value.strip()
    return mime_base, params


def extension_for_mime(mime_base: str | None) -> str:
    mapping = {
        "audio/wav": "wav",
        "audio/x-wav": "wav",
        "audio/mpeg": "mp3",
        "audio/mp3": "mp3",
        "audio/ogg": "ogg",
        "audio/flac": "flac",
        "audio/aac": "aac",
        "audio/mp4": "m4a",
        "audio/webm": "webm",
    }
    return mapping.get(mime_base, "bin")


def write_pcm_l16_to_wav(audio_bytes: bytes, params: dict[str, str], out_path: Path) -> Path:
    rate = int(params.get("rate", "24000"))
    channels = int(params.get("channels", "1"))
    frame_size = 2 * max(1, channels)
    usable = len(audio_bytes) - (len(audio_bytes) % frame_size)
    pcm = audio_bytes[:usable]
    with wave.open(str(out_path), "wb") as wavf:
        wavf.setnchannels(max(1, channels))
        wavf.setsampwidth(2)
        wavf.setframerate(rate)
        wavf.writeframes(pcm)
    return out_path


def materialize_payload_file(audio_bytes: bytes, mime_type: str | None, output_dir: Path) -> Path:
    mime_base, params = parse_mime(mime_type)
    if mime_base == "audio/l16":
        return write_pcm_l16_to_wav(audio_bytes, params, output_dir / "raw_payload.wav")
    payload_path = output_dir / f"raw_payload.{extension_for_mime(mime_base)}"
    payload_path.write_bytes(audio_bytes)
    return payload_path


def require_pydub() -> tuple[Any, Any]:
    try:
        from pydub import AudioSegment, silence
    except ImportError as exc:
        raise RuntimeError(
            "Missing dependency: pydub. Install with: pip install -r requirements.txt"
        ) from exc
    return AudioSegment, silence


def decode_audio_payload(payload_path: Path, mime_type: str | None, audio_segment_cls: Any) -> tuple[Any, str]:
    try:
        return audio_segment_cls.from_file(payload_path), "container"
    except Exception as primary_exc:  # noqa: BLE001
        mime_base, _ = parse_mime(mime_type)
        if mime_base not in (None, "audio/l16", "application/octet-stream"):
            raise RuntimeError(f"Failed to decode payload: {payload_path} (mime={mime_type!r})") from primary_exc
        for rate in (24000, 22050, 16000):
            for channels in (1, 2):
                try:
                    audio = audio_segment_cls.from_raw(
                        payload_path,
                        sample_width=2,
                        frame_rate=rate,
                        channels=channels,
                    )
                    return audio, f"raw-pcm-fallback-{rate}hz-{channels}ch"
                except Exception:  # noqa: BLE001
                    continue
        raise RuntimeError(f"Failed to decode payload: {payload_path} (mime={mime_type!r})") from primary_exc
