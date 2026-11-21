"""Synchronous Sarvam REST adapter for short voice turns."""

from __future__ import annotations

import base64
import json
import os
import time
from collections.abc import Sequence
from http.client import HTTPException
from pathlib import Path
from typing import TypedDict
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4

from companion.contracts import Transcript

_ROOT = Path(__file__).resolve().parents[2]
_BASE_URL = "https://api.sarvam.ai"
_TIMEOUT_SECONDS = 30
_KEY_NAME = "SARVAM_API_KEY"
_MALAYALAM = "ml-IN"
_ENGLISH = "en-IN"
_SPEECH_MODEL = "saaras:v4"
_TRANSLATE_MODEL = "sarvam-translate:v1"
_TTS_MODEL = "bulbul:v3"
_DEFAULT_SPEAKER = "shubh"
_SAMPLE_RATE = 16_000


class SarvamError(RuntimeError):
    """A Sarvam call could not be completed."""


class SarvamMissingKeyError(SarvamError):
    """No key was configured for this workspace."""


class SarvamHTTPError(SarvamError):
    def __init__(self, endpoint: str, status: int, body: str) -> None:
        self.status = status
        self.body = body
        super().__init__(f"Sarvam {endpoint} HTTP {status}: {body}")


class SarvamTimeoutError(SarvamError):
    """Sarvam did not respond within the HTTP socket timeout."""


class SynthesisMeta(TypedDict):
    model: str
    language_code: str
    speaker: str
    request_id: str
    latency_ms: float


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Keep the authenticated request on the configured Sarvam endpoint.
        return None


_OPENER = build_opener(_NoRedirect())


def _load_api_key() -> str:
    key = os.environ.get(_KEY_NAME, "").strip()
    if not key:
        try:
            lines = (_ROOT / ".env").read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            lines = []
        except (OSError, UnicodeError):
            raise SarvamError("Could not read the repo-root .env as UTF-8") from None
        for line in lines:
            name, sep, value = line.strip().removeprefix("export ").partition("=")
            if sep and name.strip() == _KEY_NAME:
                key = value.strip()
                if len(key) >= 2 and key[0] in ("'", '"') and key[-1] == key[0]:
                    key = key[1:-1].strip()
    if not key:
        raise SarvamMissingKeyError("BLOCKED: no SARVAM_API_KEY")
    if not key.isascii() or not key.isprintable():
        raise SarvamError("SARVAM_API_KEY contains invalid header characters")
    return key


def _redact(text: str, key: str) -> str:
    escaped = json.dumps(key)[1:-1]
    return text.replace(escaped, "[redacted]").replace(key, "[redacted]")


def _post(endpoint: str, key: str, body: bytes, content_type: str) -> tuple[dict, float]:
    request = Request(
        _BASE_URL + endpoint,
        data=body,
        method="POST",
        headers={
            "api-subscription-key": key,
            "Content-Type": content_type,
            "Accept": "application/json",
        },
    )
    started = time.perf_counter()
    try:
        with _OPENER.open(request, timeout=_TIMEOUT_SECONDS) as response:
            raw = response.read()
    except HTTPError as exc:
        try:
            with exc:
                detail = exc.read().decode("utf-8", errors="replace")
        except (OSError, HTTPException):
            detail = "error body unavailable"
        raise SarvamHTTPError(endpoint, exc.code, _redact(detail, key)) from None
    except (TimeoutError, URLError) as exc:
        reason = exc.reason if isinstance(exc, URLError) else exc
        if isinstance(reason, TimeoutError):
            raise SarvamTimeoutError(f"Sarvam {endpoint} timed out") from None
        raise SarvamError(f"Sarvam {endpoint} connection failed: {_redact(str(reason), key)}") from None
    except (OSError, HTTPException) as exc:
        raise SarvamError(f"Sarvam {endpoint} transport failed: {_redact(str(exc), key)}") from None
    elapsed_ms = (time.perf_counter() - started) * 1000

    try:
        data = json.loads(raw)
    except ValueError:
        raise SarvamError(f"Sarvam {endpoint} returned invalid JSON") from None
    if not isinstance(data, dict):
        raise SarvamError(f"Sarvam {endpoint} returned an unexpected JSON response")
    for name in ("transcript", "translated_text", "transliterated_text", "request_id", "language_code"):
        if isinstance(data.get(name), str):
            data[name] = data[name].replace(key, "[redacted]")
    return data, elapsed_ms


def _post_json(endpoint: str, fields: dict) -> tuple[dict, float]:
    key = _load_api_key()
    body = json.dumps(fields, ensure_ascii=False).encode("utf-8")
    return _post(endpoint, key, body, "application/json")


