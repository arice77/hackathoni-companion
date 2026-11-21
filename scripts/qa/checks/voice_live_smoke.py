"""Live Sarvam smoke: TTS -> STT round trip, both language preferences (5 provider calls, spends credits).

BLOCKED unless QA_LIVE_SARVAM=1 is set. Synthetic audio only; it does not replace a real-microphone test.
Offline coverage of the voice code is in tests/test_sarvam*.py, run by unit.py.
"""
import json
import os
import re

from _common import PY, ROOT, result, sh

FEATURE = "voice-sarvam"
CHECK = "live Sarvam smoke (synthetic TTS->STT, ml-IN + en-IN)"
CALLS = 5  # per docs/sarvam-voice.md: 2 TTS + 3 speech-to-text (ml native, ml->English, en native)


def run():
    if os.environ.get("QA_LIVE_SARVAM") != "1":
        return [result(FEATURE, CHECK, "blocked", "blocked",
                       f"set QA_LIVE_SARVAM=1 to run; spends about {CALLS} Sarvam API calls from the shared credit pool")]
    p = sh(PY, "scripts/sarvam_smoke.py", "--keyterm", "Save Draft", "--keyterm", "Next", timeout=180)
    if p.returncode == 2:
        return [result(FEATURE, CHECK, "blocked", "blocked", (p.stderr or p.stdout).strip()[-300:])]
    m = re.search(r"\[live\] Report: (\S+)", p.stdout)
    if p.returncode != 0 or not m:
        return [result(FEATURE, CHECK, "fail", "live-machine",
                       f"rc={p.returncode} stderr: {p.stderr.strip()[-300:]} stdout tail: {p.stdout.strip()[-200:]}")]
    path = ROOT / m.group(1) if not m.group(1).startswith("/") else m.group(1)
    try:
        report = json.loads(open(path).read())
    except (OSError, ValueError) as exc:
        return [result(FEATURE, CHECK, "fail", "live-machine", f"report {path} unreadable: {exc}")]
    checks = report.get("checks", [])
    prefs = sorted(c.get("preference") for c in checks)
    problems = []
    if report.get("evidence") != "live" or report.get("status") != "pass":
        problems.append(f"top-level evidence={report.get('evidence')} status={report.get('status')}")
    if prefs != ["en-IN", "ml-IN"]:
        problems.append(f"preferences {prefs}")
    for c in checks:
        t = c.get("transcription", {})
        # planner_text is a property on VoiceTranscript, so asdict() omits it: derive it as the adapter does
        planner = (t.get("english_translation") or {}).get("text") or t.get("text", "")
        if c.get("status") != "pass" or not t.get("text", "").strip() or not planner.strip():
            problems.append(f"{c.get('preference')}: status={c.get('status')} empty transcript")
        if c.get("audio_source") != "synthetic_tts":
            problems.append(f"{c.get('preference')}: audio_source={c.get('audio_source')}")
    ml = next((c for c in checks if c.get("preference") == "ml-IN"), {})
    if not ml.get("transcription", {}).get("english_translation"):
        problems.append("ml-IN: no English translation returned")
    sims = {c.get("preference"): round(c.get("character_similarity", 0), 2) for c in checks}
    detail = f"similarity {sims}; report {path}; synthetic audio, label live (provider) / not a microphone test"
    return [result(FEATURE, CHECK, "fail" if problems else "pass", "live-machine",
                   f"{'; '.join(problems)}; {detail}" if problems else detail)]
