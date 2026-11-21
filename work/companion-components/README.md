# Isolated H Companion component tests

This harness uses the unmodified `a11y`, `overlay` and `overlay_layout` modules from the H Companion clone at commit `287c4c1bd64f58869fc52db17aaa63f62744dbcb`. It does not load its CLI, H SDK, speech clients, HTTP server, gaze tracker or input listener. No API keys are needed.

The reference files remain unmodified on disk. The optional `overlay_styles.py` adapter changes drawing helpers only in the current probe process to try different fonts, colors and vector shapes. Set `overlay-style.json` to `focus` (blue/system font), `terminal` (dark/teal/monospace), or `original` (red/handwriting, currently selected again because the user prefers the playful asymmetric appearance). Click Show pointer to apply the selection; no app rebuild is required. Both new themes passed component render/coordinate/click-through-flag checks, but the completed live alignment and manual-click evidence below is specifically the **original-style baseline**. Live retesting of the new skins is pending.

## Current evidence

- The native practice app compiled and launched. Its controls and input field were observed through the computer-use tool.
- The original reader **passed** after the stale fixture permission entry was removed/re-added. First success at 15:41 IST: 15 controls/text elements, expected buttons found, valid rectangles and typed input values excluded. AX traversal was about 11.4 ms in that sample, excluding process startup. TCC logs confirmed the earlier failure was an old stored code requirement, not a need to permit Python separately.
- The original pointer renderer instantiated, converted top-left target coordinates into its drawing coordinates, enabled mouse-event pass-through and rendered its own view to `pointer-component.png`. Those checks passed; see `pointer-component-result.json`.
- Live alignment **passed**: the Accessibility target and independently supplied fixture button have identical centers, and the user's screenshot/confirmation show the highlight around Export PDF. Manual click-through also **passed** on the status-confirming retry: a fresh `manual-click.json` records Export PDF during the active pointer run, and the user confirmed the exact status message. See `verification-summary.json` for preserved snapshots and timing.
- Utter dictation into this window is **not verified yet**. Typed input is not proof of Utter working.
- The probe timestamps results and replaces stale results on errors. For a live pointer run sourced from Accessibility, it compares the target center with fresh fixture-supplied button geometry (inside the button, at most three points from its center). This comparison **passed live with zero center delta**; visual alignment was confirmed separately.

## Test sequence

1. Open `Companion Test Pad.app`. On this Mac (verified macOS **27.2.1**), the permission is at **System Settings → Privacy & Security → Device Control and Data Access**, not a privacy item named Accessibility. On macOS 13–26 the item was called Accessibility. The original instructions used that older name and were incorrect for this machine. Add the test app and enable its permission if needed. This is a macOS permission, not an API credential. The harness will only target the exact foreground practice app, even though the OS permission itself is broader. No permission settings are modified by these scripts.
2. Click **1 · Read controls**. It must find the known buttons, produce positive rectangles and exclude the sentinel customer-field content from the original reader's snapshot. Results go to `reader-result.json`.
3. Click **2 · Show pointer**. With reader permission, it reads a fresh Accessibility target for Export PDF. Without permission it can independently draw from geometry supplied by the fixture itself; the result explicitly records that different source and does not count as a reader pass. Keep the practice window in front and stationary during this test. The overlay hides on focus loss, Stop pointer or after 45 seconds.
4. Verify the bracket is around **Export PDF**. Click that button yourself. The status should say “Export PDF clicked — test only; no file created.” `manual-click.json` records the test-button event. The harness issues no automatic clicks.
5. Only after those checks, focus **Your question**, dictate “show me Export PDF” with the user's existing Utter shortcut, then click **Use question**. `submitted-question.json` captures only this intentionally submitted practice-field text. It does not read Utter's history, clipboard or database. User confirmation is needed to distinguish speech dictation from typed input.

The question is stored locally for input verification. It is not connected to a planner or used to choose targets yet. Stage 3 always points at the fixed known button.

## Local commands

Run commands from this directory:

```sh
.venv/bin/python probe.py pointer-check
```

This checks the renderer and saves an image of its own view; it does not capture the desktop. The GUI buttons launch `probe.py read` and `probe.py point` while the practice window remains foreground.

To rebuild the fixture:

```sh
swiftc -swift-version 5 TestPad.swift -o 'Companion Test Pad.app/Contents/MacOS/CompanionTestPad' -framework AppKit
codesign --force --sign - 'Companion Test Pad.app'
```

Reopen the app after rebuilding. Ad-hoc signing after changes may require renewing the OS permission. Only five pinned PyObjC packages from the original lockfile were installed in this harness's private `.venv`; see `requirements-macos.txt`.

**Resolved permission blocker:** `permission-signature-diagnostic.txt` records an old stored code requirement (`187d0dd…`) failing against the current fixture (`f85afe0…`). Removing/re-adding only Companion Test Pad in Device Control and Data Access fixed the reader. Keep the executable unchanged during retesting. This diagnostic did not indicate a need to grant Python separate access or reset all app permissions.

Initial scope is one stationary practice window on the main display. Multi-monitor layouts, moving targets, screenshot/OCR reading, AI target selection, Sarvam and full application flows remain untested.

## Permission-name verification (2026-11-21)

The installed OS version was read with `sw_vers`. Microsoft's [macOS 27 permission documentation](https://learn.microsoft.com/en-us/purview/endpoint-dlp-macos-27-changes) gives the exact Privacy & Security → Device Control and Data Access path and explains the former Accessibility name. Apple's [November 16 announcement](https://developer.apple.com/news/?id=oqng0zjk) confirms that the existing Device Control and Data Access setting is being split into System & App Protection Override and Accessibility starting with macOS 27.3 beta 2. Those later names must not be assumed for this 27.2.1 installation.