def _text_field(data: dict, name: str) -> str:
    value = data.get(name)
    if not isinstance(value, str):
        raise SarvamError(f"Sarvam response is missing a string {name} field")
    return value


def _speech(
    wav_path: str | Path, language_code: str, mode: str, keyterms: Sequence[str]
) -> Transcript:
    key = _load_api_key()
    fields = {"model": _SPEECH_MODEL, "mode": mode, "language_code": language_code}
    if isinstance(keyterms, str) or any(
        not isinstance(term, str) or not term.strip() or len(term) > 64 for term in keyterms
    ):
        raise ValueError("keyterms must be a sequence of nonempty strings up to 64 characters each")
    terms = list(dict.fromkeys(keyterms))
    if len(terms) > 50:
        raise ValueError("keyterms supports at most 50 distinct terms")
    if terms:
        fields["keyterms"] = json.dumps(terms, ensure_ascii=False)

    with Path(wav_path).open("rb") as audio:
        header = audio.read(12)
        if not (header.startswith(b"RIFF") and header[8:12] == b"WAVE"):
            raise SarvamError("Speech input must be a WAV file")
        wav_bytes = header + audio.read()

    boundary = uuid4().hex
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode()
        for name, value in fields.items()
    ]
    parts.extend([
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="speech.wav"\r\n'
        'Content-Type: audio/wav\r\n\r\n'.encode(),
        wav_bytes,
        f"\r\n--{boundary}--\r\n".encode(),
    ])
    data, latency = _post(
        "/speech-to-text", key, b"".join(parts), f"multipart/form-data; boundary={boundary}"
    )
    return Transcript(
        text=_text_field(data, "transcript"),
        # Sarvam's language_code describes the input even in translate mode.
        language_code=_ENGLISH if mode == "translate" else data.get("language_code") or language_code,
        provider="sarvam",
        model=_SPEECH_MODEL,
        request_id=data.get("request_id") or "",
        latency_ms=latency,
    )


def transcribe(
    wav_path: str | Path, language_code: str = _MALAYALAM, *, keyterms: Sequence[str] = ()
) -> Transcript:
    """Transcribe a short WAV in the spoken language."""
    return _speech(wav_path, language_code, "transcribe", keyterms)


def translate_speech_to_english(
    wav_path: str | Path, *, keyterms: Sequence[str] = ()
) -> Transcript:
    """Translate a short Malayalam WAV directly to English."""
    return _speech(wav_path, _MALAYALAM, "translate", keyterms)


def translate_text(text: str, source: str, target: str) -> str:
    """Translate text between explicit Sarvam language codes."""
    data, _ = _post_json("/translate", {
        "input": text,
        "source_language_code": source,
        "target_language_code": target,
        "model": _TRANSLATE_MODEL,
    })
    return _text_field(data, "translated_text")


def transliterate_text(text: str, source: str, target: str) -> str:
    """Transliterate text without translating its meaning."""
    data, _ = _post_json("/transliterate", {
        "input": text,
        "source_language_code": source,
        "target_language_code": target,
    })
    return _text_field(data, "transliterated_text")


def synthesize(
    text: str, language_code: str = _MALAYALAM, speaker: str | None = None
) -> tuple[bytes, SynthesisMeta]:
    """Return a 16 kHz WAV and metadata for a single Bulbul utterance."""
    speaker = _DEFAULT_SPEAKER if speaker is None else speaker
    data, latency = _post_json("/text-to-speech", {
        "text": text,
        "language_code": language_code,
        "speaker": speaker,
        "model": _TTS_MODEL,
        "output_audio_codec": "wav",
        "speech_sample_rate": _SAMPLE_RATE,
    })
    audios = data.get("audios")
    if not isinstance(audios, list) or len(audios) != 1 or not isinstance(audios[0], str):
        raise SarvamError("Sarvam /text-to-speech did not return one audio clip")
    try:
        wav_bytes = base64.b64decode(audios[0], validate=True)
    except ValueError:
        raise SarvamError("Sarvam /text-to-speech returned invalid base64 audio") from None
    if not (wav_bytes.startswith(b"RIFF") and wav_bytes[8:12] == b"WAVE"):
        raise SarvamError("Sarvam /text-to-speech did not return WAV audio")
    return wav_bytes, {
        "model": _TTS_MODEL,
        "language_code": language_code,
        "speaker": speaker,
        "request_id": data.get("request_id") or "",
        "latency_ms": latency,
    }
