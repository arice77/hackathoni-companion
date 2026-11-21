# Accessibility reader (`companion/reader.py`)

Status: merged · Last QA: runs/qa/20261121-194316 (pass)

## Claims
- Reads the target app's focused window: role, label, AXIdentifier, frame (top-left screen points), enabled, filled.
- Inputs report only `filled`; typed or prefilled values never appear in labels.
- Portal-style placeholders ("---Select My Service---", "Select", "Choose…") count as not filled.
- Snapshot in well under 250 ms.

## Machine checks
| Check file | Claim | Evidence |
|---|---|---|
| `aims_reader_live.py` | controls found, values withheld, positive rects | live-machine |
| `tests/test_reader_pure.py` (via `unit.py`) | placeholder detection | automated |
| `aims_e2e.py` observe latency | speed | live-machine |

## Human checklist
None; this feature has no visible output.

## Known gaps
- Web pages in browsers are untested (Chromium may need accessibility enabled).
- Moving windows, scrolling, multiple displays untested.
- Bug found by QA 21 Nov: "---Select…---" read as filled. Fixed and covered.
