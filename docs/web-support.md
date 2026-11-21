# Browser practice support

The fixture is a generic three-screen business form, not an implementation of any government service. Use synthetic data only. The companion reads Accessibility, validates a target from that snapshot, and points at it; only the person operates the form. The live checks below used test-only AXPress on the fixture, not product automation.

## Ask about a web page

Select the page in Safari's front window. The reader observes only that window's selected web area, not other windows, tabs, or browser chrome. The companion starts observing after a question, then re-checks while help is active. Click **Stop** before switching to a page you do not want read. Start the general task with `.venv/bin/python -m companion.app --task web_any --planner sarvam`; the scripted planner has no steps for this task and returns unsupported. Sarvam receives the retained control metadata and question, so use public or synthetic pages for the demo.

For a one-shot read, run `.venv/bin/python -m companion.reader com.apple.Safari`. Pass `--page-title` for an exact front window title and/or `--page-url-prefix` for a URL prefix on the same origin. The Python equivalent is `snapshot(bundle_id, page_title=..., page_url_prefix=...)`. `Task.page_title` and `Task.page_url_prefix` are available for wiring at the app call site. The reader's constrained practice path is verified through the CLI; the app and practice task call sites are outside this patch.

Generic snapshots retain interactive controls, headings and named form fieldsets, not page prose. `window_title` carries only the host for real sites; `viewport` is the visible web-area frame in screen points. Controls outside it are omitted, and partly visible controls are clipped. Password nodes are skipped before reading their attributes or children; other field values are reduced to filled flags. This does not prevent a site from independently echoing sensitive information into its own headings or control names.

