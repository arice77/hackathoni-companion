# Browser practice support

The fixture is a generic three-screen business form, not an implementation of any government service. Use synthetic data only. The companion reads Accessibility, validates a target from that snapshot, and points at it; only the person operates the form. The live checks below used test-only AXPress on the fixture, not product automation.

## Run in Safari

```sh
./scripts/open_web_practice.sh
.venv/bin/python -m companion.reader com.apple.Safari
.venv/bin/python -m companion.app --task web_practice
```

Run from an Accessibility-trusted terminal. The launcher may also prompt for macOS Automation permission to open a new Safari window. If that isn't available, run `.venv/bin/python scripts/serve_web_practice.py` and manually open `http://127.0.0.1:${CONDUCTOR_PORT:-8765}/` in a separate Safari window. Use the same `CONDUCTOR_PORT` for the server, reader and companion. The launcher starts or reuses the server for this workspace and clears the existing practice receipt. Keep just one matching practice window open to avoid ambiguity; the reader doesn't require it to have focus, but the practice tab must be selected in that window.

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

## Verification — 21 November 2026

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

## Proposed contract changes

`Control.identifier` can already hold a DOM ID; update its description to say `AXIdentifier or AXDOMIdentifier`. Add an explicit browser target to the task or reader configuration (bundle, allowed origin/path, window-title matcher and optional isolated PID) when selecting the first real website. Consider a `Snapshot.viewport_frame` separate from the outer `window_frame`, plus a way for the planner to distinguish an off-screen control from a missing one. No shared contract files changed in this build.
