# Planner + validator (`companion/planner.py`, `companion/validator.py`)

Status: merged · scripted step list, **not AI**; shown as `planner: scripted` in UI and logs.

## Claims
- Picks the first unfinished step on the recognised screen from the live snapshot; points only at controls that exist.
- Empty question → clarify; off-topic → unsupported; unknown screen or missing control → unsupported.
- Validator rejects invented ids, stale (>2 s) or mismatched snapshots, disabled or off-window targets.

## Machine checks
| Check file | Claim | Evidence |
|---|---|---|
| `tests/test_planner_validator.py` (via `unit.py`) | all of the above | automated |

## Human checklist
- A Malayalam speaker reads every instruction in the active task and marks unnatural or wrong ones.

## Known gaps
- Intent check is a keyword regex. A Sarvam planner (stage C) is not built.
- Malayalam wording is an unreviewed draft.
