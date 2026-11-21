# Native sketch pointer verification

Verified 21 November 2026 on one 1470 × 956 pt display at 2× with Python 3.13 and PyObjC 13.0. The six transparent PNGs contain the overlay and sample instructions. The comparison uses crops of the approved local preview and synthetic buttons.

## Appearance at display scale

[Open the side-by-side comparison](overlay-renders/compare-preview.png). The upper row uses the preview’s “Publish project” label, button dimensions and two lines of English in both panels. The lower right overlays the actual Malayalam PNG on a dark sample button. One native point corresponds to one preview pixel.

The two plum passes meet on portions of the side edges, separate along the longer edges and carry a few points past the corners. The native card has a 2° counterclockwise tilt, a warm shadow under its lower edge and tighter padding than the approved fixed-size web card. The English comparison retains the 25 pt instruction and 17 pt subtitle. The Malayalam instruction sits in a 320 × 48 pt card with one line.

| Evidence | Sample | Inspection |
| --- | --- | --- |
| automated | [English](overlay-renders/english.png) | “Click Save Draft” sits on one compact line with balanced space above and below. |
| automated | [Malayalam and English label](overlay-renders/malayalam-english.png) | “Prepare Online” and തുറക്കൂ share the tilted baseline. Vowel signs are visible and there are no missing-glyph boxes. |
| automated | [Top](overlay-renders/top.png) | The paper flips below the target. The practice form’s full Malayalam instruction for “Business Name” wraps to three lines on a 405 × 116 pt card. The final word fits. |
| automated | [Bottom](overlay-renders/bottom.png) | The one-word Malayalam prompt തുടരൂ fits on a 90 × 48 pt card above the target. |
| automated | [Left](overlay-renders/left.png) | The note extends inward to the right. Its smaller English subtitle sits directly below the instruction. |
| automated | [Right](overlay-renders/right.png) | The note extends to the left and the arrow bends back to the top edge of the target. |
| automated | [Preview comparison](overlay-renders/compare-preview.png) | Both native arrows meet the paper near its corner. The reference leaves more space between the target and the paper. |

## Verification

| Evidence | Check | Result |
| --- | --- | --- |
| automated | `.venv/bin/python -m unittest` | 65 passed. Tests exercise the AX coordinate conversion, display selection, note flipping, single-language text fit, full wrapped Malayalam text, and arrow length at corners and across displays. |
| automated | Font shaping | Core Text selected Shantell Sans at INFM 35, BNCE 16 and wght 500 for English, and Malayalam Sangam MN for Malayalam. The test checked that every glyph ID in the mixed sample was nonzero. |
| automated | Repeat export | All six CLI renders and the comparison were byte-identical on repeat export. |
| live-machine | `.venv/bin/python -m tests.test_overlay_live` | AX returned (256, 612, 118, 26) in global top-left points. Both drawn paths contained the independently measured AppKit button centre at (315, 330). Their maximum per-axis centre errors were 0.77 and 2.07 pt. |
| live-machine | Click-through and lifetime | The system hit test selected the underlying fixture window. It received one down/up pair in its own event queue, fired the button once and retained keyboard focus. Replacement hid the old pointer, and the new pointer expired after 45 seconds. An earlier probe detected an intervening window and stopped before posting input. |
| live-machine | `.venv/bin/python scripts/qa/run.py` | Final run at 20:28 IST passed 8 checks with 0 failures, 0 blocked and 1 needs-human skip. The session logged `overlay=sketch`, all 15 AIMS decisions validated and completion included a fresh practice receipt. Three earlier runs during shared fixture use had 3, 2 and 2 failures involving step progression, receipt detection or initial controls. |
| not done | Physical second display | The build Mac exposed one display. Above-primary and left-of-primary cases used synthetic screen frames. |

To reproduce the mixed-label example from the repository root, run

```sh
.venv/bin/python -m companion.overlay --rect 240,325,122,36 \
  --text '“Prepare Online” തുറക്കൂ' --render docs/overlay-renders/malayalam-english.png
```

## Human checks

- **needs-human** — Follow the outline and click a real practice control after moving the practice window.
- **needs-human** — Inspect the two strokes and smaller type on the Retina display at normal scale.
- **needs-human** — Read a wrapped Malayalam instruction and its English control label at arm’s length.

**Proposed contract changes** — None.
