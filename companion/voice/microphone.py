"""Push-to-talk capture using the macOS default microphone."""

from __future__ import annotations

import hashlib
import select
import subprocess
import tempfile
import wave
from pathlib import Path
from threading import Lock
from uuid import uuid4

_ROOT = Path(__file__).resolve().parents[2]
_SOURCE = Path(__file__).resolve().with_name("Microphone.swift")
_INFO = _SOURCE.with_name("Microphone-Info.plist")
_lock = Lock()
_recording: tuple[subprocess.Popen[bytes], Path] | None = None


class MicrophoneError(RuntimeError):
    """The local recorder could not capture a usable WAV."""


class MicrophonePermissionError(MicrophoneError):
    """The macOS microphone permission was denied or restricted."""


def _recorder_binary() -> Path:
    digest = hashlib.sha256(_SOURCE.read_bytes() + _INFO.read_bytes()).hexdigest()[:16]
    cache = _ROOT / ".context" / "voice-tools"
    binary = cache / f"hackathoni-microphone-{digest}"
    if binary.is_file():
        return binary

    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=cache) as staging:
        target = Path(staging) / binary.name
        try:
            subprocess.run(
                [
                    "/usr/bin/swiftc", "-parse-as-library", str(_SOURCE), "-o", str(target),
                    "-Xlinker", "-sectcreate", "-Xlinker", "__TEXT", "-Xlinker", "__info_plist",
                    "-Xlinker", str(_INFO),
                ],
                check=True, capture_output=True, text=True, timeout=60,
            )
        except subprocess.CalledProcessError as exc:
            raise MicrophoneError(f"Could not build the macOS microphone helper: {exc.stderr.strip()}") from None
        except (OSError, subprocess.TimeoutExpired):
            raise MicrophoneError("Could not run swiftc to build the macOS microphone helper") from None
        target.replace(binary)
    return binary


def record_push_to_talk() -> None:
    """Start one microphone recording. Call from a worker thread."""
    global _recording
    with _lock:
        if _recording is not None:
            raise MicrophoneError("A microphone recording is already active")
        binary = _recorder_binary()
        output = _ROOT / "runs"
        output.mkdir(parents=True, exist_ok=True)
        wav_path = output / f"voice-mic-{uuid4().hex}.wav"
        process = subprocess.Popen(
            [str(binary), str(wav_path)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        try:
            if not select.select([process.stdout], [], [], 60)[0]:
                raise MicrophoneError("Microphone startup timed out while waiting for macOS")
            if process.stdout.readline() != b"ready\n":
                _, stderr = process.communicate(timeout=5)
                detail = stderr.decode("utf-8", errors="replace").strip()
                if process.returncode == 77:
                    raise MicrophonePermissionError(detail)
                raise MicrophoneError(detail or f"Microphone helper exited with status {process.returncode}")
        except BaseException:
            if process.poll() is None:
                process.kill()
                process.communicate()
            wav_path.unlink(missing_ok=True)
            raise
        _recording = (process, wav_path)


def stop_recording() -> Path:
    """Finalize the current recording and return its repo-local WAV path."""
    global _recording
    with _lock:
        if _recording is None:
            raise MicrophoneError("There is no active microphone recording")
        process, wav_path = _recording
        _recording = None
        try:
            _, stderr = process.communicate(input=b"\n", timeout=5)
            if process.returncode:
                detail = stderr.decode("utf-8", errors="replace").strip()
                raise MicrophoneError(detail or f"Microphone helper exited with status {process.returncode}")
            with wave.open(str(wav_path), "rb") as audio:
                if (audio.getframerate(), audio.getnchannels(), audio.getsampwidth()) != (16_000, 1, 2):
                    raise MicrophoneError("The microphone WAV is not 16 kHz mono 16-bit PCM")
                if audio.getnframes() == 0:
                    raise MicrophoneError("No audio was captured. Hold the microphone button while speaking.")
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            wav_path.unlink(missing_ok=True)
            raise MicrophoneError("The microphone helper timed out while finalizing the WAV") from None
        except (wave.Error, EOFError, OSError, MicrophoneError) as exc:
            wav_path.unlink(missing_ok=True)
            if isinstance(exc, MicrophoneError):
                raise
            raise MicrophoneError("The microphone helper did not produce a readable WAV") from None
        return wav_path
