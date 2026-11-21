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

| `pizza_follow_pointer_e2e.py` | **follow-the-pointer on a real-shaped form** (pizza page `/pizza`, Sarvam planner): order name→phone→email→Pizza Size→Submit, Pizza Size covered, no repeated target, orientation text only once, filled control never pointed at, toppings skipped, every pointer validated, completion + receipt | live-machine, **live Sarvam** (~10-15 chat calls); BLOCKED unless `QA_LIVE_SARVAM=1` |
| `qa_selftest.py` | the pizza assertions pass a good decision list and fail an Abin-style buggy one | automated |

Pizza page: `apps/web-practice/pizza.html` (+ `pizza.css`, `pizza.js`), route `/pizza`, same structure as https://httpbin.org/forms/post, written from scratch: no ids on fields, no required markers, no headings. Submit POSTs an empty body to `/pizza-receipt` and writes `runs/pizza-complete.json` (`task`, `synthetic`, `completed_at`); the page then shows the heading "Order received (practice)" under the form. Driver: `scripts/drive_follow_pointer.py` tails `runs/session-*.jsonl`, maps each pointed frame to an element of the pizza page (IoU ≥ 0.6, else presses nothing), types a sample into text fields, presses the first option of a choice set, presses buttons, leaves checkboxes and the time input alone, and stops on `complete`, a terminal decision, the same target 3×, or a timeout. It writes `runs/pizza-follow-<stamp>.jsonl` (one line per decision, with `filled_before`), which the check turns into verdicts; the full decision list is printed and stored in the failing result's detail.

How the live checks work: `scripts/qa/checks/_web.py` closes only Safari windows/tabs whose URL is exactly this workspace's `http://127.0.0.1:$CONDUCTOR_PORT/`, opens one fresh page with `open_web_practice.sh`, and closes it afterwards. `scripts/drive_web_practice.py` (test-only) acts only inside the `AXWebArea` with that exact URL, by DOM id. The e2e launches the companion with `--mute --task web_practice --question ...`: no Sarvam calls.

Driver limits (so nobody over-reads a pass): Safari does not expose `<select>` popup menus to Accessibility, so district and category are filled by the page's own "Use Sample Details" button, not by choosing options. The name is typed via `AXValue` (needs `AXFocused` first). Per-field district/category progression is covered only by unit tests.

## Human checklist
1. Run `./scripts/open_web_practice.sh`, then `.venv/bin/python -m companion.app --task web_practice` from an Accessibility-trusted terminal.
2. Follow only the pointer: type a made-up name, choose district and category from the real menus, Next, Attach Sample Document, Next, tick the box, Save. The pointer must sit on each control in turn and end with "Verified: status text seen + fresh training receipt file".
3. Click-through: the pointer must never swallow your click on the page.
4. Malayalam text: read the instruction for each step aloud; flag anything unnatural (copy is marked draft for native-speaker review).
5. Scroll or resize the window so a control scrolls out of view: the pointer should vanish or ask, not point at empty space (gap below).
6. Confirm visually the pointer lines up with the browser page (not offset by the toolbar) at normal and zoomed page sizes.

7. Pizza page by hand: open `http://127.0.0.1:$CONDUCTOR_PORT/pizza` in the front Safari window, run `.venv/bin/python -m companion.app --task web_any`, ask "Can you help me fill this form?" and follow only the pointer. It should visit name, phone, email, the Pizza Size set, then Submit; say what the page is once; never point at a field you already filled; and congratulate you after "Order received (practice)".

## Known gaps
- Pizza follow-the-pointer: the first run on 21 Nov (HEAD c84e361) was RED by design (misordered/skipped steps, repeated orientation, no `complete`): see `runs/qa/20261121-231110`. The time input (`AXDateTimeArea`) cannot be driven through Accessibility, so the driver ignores it; if the planner points there the run ends by repeat/timeout. The page keeps the form visible after submit (inline confirmation), so "complete" needs the planner to read the confirmation heading; a replace-the-form variant is not covered.
- The live pizza check puts a Safari window in front and drives only our page, but it competes with a person using Safari and with other companions reading the front window: run it when Safari is idle.
- Only the optional sample button fills selects in automation; real select menus untested by machine.
- Nested scroll panes, iframes, real portals, other browsers, personal profiles: not tested (by design).
- Scrolled-out controls are excluded, not revealed; a duplicate matching Safari window on the same port is ambiguous (the QA check closes duplicates first).
- Live checks assume Safari windows for this port belong to QA while the suite runs; two agents running the web checks at once on one port will interfere.
