# Feature registry

| Feature | Status | File |
|---|---|---|
| Accessibility reader | merged | [reader.md](reader.md) |
| Planner + validator | merged (scripted, not AI) | [planner.md](planner.md) |
| Companion loop (panel, re-check, completion) | merged | [companion-loop.md](companion-loop.md) |
| AIMS crop-insurance training fixture | prototype, kept for reference | [aims-fixture.md](aims-fixture.md) |
| GST return practice fixture | planned (hero demo) | [gst-fixture.md](gst-fixture.md) |
| Sketch overlay (Plum) | merged | [overlay.md](overlay.md) |
| Sarvam voice (Malayalam STT/TTS/translate) | merged; live check opt-in (`QA_LIVE_SARVAM=1`) | [voice-sarvam.md](voice-sarvam.md) |
| Web support (Safari practice form + browser reader) | merged | [web-support.md](web-support.md) |
| Utter dictation input | untested | [companion-loop.md](companion-loop.md) |

## Running live checks on a shared Mac
`scripts/qa/run.py` holds an exclusive `flock` on `/tmp/hackathoni-companion-qa.lock` for the whole run (unless only `unit` is selected), so live checks from different worktrees take turns. It prints `waiting for another QA run (holder: ...)` and, after 10 minutes (`QA_LOCK_TIMEOUT_S` to change), records BLOCKED and exits 2. Only runs started through `run.py` honour the lock: a worktree whose `run.py` predates it, or a hand-run `restart_training.sh`, can still collide. All worktrees share the AIMS fixture bundle id, and Safari practice windows are matched by port (`CONDUCTOR_PORT`).