The reader intersects target frames with every enclosing AX scroll area and the outer web viewport (or native window). `Control.frame` contains only the visible rectangle; a control with no overlap is not a pointer target. Ordinary AX groups do not establish a clip. This uses the ancestor-intersection idea from [MacPaw's macapptree](https://github.com/MacPaw/macapptree/blob/7758229ebe0a2d6258a6090e1a14dd5f509fe22d/macapptree/uielement.py#L221-L241), reimplemented in the bounded reader walk.

The reader and its CLI expose an experimental `below_fold_count`. It counts observed, enabled controls wholly below the page viewport with horizontal overlap, excluding controls clipped out by nested panes. It provides no offscreen targets or labels and can undercount if AX does not expose an element or the traversal reaches its cap. The proposed shared contract is `Snapshot.below_fold_count: int = 0`; a planner can give a non-point scroll-down hint when the next action is not visible and this count is positive, then re-read. No shared contract or planner change is in this patch.

Radio buttons and checkboxes report `filled` from their AX selection state on both web and native screens. Options inside an AX radio group or fieldset carry its label as `group`. The set itself is a non-clickable control with its own frame and an aggregate state: `false` when observed choices are all unselected, `true` when any is selected. A fieldset without observed choices has no aggregate state. Scrolled-out options aren't shown as pointer targets, but their selection can still count toward a visible set.

The reader visits at most 1,200 AX elements per traversal and retains at most 96 controls, including up to 12 headings/fieldsets. Web labels are limited to 160 characters. Browser AX requests have a 40 ms per-request timeout and a 300 ms traversal budget; on timeout the reader raises an error instead of returning a partial snapshot. Hitting a count cap can omit controls. Nested scroll panes are covered by fake-tree tests; CSS clipping not represented by AX scroll areas, embedded web areas, and canvas controls are outside this check.

## Run in Safari

```sh
./scripts/open_web_practice.sh
.venv/bin/python -m companion.reader com.apple.Safari
.venv/bin/python -m companion.app --task web_practice
```

Run from an Accessibility-trusted terminal. The launcher may also prompt for macOS Automation permission to open a new Safari window. If that isn't available, run `.venv/bin/python scripts/serve_web_practice.py` and manually open `http://127.0.0.1:${CONDUCTOR_PORT:-8765}/` in a separate Safari window. Use the same `CONDUCTOR_PORT` for the server, reader and companion. The launcher starts or reuses the server for this workspace and clears the existing practice receipt. Leave the practice tab selected in Safari's front window; Safari itself does not have to have keyboard focus.

| Screen | Controls the companion points to | Progress evidence |
| --- | --- | --- |
| Business Details | Business Name, District, Category, Next | Three `filled` bits; the optional Use Sample Details button fills synthetic values without typing. |
| Documents | Attach Sample Document, Next | `document-note` changes to `Sample attached…`; no file picker or upload. |
| Review | I used only synthetic data, Save | The declaration is checked; the status starts `Training complete` after a successful local receipt write. |

Save posts an empty request to the same loopback server. `runs/web-practice-complete.json` contains only task name, a synthetic-data flag and a timestamp. The practice page does not send the form fields or a file. The companion checks the status and the receipt's freshness independently.

## Isolated Brave probe

Never use a personal browser PID or profile. The Brave reader requires `--pid` and rejects a process unless it matches the Brave bundle, the dedicated temporary profile naming convention and the forced accessibility flag. Only the isolated process and the practice window were inspected during the probe.

```sh
profile="$(mktemp -d /tmp/hackathoni-brave.XXXXXX)"
open -na 'Brave Browser' --args --user-data-dir="$profile" --no-first-run \
  --no-default-browser-check --force-renderer-accessibility=complete \
  "http://127.0.0.1:${CONDUCTOR_PORT:-8765}/"
sleep 1
pid="$(ps -ww -axo pid=,command= | awk -v flag="--user-data-dir=$profile " \
  '/\/Contents\/MacOS\/Brave Browser / && !/ --type=/ && !/awk/ && index($0, flag) {print $1; exit}')"
.venv/bin/python -m companion.reader com.brave.Browser --pid "$pid"
```

Wait for the practice tab to load before reading. A fresh unforced instance exposed no practice `AXWebArea` across 30 polls (~5 seconds). Its app and window reported `AXManualAccessibility` unsupported (`-25205`); `AXEnhancedUserInterface` reported settable on the app but unsupported on the window. Neither attribute was set in this probe. With `--force-renderer-accessibility=complete`, the page was readable ~0.6–0.8 seconds after launch in two runs, without mutating AX attributes. Chromium documents the flag and mode values in its [Accessibility Overview](https://chromium.googlesource.com/chromium/src.git/+/refs/heads/main/docs/accessibility/overview.md). The shipped task still defaults to Safari; Brave is verified as a reader target, not wired into `--task web_practice`.

## Practice fixture baseline — 21 November 2026

**Live-machine:** five CLI snapshots per row and browser. Timings in milliseconds, excluding Python startup; each cell is median / max.

| State | Safari | Isolated Brave |
| --- | ---: | ---: |
| Business Details, empty | 66.8 / 101.7 | 67.8 / 69.5 |
| Business Details, sample filled | 74.0 / 112.7 | 71.7 / 74.5 |
| Documents | 70.9 / 73.4 | 69.3 / 72.6 |
| Review | 68.4 / 69.3 | 68.5 / 71.7 |

All 40 snapshots found the expected IDs (including `screen-title` and `status`) with positive frames and no browser chrome or typed/selected values. Both browsers reported the three practice fields as filled only after sample entry. In Safari, `--task web_practice` validated all seven decisions, from the initial pointer through the fresh receipt; in-process observation max was 51.1 ms. The live run used the sample button to fill all three fields together; individual field progression is covered by unit tests.

**Automated:** `.venv/bin/python -m unittest discover` — 28 passed, 0 failed. `node --check apps/web-practice/practice.js`, `sh -n scripts/open_web_practice.sh` and `git diff --check` passed. HTTP negative checks — 3 passed (foreign origin, nonempty body, invalid route). `./apps/aims-training/build.sh` succeeded; `.venv/bin/python scripts/qa/run.py` — 8 passed, 0 failed, 0 blocked, 1 needs-human skip. AIMS still completed 15 decisions and verified its own receipt.

**Needs human:** Malayalam copy, voice input, visual pointer placement, and click-through on the browser page. No real portal, personal browser profile, third-party login, nested scroll pane, or iframe was tested. Scrolled-out controls are excluded rather than automatically revealed. An obscured practice window or a duplicate matching window is not disambiguated by the overlay.

## Public-page verification — 21 November 2026

**Live-machine / read-only:** seven successful Safari CLI reads per page after load. Each public site was opened in a new dedicated window; no fields or buttons were used. All retained frames were positive and inside the reported viewport.

| Page | Median / max | What Safari exposed |
| --- | ---: | --- |
| [httpbin pizza order form](https://httpbin.org/forms/post) | 70.3 / 72.1 ms | Name, phone, email, size radios, topping checkboxes, delivery time, instructions, submit button, and both named fieldsets. The native time picker is one labeled control; its segments and filled state are omitted. |
| [Wikipedia home](https://www.wikipedia.org/) | 75.9 / 78.4 ms | Search field and button, language picker, heading and visible links. Page prose and links outside the viewport were omitted. |
| Local practice, Business Details, strict title/URL | 69.8 / 71.7 ms | The expected fields, controls, `screen-title` and `status`. |

No page path/query, browser chrome, or entered values appeared in the public-page snapshots. Safari can return no usable web area while a tab loads; retry after it settles. Password suppression was tested with both an AX secure role and a secure subrole in a fake tree, not on any login page. Live Sarvam guidance on the public pages was not tested.

**Choice sets / read-only:** a fresh httpbin window exposed three `Pizza Size` radios and four `Pizza Toppings` checkboxes. All seven were unselected, and both group controls reported `filled=false`, matching Safari's raw AX selection flags. Five CLI reads took 70.1 ms median / 70.8 ms max. No external controls were operated. Automated fake-tree tests cover selection transitions, the planner signature change, and a checked option outside the viewport.

**Below the fold / read-only:** in a dedicated Safari window on local `/pizza`, a 278 pt-high viewport omitted Submit order (raw top `y=854`, viewport bottom `y=400`) and returned `below_fold_count=8`. Enlarging the window gave an 843 pt-high viewport, made Submit visible, and returned `0`. Five CLI reads at each size took 70.3 / 72.5 ms median / max (short) and 70.5 / 71.9 ms (tall). No form controls were operated; the test window was closed.

**Live-machine / regression:** five isolated Brave reads of the practice page in front-window mode gave 65.4 ms median / 67.0 ms max. The locked QA suite confirmed all three Safari practice screens and the AIMS flow through their local receipts. The reader prefers bundle paths under this worktree root. It does not fall back to another worktree for `in.hackathoni.*` fixtures; external apps such as Safari still use the first running instance when there's no local copy.

**Automated:** `.venv/bin/python -m unittest discover` — 115 passed. `.venv/bin/python scripts/qa/run.py` — 19 passed, 0 failed, 2 blocked (opt-in Sarvam checks), 3 needs-human skips.
