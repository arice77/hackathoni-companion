"""English panel + Malayalam speech (live Sarvam, 3 calls, synthetic audio, no screen, no Safari).

Abin's hand test (22 Nov): with the panel in English and Malayalam spoken, STT produced Manglish and the planner got no usable
text. Since 293d3e0 English mode transcribes with language_code=unknown and, when Malayalam is detected, also asks Sarvam to
translate to English. Calls: 1 Bulbul (ml-IN) to make the audio, 1 speech-to-text (unknown), 1 speech translate.
BLOCKED unless QA_LIVE_SARVAM=1. Synthetic audio is not a microphone test (a person speaking is still a human check).
"""
import os
import re
import tempfile
from pathlib import Path

from _common import ROOT, result
import _follow

FEATURE = "voice-sarvam"
CHECK = "English panel + Malayalam speech: translation reaches the planner (3 Sarvam calls, synthetic audio)"
SENTENCE = "എനിക്ക് ഈ വീഡിയോ സ്ലോ ആക്കണം"
MALAYALAM = re.compile(r"[ഀ-ൿ]")


def run():
    if os.environ.get("QA_LIVE_SARVAM") != "1":
        return [result(FEATURE, CHECK, "blocked", "blocked", "set QA_LIVE_SARVAM=1 (3 Sarvam calls: Malayalam TTS, speech-to-text, speech translate)")]
    if not _follow.key_available():
        return [result(FEATURE, CHECK, "blocked", "blocked", "no SARVAM_API_KEY in env or .env")]
    from companion import voice
    from companion.voice import sarvam
    problems, info = [], []
    with tempfile.TemporaryDirectory(prefix="qa-voice-") as tmp:
        wav = Path(tmp) / "ml.wav"
        try:
            audio, meta = sarvam.synthesize(SENTENCE, language_code="ml-IN")
            wav.write_bytes(audio)
            heard = voice.ask(wav, "en-IN", keyterms=["Settings", "Playback speed", "Search"])
        except Exception as exc:  # noqa: BLE001 - provider or network failure is a finding, not a crash
            return [result(FEATURE, CHECK, "fail", "live-machine", f"{type(exc).__name__}: {str(exc)[:200]}")]
    native, english = heard.text, heard.english_translation
    info.append(f"STT language {heard.language_code!r}, {'Malayalam script' if MALAYALAM.search(native) else 'romanized/Latin'} transcript")
    if english is None:
        problems.append("Malayalam was spoken in English mode but no English translation was requested")
    else:
        text = english.text.strip()
        letters = [c for c in text if c.isalpha()]
        if not text or len(letters) < 4 or sum(c.isascii() for c in letters) / len(letters) < 0.9:
            problems.append(f"the planner text is not English: {text[:60]!r}")
        if not re.search(r"video|slow|speed|down", text, re.IGNORECASE):
            problems.append(f"the planner text lost the request: {text[:60]!r}")
        info.append(f"planner text: {text[:80]!r}")
    if not heard.planner_text.strip():
        problems.append("empty planner text")
    return [result(FEATURE, CHECK, "fail" if problems else "pass", "live-machine",
                   "; ".join(problems + info) if problems else "; ".join(info) + "; synthetic Malayalam audio, label live (provider) / not a microphone test")]
