# Companion loop (`companion/app.py`)

Status: merged · Last QA: runs/qa/20261121-194814 (pass ×3 consecutive, driver-clicked)

## Claims
- Question (typed, Utter-dictated or `--question`) → snapshot → decision → validation → pointer, re-checked every 0.5 s.
- Pointer moves to the next step only after the screen shows the previous one done.
- Finish is verified by on-screen status text plus a fresh receipt file from the fixture.
- Stop hides the pointer. Every decision is logged to `runs/session-*.jsonl` with observe/plan/draw ms.

## Machine checks
| Check file | Claim | Evidence |
|---|---|---|
| `aims_e2e.py` | full step sequence, validation, completion, latency | live-machine |

## Human checklist
1. `./scripts/restart_training.sh`, then `.venv/bin/python -m companion.app` from a Conductor terminal.
2. Type or dictate with Utter: "എന്റെ നെല്ല് നശിച്ചു, ക്ലെയിം എങ്ങനെ?" → the panel shows exactly what was heard (Utter check).
3. Highlight sits on Classification. Click it yourself; the highlight moves on.
4. Finish all screens by following only the pointer. Panel ends with "Verified: status text seen + fresh training receipt file".
5. Click Stop mid-task: highlight disappears.

## Known gaps
- QA find 21 Nov: a half-drawn new screen read as "unsupported" and stopped the task. Fixed: mid-task unsupported must persist 3 ticks (`SETTLE_TICKS`).
- No person has run steps 1–5 yet. Utter dictation unverified. The pointer is the plain fallback until the sketch overlay merges.
