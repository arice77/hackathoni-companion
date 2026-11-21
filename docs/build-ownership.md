# Overnight build: who owns which files

Coordinator (main workspace) owns the integration and everything not listed below:
`companion/contracts.py`, `companion/reader.py`, `companion/planner*.py`, `companion/validator.py`,
`companion/observer.py`, `companion/app.py`, `apps/aims-training/`, `HANDOFF.md`, `README.md`,
`building companion app.md`.

| Agent | Writes only | Must not touch |
| --- | --- | --- |
| Workflow reviewer (read-only) | `.context/workflow-review.md` | Everything else |
| Overlay | `companion/overlay/**`, `tests/test_overlay*.py`, `docs/overlay-verification.md` | Contracts, reader, planner, app, fixture |
| Sarvam voice | `companion/voice/**`, `scripts/sarvam_smoke.py`, `tests/test_sarvam*.py`, `docs/sarvam-voice.md` | Contracts, overlay, app; never commit keys or audio of real people |

Shared rules: Python 3.13 venv via `scripts/bootstrap.sh` (pinned PyObjC 13.0 only; ask before adding
dependencies). Rects are top-left global screen points (see `companion/contracts.py`). Label every result as
live, recorded, mock or unverified. No automatic clicks. Synthetic records only.
