"""Push-to-talk, transcription and spoken replies for the Companion."""

from __future__ import annotations

import subprocess
import tempfile
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from threading import Lock
from typing import Literal

from companion.contracts import Transcript

from . import sarvam
from .microphone import (
    MicrophoneError as MicrophoneError,
    MicrophonePermissionError as MicrophonePermissionError,
    record_push_to_talk as record_push_to_talk,
    stop_recording as stop_recording,
)

LanguagePreference = Literal["ml-IN", "en-IN"]
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
    if preference not in ("ml-IN", "en-IN"):
        raise ValueError("Voice preference must be ml-IN or en-IN")


def ask(
    wav_path: str | Path, preference: LanguagePreference, *, keyterms: Sequence[str] = ()
) -> VoiceTranscript:
    """Return the preferred-language transcript and its English companion when needed."""
    _validate_preference(preference)
    native = sarvam.transcribe(wav_path, language_code=preference, keyterms=keyterms)
    english = sarvam.translate_speech_to_english(wav_path, keyterms=keyterms) if preference == "ml-IN" else None
    return VoiceTranscript(**asdict(native), english_translation=english)


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
