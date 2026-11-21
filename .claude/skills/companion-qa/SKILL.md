---
name: companion-qa
description: QA the HackaThoni Companion (Malayalam voice + on-screen pointer for English business software). Use to verify a feature or branch before merge, run the regression suite, or add QA coverage when a feature lands.
---

# Companion QA

QA here produces **evidence**, not opinions. Every result carries a status and an evidence label, and the registry in `features/` grows by one file per feature so the suite keeps pace with the app.

## Evidence labels

| Label | Means | Example |
|---|---|---|
| `automated` | Pure code, no screen | unit tests |
| `live-machine` | Real macOS app + Accessibility on this Mac, no person | reader snapshot, driver-clicked e2e |
| `needs-human` | Only a person can confirm | pointer looks aligned, Malayalam reads naturally, Utter dictation arrived |
| `blocked` | Missing precondition | no `SARVAM_API_KEY`, no Accessibility trust |

A driver-clicked pass is `live-machine`, never proof that a person can follow the pointer. Mock or recorded provider calls are labelled as such in the detail.

## Run the suite

1. `./scripts/bootstrap.sh` once per worktree (pinned venv).
2. `.venv/bin/python scripts/qa/run.py` (all checks) or `run.py <word>` (checks whose file name contains the word).
3. Read `runs/qa/<timestamp>/report.md`. Done when every check is PASS, SKIP (`needs-human`) or BLOCKED with a stated reason, and every FAIL is either fixed or reported with its log path.

Live checks open the training fixtures on screen and need an Accessibility-trusted process (this Conductor shell is; `AXIsProcessTrusted()` tells you). They reset fixtures themselves via `scripts/restart_*.sh`.

## Test drivers are the only things that click

The product never clicks or types for the person. QA drivers (`scripts/drive_*.py`) may press controls **only in our own synthetic fixtures**, by bundle id, through Accessibility. Point a driver at any other app and the test is invalid.

## When a feature lands

1. Read the feature's diff and its owner's report.
2. Create or update `features/<feature>.md` from `features/_template.md`: claims, checks, the human checklist, known gaps.
3. Add `scripts/qa/checks/<feature>_<what>.py` for every claim a machine can check. Module defines `FEATURE` (the registry file name) and `run()` returning `result(...)` items from `_common.py`. Keep each check self-resetting and under ~60 s.
4. Run the whole suite, not only the new check: regressions show up in old features.
5. Report: counts, each FAIL with cause and log path, the `needs-human` checklist for the coordinator to hand to Abin, and anything you could not test.

Fix a failing check only when the fix is inside QA files (checks, drivers, registry). Product bugs go back to the coordinator with the evidence: QA reports, the builder fixes.

## Commits

Plain commit messages: no `Co-Authored-By:` trailers and no "Generated with" lines.

## Registry

`features/*.md`, one per feature, each holding status, claims, checks, human checklist and gaps. Read the ones touched by the change you are testing; `features/README.md` lists them all.
