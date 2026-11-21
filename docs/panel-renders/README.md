# Paper Note panel

These PNGs show the AppKit content view rendered offscreen at 2×. The examples use synthetic questions and instructions. The live panel draws the same views.

| State | Malayalam | English |
| --- | --- | --- |
| Idle | [Open Malayalam idle](idle-ml.png) | [Open English idle](idle-en.png) |
| Listening | [Open Malayalam listening](listening-ml.png) | [Open English listening](listening-en.png) |
| Thinking | [Open Malayalam thinking](thinking-ml.png) | [Open English thinking](thinking-en.png) |
| Guiding | [Open Malayalam guiding](guiding-ml.png) | [Open English guiding](guiding-en.png) |
| Done | [Open Malayalam done](done-ml.png) | [Open English done](done-en.png) |
| Error | [Open Malayalam error](error-ml.png) | [Open English error](error-en.png) |

The idle microphone is 96 pt. During guidance it shrinks to 56 pt beside 50 pt Skip and Stop buttons. The step uses 27 pt Shantell Sans with Malayalam Sangam MN in the cascade and a minimum line height of 41 pt. Long instructions scroll within the step card. The chip shows the validated target’s label when a target is available.

Replay uses the existing Sarvam speech path and the current language. Completion shows the planner’s actual completion message. New question returns to the microphone and clears the question field. The typed question and Ask stay visible in all six states. The ellipsis opens the existing developer status.

Listening uses a stop glyph and Core Animation rings and bars. The bars indicate recording activity. The voice adapter exposes no input-amplitude feed. Reduce Motion holds the rings and bars still, including when the preference changes during a recording.

## Verification on the build Mac

| Evidence | Command | Result |
| --- | --- | --- |
| automated | `.venv/bin/python -m unittest` | 192 passed. Panel coverage includes language changes, replay, recovery with the same step after a reader error, speech failure during guidance, recording priority, long text, details and Reduce Motion. |
| automated | `.venv/bin/python -m companion.panel.render docs/panel-renders` | Rendered and visually inspected all 12 panels. The Malayalam text is shaped, with distinct vowel signs. The long sample wraps inside the step card. |
| live-machine | `.venv/bin/python -m tests.test_panel_ax` | Passed all 12 state/language combinations. The window exposed its state, the first AXTextField was the question field, and an AXButton had the exact localized Ask title. The guiding tree exposed all nine required identifiers, including companion-skip. |
| live-machine | `.venv/bin/python -m tests.test_panel_focus` | Safari remained frontmost in all 25 samples during normal Companion launch and all 10 samples after focusing the panel’s question field, entering a question and pressing Ask via Accessibility. |
| live-machine | `.venv/bin/python scripts/qa/run.py` | 20 passed, 0 failed, 3 human checks skipped and 5 opt-in checks gated. The Safari practice form reached its receipt in eight decisions with zero reader pauses. The AIMS fixture completed 15 decisions. |
| live-machine | `QA_LIVE_SARVAM=1 .venv/bin/python scripts/qa/run.py pizza_follow kseb_follow` | 21 passed, 0 failed, 2 human checks skipped. Both local practice walks reached their completion messages and wrote fresh receipts. Pizza exercised the panel’s Skip button twice. |
| needs-human | Older Malayalam speaker on the actual display | Assess reading comfort at arm’s length, understanding of each state, and ease of using the mic and replay. |

One earlier KSEB run reached Submit and timed out before a receipt appeared. Two subsequent locked runs passed all 21 live assertions. The final default and live reports are in `runs/qa/20261122-013428/` and `runs/qa/20261122-013609/` respectively. The team can reproduce the focus and Accessibility probes with the commands above.
