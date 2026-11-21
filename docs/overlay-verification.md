# Native sketch pointer verification

Verified 21 November 2026 on the build Mac with Python 3.13, PyObjC 13.0 and one 1470 × 956 pt display at 2×. The PNGs contain only the pointer view and synthetic instructions. The live alignment test uses a separate one-button fixture. Integration QA uses the repository's AIMS practice app.

| Evidence | Check | Result |
| --- | --- | --- |
| automated | `.venv/bin/python -m unittest` | 24 passed, 0 failed. Six overlay tests cover fractional coordinates, displays above and left, a target across a display boundary, edge placement, horizontal placement beside tall targets, and the actual mixed-script font runs. |
| automated | Core Text shaping | The English run used the process-registered Shantell Sans at INFM 35, BNCE 16 and wght 500. Malayalam used Malayalam Sangam MN. All glyph IDs in the mixed “Prepare Online” instruction were nonzero. |
| automated | Offscreen render | Six CLI exports passed. Each was 1600 × 960 pixels for an 800 × 480 pt transparent sample canvas on this Mac. A second invocation for each sample produced identical PNG bytes. |
| live-machine | `.venv/bin/python -m tests.test_overlay_live` | Accessibility returned the button frame (256, 612, 118, 26) in global top-left points. The fixture independently reported the button centre at (315, 330) in AppKit points. Both painted paths contained the centre. Their maximum per-axis centre deviations were 1.25 and 1.53 pt, within the 3 pt tolerance. |
| live-machine | Click-through and focus | With the pointer ordered above the key fixture window, the system window hit test at the button centre returned the fixture window number. The harness posted one down/up pair to that window through its own AppKit event queue. The button fired once, the fixture kept keyboard focus and the overlay stayed visible. |
| live-machine | Replacement and expiry | A second show hid the first window and invalidated its timer. The replacement disappeared after its default 45 seconds. The CLI also accepted an explicit duration and a rectangle starting at negative x. |
| live-machine | `.venv/bin/python scripts/qa/run.py` | 8 passed, 0 failed, 0 blocked, 1 needs-human skip. The session start recorded `overlay=sketch` and `planner=scripted`. All 15 decisions in the AIMS sequence passed validation and the run observed both completion text and a fresh practice receipt. |
| not done | Physical second display | The build Mac exposed one display. Above-primary and left-of-primary arrangements were exercised with synthetic screen frames. |

The first click probe used a PID-addressed Quartz event and timed out waiting for the button. The passing probe above checks system window selection and then delivers through the fixture queue. A physical mouse click remains on the human checklist. Both full QA runs produced the counts above, including the final run at 19:58 IST.

## Render inspection

| Evidence | PNG | Observed appearance |
| --- | --- | --- |
| automated | [English](overlay-renders/english.png) | Handwritten “Save Draft” and a smaller subtitle sit on a slanted cream card. A short curved plum arrow ends just outside the double outline. |
| automated | [Malayalam and English](overlay-renders/malayalam-english.png) | The quoted English label and Malayalam തുറക്കൂ share one line. The Malayalam vowel marks are visible and there are no missing-character boxes. |
| automated | [Top](overlay-renders/top.png) | The card sits below the target and the arrow points up. |
| automated | [Bottom](overlay-renders/bottom.png) | The card sits above the target with both lines visible. |
| automated | [Left](overlay-renders/left.png) | The paper extends inward to the right. The left outline stroke fits inside the canvas. |
| automated | [Right](overlay-renders/right.png) | The paper extends inward to the left. The arrow curves down from its right corner. |

To reproduce the mixed-language sample from the repository root, run

```sh
.venv/bin/python -m companion.overlay --rect 240,325,122,36 \
  --text '“Prepare Online” തുറക്കൂ' --subtitle 'Open the practice return.' \
  --render docs/overlay-renders/malayalam-english.png
```

Omit `--render` to use global AX coordinates on the live display. Use `--seconds 5` for a short preview.

## Human checks

- **needs-human** — Follow the outline on a real practice control, move the practice window and confirm alignment by eye. Click the control while the pointer is visible.
- **needs-human** — Inspect both strokes and the smaller subtitle on the Retina display at the normal viewing scale.
- **needs-human** — Read the Malayalam instruction and quoted English label at arm's length.

**Proposed contract changes** — None.
