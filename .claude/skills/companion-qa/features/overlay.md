# Sketch overlay (`companion/overlay/`)

Status: merged · Owner: Codex `gpt-6.2-astra` (damascus) · Source: `docs/overlay-verification.md`

Native pointer implementing `PointerOverlay`: Plum sketch style, Malayalam glyph fallback, click-through. The companion falls back to the plain pointer if the overlay fails to import (session log records `overlay=sketch` or `basic`).

## Claims
- Stroke path centre matches the Accessibility centre of a real control within 3 pt (docs: 1.25 and 1.53 pt).
- Fractional coordinates, displays above or left of the primary, targets across a display boundary, edge placement and tall-target placement are handled (6 geometry/font tests).
- Mixed English/Malayalam text shapes with no missing glyphs (Shantell Sans + Malayalam Sangam MN).
- Click-through: with the pointer on top, the window server still routes a click at the control to the control; the fixture keeps keyboard focus.
- A second `show` replaces the first; the default expiry is 45 s; renders are byte-stable.

## Machine checks
| Check file | Claim | Evidence |
|---|---|---|
| `unit.py` (`tests/test_overlay_geometry.py`, `test_overlay_fonts.py`) | geometry, glyph runs | automated |
| `overlay_live.py` | AX alignment ≤ 3 pt, click-through, timers (`python -m tests.test_overlay_live`) | live-machine |
| `aims_e2e.py`, `web_practice_e2e.py` | companion still completes with the sketch overlay installed | live-machine |

Registry note: `tests/test_overlay_live.py` is a script, not a unittest, so `unittest discover` runs **zero** tests from it. `overlay_live.py` exists for that reason. It is BLOCKED (not FAIL) when another agent's panel or overlay sits over its fixture button after one retry; any other failure is a FAIL.

## Human checklist
1. Follow the outline on a real practice control (AIMS and the Safari form); move the practice window and confirm the outline stays on the control by eye.
2. Click the control while the pointer is visible; the click must land on the control, once.
3. Inspect both strokes and the smaller subtitle on the Retina display at normal viewing scale.
4. Read the Malayalam instruction and the quoted English label at arm's length (renders: `docs/overlay-renders/*.png`).
5. If a second display is available, drag the practice window onto it and check alignment (only synthetic frames tested).

## Known gaps
- No physical second display, no physical mouse click, no human legibility check.
- Alignment is proven against a native fixture, not yet against the Safari page (the web e2e proves validation and completion, not pixel alignment).
- The live test fails when a foreign window covers its fixture; it is not isolated from other agents' windows.
