# Sarvam voice (`companion/voice/`, `scripts/sarvam_smoke.py`)

Status: merged and wired into the panel (click-to-talk, screen labels as keyterms, spoken replies). Live synthetic round trip passed for the adapter builder on 21 Nov 2026 (docs). Real-microphone capture: blocked on macOS microphone permission. Source: `docs/sarvam-voice.md`.

## Claims
- Malayalam and English preferences: native transcript (Saaras v4), Malayalam audio → English for the planner, TTS (Bulbul v3) in the chosen language.
- Screen labels are forwarded as `keyterms` (≤50 distinct, ≤64 characters).
- Missing key → clear BLOCKED (smoke exit 2), no live report written; HTTP 402/403 surfaced with the credential redacted.
- Mic helper records 16 kHz mono WAV, capped at 29 s; `stop_speaking()` cancels playback and in-flight synthesis.

## Machine checks
| Check file | Claim | Evidence |
|---|---|---|
| `unit.py` (`tests/test_sarvam.py`, `tests/test_sarvam_voice.py`) | request shapes, error handling, keyterms, missing-key blocking, playback cancel (mocked provider) | automated (mock) |
| `voice_live_smoke.py` | one live synthetic TTS→STT run, both preferences, checks the report JSON | live-machine, provider call; **BLOCKED unless `QA_LIVE_SARVAM=1`** |

`voice_live_smoke.py` costs about 5 Sarvam calls (2 TTS, 3 speech-to-text) from the shared 600-credit pool, so it never runs by default. When enabled it checks `evidence=live`, top-level pass, both `ml-IN` and `en-IN`, nonempty native and planner transcripts, an English translation for Malayalam, and logs the character similarity. Synthetic audio only. QA's own e2e checks run the companion with `--mute` and typed questions: zero Sarvam calls.

Not run in this QA pass (credits were not authorised); that check's PASS path is untested beyond reading the smoke script's JSON schema.

## Human checklist
1. Grant microphone access when macOS asks (Terminal or Conductor, whichever launches the helper): System Settings → Privacy & Security → Microphone.
2. `.venv/bin/python scripts/sarvam_smoke.py --record --preference ml-IN`: say "ഈ ഫോം എങ്ങനെ പൂരിപ്പിക്കാം?"; the transcript must read as what you said.
3. Same with `--preference en-IN` in English.
4. In the panel, click the mic, ask in Malayalam, and confirm the "Heard" line matches. Confirm the spoken reply is in Malayalam and sounds natural; repeat in English.
5. Press Stop while the reply is playing: audio must stop immediately and stay stopped.
6. Dashboard check: note the credit balance before and after to confirm real consumption matches the call counts reported.

## Known gaps
- Synthetic TTS→STT is not a microphone test, and its high similarity says nothing about accents, noise or shop-floor speech.
- No test of 429 rate limiting (60 req/min), long audio over 30 s, or offline behaviour in the live path.
- Malayalam wording and voice quality need a native speaker.
