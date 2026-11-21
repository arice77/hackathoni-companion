"""Push-to-talk, transcription and spoken replies for the Companion."""

from __future__ import annotations

import re
import subprocess
import tempfile
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import Lock
from typing import Literal, get_args

from companion.contracts import Transcript

from . import sarvam
from .microphone import (
    MicrophoneError as MicrophoneError,
    MicrophonePermissionError as MicrophonePermissionError,
    record_push_to_talk as record_push_to_talk,
    stop_recording as stop_recording,
)

LanguagePreference = Literal["ml-IN", "en-IN", "hi-IN", "kn-IN"]
_PREFERENCES = get_args(LanguagePreference)
_QUOTED_LABEL = re.compile(r'''"[^"\n]+"|“[^”\n]+”|(?<!\w)'[^\n]+?'(?!\w)|‘[^\n]+?’(?!\w)''')
_MALAYALAM_SCRIPT = re.compile(r"[\u0d00-\u0d7f]")
_MALAYALAM_ROMAN_WORDS = frozenset({
    "enikku", "enikk", "enik", "kaananam", "kaanam", "kaanan", "kelkkanam", "venam", "vekku",
    "cheyyu", "cheyyanam", "pathukke", "kuraykku", "kurakku", "koottu",
})
_playback_lock = Lock()
_playback_generation = 0
_player: subprocess.Popen[bytes] | None = None


@dataclass(frozen=True)
class VoiceTranscript(Transcript):
    english_translation: Transcript | None = None

    @property
    def planner_text(self) -> str:
        return self.english_translation.text if self.english_translation is not None else self.text


class VoicePlaybackError(RuntimeError):
    """The local audio player could not play the reply."""


def _validate_preference(preference: LanguagePreference) -> None:
    if preference not in _PREFERENCES:
        raise ValueError(f"Voice preference must be one of {', '.join(_PREFERENCES)}")


def ask(
    wav_path: str | Path, preference: LanguagePreference, *, keyterms: Sequence[str] = ()
) -> VoiceTranscript:
    """Return the spoken-language transcript and its English companion when needed."""
    _validate_preference(preference)
    language = "unknown" if preference == "en-IN" else preference
    native = sarvam.transcribe(wav_path, language_code=language, keyterms=keyterms)
    source = preference if preference != "en-IN" else native.language_code
    if source not in ("hi-IN", "kn-IN", "ml-IN") and (
        _MALAYALAM_SCRIPT.search(native.text)
        or not _MALAYALAM_ROMAN_WORDS.isdisjoint(re.findall(r"\b\w+\b", native.text.casefold()))
    ):
        source = "ml-IN"
    english = None
    if source in ("hi-IN", "kn-IN", "ml-IN"):
        english = sarvam.translate_speech_to_english(wav_path, language_code=source, keyterms=keyterms)
    return VoiceTranscript(**asdict(native), english_translation=english)


def translate_instruction(text: str, preference: LanguagePreference) -> str:
    """Translate a whole sentence while keeping quoted labels byte-for-byte intact."""
    _validate_preference(preference)
    labels = {}
    number = 910001

    def mask(match):
        nonlocal number
        while str(number) in text:
            number += 1
        token = str(number)
        labels[token] = match.group()
        number += 1
        return token

    masked = _QUOTED_LABEL.sub(mask, text)
    translated = sarvam.translate_text(masked, "en-IN", preference).strip()
    if not translated:
        raise sarvam.SarvamError("Empty instruction translation")
    if labels:
        tokens = re.compile(r"(?<!\d)(?:" + "|".join(labels) + r")(?!\d)")
        if sorted(tokens.findall(translated)) != sorted(labels):
            raise sarvam.SarvamError("Instruction translation lost a quoted label")
        translated = tokens.sub(lambda match: labels[match.group()], translated)
    return translated


def _interrupt_playback_locked() -> int:
    global _playback_generation
    _playback_generation += 1
    if _player is not None and _player.poll() is None:
        _player.terminate()
    return _playback_generation


def stop_speaking() -> None:
    """Interrupt playback and invalidate synthesis already in flight."""
    with _playback_lock:
        _interrupt_playback_locked()


def speak(text: str, preference: LanguagePreference) -> sarvam.SynthesisMeta | None:
    """Synthesize and play on a worker thread. Return metadata or None if interrupted."""
    global _player
    _validate_preference(preference)
    with _playback_lock:
        generation = _interrupt_playback_locked()

    try:
        wav_bytes, meta = sarvam.synthesize(text, language_code=preference)
    except sarvam.SarvamError:
        with _playback_lock:
            if generation != _playback_generation:
                return None
        raise

    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", prefix="hackathoni-reply-") as audio:
            audio.write(wav_bytes)
            audio.flush()
            with _playback_lock:
                if generation != _playback_generation:
                    return None
                player = subprocess.Popen(
                    ["/usr/bin/afplay", audio.name],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                _player = player
            try:
                status = player.wait()
            finally:
                with _playback_lock:
                    if _player is player:
                        _player = None
            with _playback_lock:
                if generation != _playback_generation:
                    return None
            if status:
                raise VoicePlaybackError(f"afplay exited with status {status}")
    except OSError as exc:
        raise VoicePlaybackError(f"Could not play the Sarvam reply: {exc}") from None
    return meta
