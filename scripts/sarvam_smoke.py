"""Call Sarvam with a synthetic utterance or a supplied Malayalam WAV."""

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

from companion.voice import sarvam


QUESTION = "ഈ മാസത്തെ GST റിട്ടേണ്‍ എങ്ങനെ ഫയല്‍ ചെയ്യും?"
SYNTHETIC_NOTE = "TTS→STT uses synthetic audio and doesn't replace a real-microphone test."


def _normalized(text: str) -> str:
    return " ".join(unicodedata.normalize("NFC", text).casefold().split())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wav", type=Path, help="Malayalam WAV of the demo question, up to 30 s")
    args = parser.parse_args(argv)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    output = ROOT / "runs"
    wav_path = args.wav
    tts_meta = None
    try:
        if wav_path is None:
            wav_bytes, tts_meta = sarvam.synthesize(QUESTION)
            output.mkdir(parents=True, exist_ok=True)
            wav_path = output / f"sarvam-smoke-{timestamp}.wav"
            wav_path.write_bytes(wav_bytes)
            print(f"[live] TTS {tts_meta['latency_ms']:.1f} ms, request_id={tts_meta['request_id']}")
            print(f"[live] Synthetic WAV saved to {wav_path}")
            print(SYNTHETIC_NOTE)

        native = sarvam.transcribe(wav_path)
        english = sarvam.translate_speech_to_english(wav_path)
        output.mkdir(parents=True, exist_ok=True)
        similarity = SequenceMatcher(
            None, _normalized(QUESTION), _normalized(native.text), autojunk=False
        ).ratio()
        report = output / f"sarvam-smoke-{timestamp}.json"
        passed = bool(native.text.strip() and english.text.strip())
        report.write_text(json.dumps({
            "evidence": "live",
            "status": "pass" if passed else "fail",
            "audio_source": "synthetic_tts" if args.wav is None else "supplied_wav",
            "synthetic_note": SYNTHETIC_NOTE if args.wav is None else None,
            "generated_wav": wav_path.name if args.wav is None else None,
            "reference_ml": QUESTION,
            "character_similarity": similarity,
            "tts": tts_meta,
            "transcription": asdict(native),
            "speech_to_english": asdict(english),
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except sarvam.SarvamMissingKeyError as exc:
        print(exc, file=sys.stderr)
        return 2
    except (sarvam.SarvamError, OSError) as exc:
        print(f"[live] FAIL: {exc}", file=sys.stderr)
        return 1

    print(f"[live] Reference: {QUESTION}")
    print(f"[live] Malayalam STT ({native.latency_ms:.1f} ms, request_id={native.request_id}): {native.text}")
    print(f"[live] Speech→English ({english.latency_ms:.1f} ms, request_id={english.request_id}): {english.text}")
    print(f"[live] Character similarity to reference: {similarity:.1%}")
    print(f"[live] Report: {report}")
    if not passed:
        print("[live] FAIL: Sarvam returned an empty transcript", file=sys.stderr)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
