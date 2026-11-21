# Web support (Safari practice form)

Status: merged · Owner: Codex `gpt-6.2-sol` (port-louis), QA coverage by Sonnet QA · Last QA: see `runs/qa/` newest report

Browser support for the reader plus the synthetic three-screen business form (`apps/web-practice/`, served by `scripts/serve_web_practice.py`, launched by `scripts/open_web_practice.sh`, scripted by `companion/tasks/web_practice.py`). Source: `docs/web-support.md`. Safari only is wired into the task; isolated Brave is a reader probe, not tested here.

## Claims
- The reader finds the practice page's controls by DOM id (`AXDOMIdentifier`) in Safari, with no browser chrome.
- Typed and chosen values never appear in a label; inputs report only `filled`.
- With `--task web_practice` the pointer visits business-name → district → category → Next → Attach Sample → Next → declaration → Save, then completion, each decision validated against the live snapshot.
- Completion needs the on-screen status `Training complete` plus a fresh `runs/web-practice-complete.json` holding only `task`, `synthetic`, `completed_at`.
- Reads stay well under the 250 ms budget (docs: median ~70 ms CLI, in-process max 51 ms).

## Machine checks
| Check file | Claim | Evidence |
|---|---|---|
| `unit.py` (`tests/test_task_web_practice.py`) | task script, per-field progression | automated |
| `web_practice_reader_live.py` | step ids on all 3 screens, no chrome controls, no leaked values, filled flags, read latency | live-machine |
| `web_practice_e2e.py` | step sequence, validation, completion + fresh receipt (keys checked), observe latency | live-machine |

How the live checks work: `scripts/qa/checks/_web.py` closes only Safari windows/tabs whose URL is exactly this workspace's `http://127.0.0.1:$CONDUCTOR_PORT/`, opens one fresh page with `open_web_practice.sh`, and closes it afterwards. `scripts/drive_web_practice.py` (test-only) acts only inside the `AXWebArea` with that exact URL, by DOM id. The e2e launches the companion with `--mute --task web_practice --question ...`: no Sarvam calls.

Driver limits (so nobody over-reads a pass): Safari does not expose `<select>` popup menus to Accessibility, so district and category are filled by the page's own "Use Sample Details" button, not by choosing options. The name is typed via `AXValue` (needs `AXFocused` first). Per-field district/category progression is covered only by unit tests.

## Human checklist
1. Run `./scripts/open_web_practice.sh`, then `.venv/bin/python -m companion.app --task web_practice` from an Accessibility-trusted terminal.
2. Follow only the pointer: type a made-up name, choose district and category from the real menus, Next, Attach Sample Document, Next, tick the box, Save. The pointer must sit on each control in turn and end with "Verified: status text seen + fresh training receipt file".
3. Click-through: the pointer must never swallow your click on the page.
4. Malayalam text: read the instruction for each step aloud; flag anything unnatural (copy is marked draft for native-speaker review).
5. Scroll or resize the window so a control scrolls out of view: the pointer should vanish or ask, not point at empty space (gap below).
6. Confirm visually the pointer lines up with the browser page (not offset by the toolbar) at normal and zoomed page sizes.

## Known gaps
- Only the optional sample button fills selects in automation; real select menus untested by machine.
- Nested scroll panes, iframes, real portals, other browsers, personal profiles: not tested (by design).
- Scrolled-out controls are excluded, not revealed; a duplicate matching Safari window on the same port is ambiguous (the QA check closes duplicates first).
- Live checks assume Safari windows for this port belong to QA while the suite runs; two agents running the web checks at once on one port will interfere.
