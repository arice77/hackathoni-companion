"""Check the Malayalam and English Sarvam voice paths."""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from dataclasses import asdict
from datetime import UTC, datetime
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from companion import voice
from companion.voice import sarvam


QUESTIONS = {
    "ml-IN": "ഈ ഫോം എങ്ങനെ പൂരിപ്പിക്കാം?",
    "en-IN": "How do I fill this form?",
}
SYNTHETIC_NOTE = "TTS→STT uses synthetic audio and doesn't replace a real-microphone test."


def _normalized(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).casefold().split())


def _check(
    preference: voice.LanguagePreference, output: Path, timestamp: str, wav_path: Path | None,
    audio_source: str,
) -> dict:
    question = QUESTIONS[preference]
    tts_meta = None
    if wav_path is None:
        wav_bytes, tts_meta = sarvam.synthesize(question, language_code=preference)
        wav_path = output / f"sarvam-smoke-{timestamp}-{preference}.wav"
        wav_path.write_bytes(wav_bytes)
        print(f"[live] {preference} TTS {tts_meta['latency_ms']:.1f} ms, request_id={tts_meta['request_id']}")
        print(f"[live] Synthetic WAV saved to {wav_path}")

    transcript = voice.ask(wav_path, preference)
    english = transcript.english_translation
    similarity = SequenceMatcher(
        None, _normalized(question), _normalized(transcript.text), autojunk=False
    ).ratio()
    print(f"[live] {preference} reference: {question}")
    print(f"[live] {preference} STT ({transcript.latency_ms:.1f} ms, request_id={transcript.request_id}): "
          f"{transcript.text}")
    if english is not None:
        print(f"[live] Speech→English ({english.latency_ms:.1f} ms, request_id={english.request_id}): "
              f"{english.text}")
    print(f"[live] {preference} character similarity to reference: {similarity:.1%}")
    passed = bool(transcript.text.strip() and transcript.planner_text.strip())
    if not passed:
        print(f"[live] FAIL: Sarvam returned an empty transcript for {preference}", file=sys.stderr)
    return {
        "status": "pass" if passed else "fail",
        "preference": preference,
        "audio_source": audio_source,
        "saved_wav": wav_path.name if audio_source != "supplied_wav" else None,
        "reference": question,
        "character_similarity": similarity,
        "tts": tts_meta,
        "transcription": asdict(transcript),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--wav", type=Path, help="WAV of the form question, up to 30 s")
    inputs.add_argument("--record", action="store_true", help="Record one form question from the microphone")
    parser.add_argument("--preference", choices=tuple(QUESTIONS), help="Language of a single check")
    args = parser.parse_args(argv)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    output = ROOT / "runs"
    wav_path = args.wav
    audio_source = "supplied_wav" if args.wav is not None else "synthetic_tts"
    preferences = (args.preference,) if args.preference else tuple(QUESTIONS)
    if args.wav is not None or args.record:
        preferences = (args.preference or "ml-IN",)

    try:
        # Check credentials before requesting mic access or creating any artifacts.
        sarvam._load_api_key()
        if args.record:
            if not sys.stdin.isatty():
                print("BLOCKED: --record needs an interactive terminal", file=sys.stderr)
                return 2
            input(f"Press Return to start recording, then say “{QUESTIONS[preferences[0]]}”\n")
            voice.record_push_to_talk()
            try:
                input("Recording. Press Return to stop.\n")
            finally:
                wav_path = voice.stop_recording()
            audio_source = "microphone"
        if audio_source == "synthetic_tts":
            print(SYNTHETIC_NOTE)
        output.mkdir(parents=True, exist_ok=True)
        checks = [_check(pref, output, timestamp, wav_path, audio_source) for pref in preferences]
        passed = all(check["status"] == "pass" for check in checks)
        report = output / f"sarvam-smoke-{timestamp}.json"
        report.write_text(json.dumps({
            "evidence": "live",
            "status": "pass" if passed else "fail",
            "synthetic_note": SYNTHETIC_NOTE if audio_source == "synthetic_tts" else None,
            "checks": checks,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except sarvam.SarvamMissingKeyError as exc:
        print(exc, file=sys.stderr)
        return 2
    except voice.MicrophonePermissionError as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    except (EOFError, KeyboardInterrupt):
        print("Recording check cancelled.", file=sys.stderr)
        return 1
    except (sarvam.SarvamError, voice.MicrophoneError, OSError) as exc:
        print(f"[live] FAIL: {exc}", file=sys.stderr)
        return 1

    print(f"[live] Report: {report}")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
