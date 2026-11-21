# Building the companion app

Updated: 21 November 2026, Asia/Kolkata. **Living handoff for Abin, Conductor, Claude and Codex.** Read this before starting the hackathon implementation. Update the status and next action after each meaningful test, preserving the distinction between observed results and proposed work.

## 1. What we are building

A macOS companion that helps a person use software: ask a question, see one short instruction and a pointer marking the relevant live control, perform the click yourself, then receive the next step after the screen is checked again.

The inspiration is H Companion. The intended new implementation should work without an H Company account. **Utter is our voice input for now.** Sarvam is the proposed reasoning provider; its ability to select the correct controls still needs testing. Sarvam speech input/output and a Devin repair workflow come later if useful and feasible.

Build a small implementation from scratch around this flow. Study the original for mechanics; avoid importing its entire product and dependency tree. First prove one application and two or three tasks. The real target app and tasks are still undecided; the current practice invoice window is only a component fixture.

At the hackathon, read the actual brief and sponsor requirements before committing to a demo. Earlier winners are design evidence, not proof that our proposed idea meets the current judging criteria. In particular, establish whether using Devin to build the app satisfies the relevant track or whether a runtime integration is required.

## 2. Exact current state — start here

| Item | Evidence and status |
| --- | --- |
| Original project studied | H Companion clone at commit `287c4c1bd64f58869fc52db17aaa63f62744dbcb`; its tracked working tree was clean on the last check. |
| Original full application | **Not launched.** No H, Gladia, Sarvam or Devin API calls were made for our component tests. |
| H Company access | User attempted signup and reported that new signups were disabled. Do not spend the demo build trying to obtain H access; recheck only if there is a concrete reason. |
| Local fixture | Native Swift/AppKit “Companion Test Pad” built and launched. Contains a question field, fake invoice controls and reader/pointer test buttons. It is separate from the original clone. |
| Minimal dependencies | Five PyObjC packages, all version `13.0`, installed in the harness's own Python 3.13 virtual environment. Package versions and wheel hashes came from the original lockfile. |
| Pointer component | **Passed:** original renderer instantiated, coordinate conversion assertions passed, click-through flag enabled, and its own view rendered to PNG. Live positioning also passed below; physical click-through is a separate check. |
| Original Accessibility reader | **Passed.** First confirmed success at 15:41 IST after re-adding the current app: 15 controls/text entries, expected buttons found, positive rectangles and typed input values excluded. AX traversal took about 11.4 ms in that sample, excluding interpreter startup. |
| Permission grant | **Resolved and verified.** Removing the stale entry and re-adding the unchanged current fixture fixed the reader permission failure. No separate Python grant was needed. |
| Restart | Quit and reopened the test app successfully using command-line commands after the reported grant. |
| Command-driven button press | Blocked by macOS: `osascript is not allowed assistive access` (`-1728`). This is a separate automation-process permission, not evidence that the test app's own reader will fail. |
| Live pointer over Export PDF | **Positioning and manual click-through passed.** Fresh Accessibility target center `(483, 480)` matches independently supplied fixture geometry exactly (zero-point delta). Screenshot/user evidence confirms the highlight surrounds Export PDF. At 15:44:27 IST the fixture saved its Export PDF click receipt during the overlay run, and the user confirmed the exact post-click status. |
| Utter | Local installation and stored transcripts were located earlier using a read-only inspection. **Live Utter dictation into our fixture is unverified.** Use its normal dictation-to-field flow; history access is unnecessary. |
| Question → target selection | **Not implemented.** “Use question” stores input locally. “Show pointer” always targets the known Export PDF button. It does not interpret the question. |
| Sarvam / Devin product integration | **Proposed only.** No working planner, speech adapter or live repair session has been demonstrated. |

**Immediate next action:** stage A is complete for the stationary single-window fixture. Next test real Utter dictation into the question field (stage B), then separately evaluate semantic control selection. Keep the compiled fixture unchanged; there is no reason to repeat the resolved permission setup or grant unrelated helpers access. The current known-target highlight is not yet an AI assistant driven by the question.

### Visual style experiments after the baseline passed

The successful live stage-A tests used the **original red handwritten style**. Two local alternatives now exist: **Focus** (blue, white rounded callout, semibold macOS system font) and **Terminal** (teal, dark rounded callout, macOS monospace font). Both passed renderer instantiation, coordinate-conversion assertions, click-through-flag and own-view PNG rendering checks. **Live alignment/click-through of these new visual variants has not yet been retested.** After seeing them, the user explicitly preferred the initial playful handwriting and asymmetry with a small distinctive twist. **Original is selected again for the next Show pointer click.** The intended design direction is organic/hand-drawn, rather than the smooth system-font variants.

The original appearance is defined in the reference `overlay.py`: `GRAPHITE`, `PAPER`, `PAPER_SOFT`, `HAND_FONTS`, `TEXT_SCALE`, `_hand_font`, `_wobble_path`, `_draw_paper`, `_frame` and `_arrow`. It is native AppKit drawing, not CSS, an AI-generated image or a service response. Fonts are locally resolved macOS fonts; the original tries Bradley Hand, Noteworthy, Marker Felt and Chalkboard before system fallback.

Our [local style adapter](work/companion-components/overlay_styles.py) changes drawing helpers only in the running probe process. [Style selection](work/companion-components/overlay-style.json) accepts `focus`, `terminal` or `original` (currently selected). No original repository files or fixture executable were changed; the permission-sensitive code hash remains `f85afe0669e25e922c54a271bb5a7e857835c51b`. Previews and style-specific component results are in the harness folder. Changing this JSON and clicking Show pointer is sufficient to try a style, without rebuilding the app.

This helper override is an isolated style experiment against the reference renderer. In the clean implementation, put themes behind an explicit renderer/theme interface instead of depending on another project's private helper names. The reader/target selection should remain independent of typography and colors. Preserve `verification-summary.json` as the original-style live baseline rather than presenting it as proof of every future skin.

#### Handwritten font and sketch-UI sources (researched 21 November)

- [Google Fonts](https://fonts.google.com/): browse handwriting typefaces. [Caveat](https://fonts.google.com/specimen/Caveat) is designed for annotations and has contextual letter variations; [Kalam](https://fonts.google.com/specimen/Kalam) has a quick pen-written feel. See the first-party [Caveat description](https://github.com/google/fonts/blob/main/ofl/caveat/DESCRIPTION.en_us.html) and [Kalam description](https://github.com/google/fonts/blob/main/ofl/kalam/DESCRIPTION.en_us.html).
- [Shantell Sans](https://shantellsans.com/): strongest candidate to try next, not yet downloaded or integrated. The official site has a playground, downloads and an SIL OFL 1.1 license. Its Informality and Bounce axes adjust irregular letterforms and uneven baselines. These are useful for a deliberately playful identity. The font supports Latin/Cyrillic; it does not establish Malayalam-script coverage.
- [Fontsource](https://fontsource.org/): font directory and self-hosted web-font packages, useful if the final UI uses web technology. Native AppKit font loading is a separate integration.
- [Rough Notation](https://roughnotation.com/): live gallery and JavaScript library for sketchy boxes, circles, highlights and underlines.
- [Rough.js](https://roughjs.com/): Canvas/SVG primitives with configurable roughness, bowing and stroke width.
- [Wired Elements](https://wiredjs.com/): gallery and installable hand-drawn web components. These web libraries are design/implementation references, not drop-in replacements for the current native AppKit overlay.

Recommended next visual experiment: retain asymmetric borders and compact paper-like callouts, compare the existing handwriting with Caveat and Shantell Sans, and try a distinctive ink/paper palette. Font choice alone does not create irregular border geometry. No fonts were globally installed and no sketch-UI JavaScript dependencies were added for this research.

#### Desktop and web rendering option

The user wants the playful appearance to suit desktop applications and websites. Our existing native macOS overlay already draws over both browser windows and desktop apps; its application-observation support is a separate constraint. We do not need to migrate frameworks simply to change its font, ink color or irregular shapes.

For a future implementation that shares a web renderer, the strongest researched candidate is **Rough.js + Shantell Sans**, hosted in a transparent desktop window when used system-wide. [Rough.js](https://roughjs.com/) draws sketchy Canvas/SVG primitives and exposes roughness, bowing and stroke-width options. [Shantell Sans](https://shantellsans.com/) supplies a distinct handwriting identity with variable Informality and Bounce. These are composable building blocks, not a ready-made native desktop overlay package.

**Proposed integration, not implemented or live-tested:**

- In a website, render Rough.js SVG/Canvas annotations using that page's observed target geometry.
- On desktop, an Electron transparent, frameless, always-on-top window can host the same local renderer over other app windows. Explicitly use `setIgnoreMouseEvents(true)` for pass-through; transparency alone does not enable clicking through. See [window styling](https://www.electronjs.org/docs/latest/tutorial/custom-window-styles) and [click-through APIs](https://www.electronjs.org/docs/latest/tutorial/custom-window-interactions).
- Keep Accessibility observation and the planner behind the existing scene/control-ID contract. Convert screen-point coordinates into the overlay's coordinate system deliberately, including display origin and scaling; a web drawing library does not solve native observation or grounding.
- Keep the currently working native prototype for Utter/planner tests. If shared web rendering becomes a chosen requirement, prove this alternative in an isolated visual prototype before replacing the tested overlay. No Electron or Rough.js dependencies were installed as part of this recommendation.

**Later visual proof completed:** [interactive sketch-style preview](work/companion-style-preview/index.html) and [rendered screenshot](work/companion-style-preview/preview.png). This separate preview uses actual Rough.js 4.6.6 plus a downloaded, locally hosted Shantell Sans variable font. It shows simulated dark desktop and light website screens with cream paper notes, asymmetric outlines and Plum/Forest/Terracotta ink choices. Roughness and font Informality can be adjusted. The font loaded, both SVG annotation layers rendered, the Forest color control updated the ink, and the Export PDF sample button received a click through the SVG; the browser reported no console errors. Asset sources, integrity fingerprints and licenses are stored with the preview.

This is **web-rendered visual proof only**, not a live native-desktop Rough.js overlay or an AI integration. No Electron wrapper was installed, no system fonts were installed, and the permission-sensitive fixture executable was unchanged. The original native prototype remains the tested runtime. Use the preview README to restart its loopback-only local server when needed.

**User-selected visual settings, confirmed from the 21 November 16:09:46 IST screenshot:** Plum ink `#674064`, Rough.js roughness **1.9**, and Playfulness **35** (Shantell Sans `INFM` axis). The existing font Bounce remains **16**, weight **500**, instruction size **25 CSS px**, subtitle **17 CSS px**. The paper fill remains `#fff4d8`, with `#d9c8a6` border and an asymmetric polygon. Outline stroke width is **1.8 CSS px**; paper roughness is independently fixed at **0.65**. These are the preferred values to carry into the product's visual design.

The full record is [selected-style.json](work/companion-style-preview/selected-style.json). The preview defaults now match this selection. Subsequent preview changes autosave in browser local storage and appear in its URL hash, so the values can be recovered without guessing from slider positions. They do not automatically rewrite this handoff or the selected JSON file. The native overlay has **not yet been reskinned** with this selection.

### Latest testing continuation

- **Reader passed after targeted permission refresh.** First successful run: `5a608bcf162c41e99b9a420d1b7c0d9f` at 15:41:09 IST. It found 15 controls/text elements and excluded typed input values.
- **Live positioning passed.** Run `e8f1bc11bd4b4cda8d46c8ac6296ee64` at 15:42:00 IST used Accessibility, not fixture-geometry fallback. Reader and pointer results share that run ID. AX rectangle: `[402, 462, 162, 36]`; fixture rectangle: `[403, 463, 160, 34]`; both centers: `[483, 480]`. The one-point border differences do not change the center. The screenshot supplied by the user shows Export PDF highlighted, and the user confirmed alignment.
- **Manual click-through passed on the status-confirming retry.** Run `1a3ffaccd5404d38a50d90d3c60eecb2` started the pointer at 15:44:26 IST; the app saved `manual-click.json` for Export PDF at 15:44:27 IST, within the active 45-second overlay period. The user confirmed “Export PDF clicked — test only; no file created.” The same run also passed reader and independent target-geometry checks. The earlier missing receipt was treated as incomplete evidence until this successful retry.
- Command-driven Read controls was retried after the reported grant and again denied: `osascript is not allowed assistive access` (`-1728`). The user then clicked the fixture button manually; the new reader run failed its permission preflight.
- **Root cause confirmed in macOS TCC logs:** the reader's Python process is correctly attributed to `in.hackathoni.component-fixture`. The stored grant requires code hash `187d0dd4586aa1d81aff4a74ba8f115c51abfcaf`, while the current fixture is `f85afe0669e25e922c54a271bb5a7e857835c51b`. The log explicitly says “Failed to match existing code requirement.” The changing ad-hoc-signed fixture left a stale permission entry. This is not evidence that Python needs a separate permission. See [bounded diagnostic log](work/companion-components/permission-signature-diagnostic.txt).
- The Python probe now records a run ID and UTC timestamp with results. Reader exceptions update the result instead of leaving an old failure or pass silently in place; pointer failures also produce a fresh failure result.
- Live pointer testing compares the Accessibility target center with independently supplied fresh fixture-button geometry. It requires the center to lie inside that button and differ from its center by at most three screen points. This check **passed live**, visual alignment was confirmed separately, and manual click-through was subsequently corroborated by the fixture's receipt and the user's status confirmation.
- The modified probe passed Python syntax compilation. No fixture-app rebuild or permission setting change was needed for these script changes.

## 3. Workspace and evidence

Workspace: `/Users/abinsaji/Documents/Codex/2026-11-08/https-www-hackathoni-in-https-www`.

Main local entry point: [component harness and instructions](work/companion-components/README.md). That directory contains:

- `TestPad.swift`: fixture UI; launches a narrow Python probe from its buttons.
- `Companion Test Pad.app`: compiled fixture; bundle ID `in.hackathoni.component-fixture`.
- `probe.py`: imports only the original reader and overlay modules through an isolated package namespace, avoiding the original package initializer/CLI.
- `.venv` and `requirements-macos.txt`: isolated, pinned PyObjC dependencies. No original Electron install is required for this harness.
- `reader-result.json`: last reader result; inspect its modification time before relying on it.
- `pointer-component-result.json` and `pointer-component.png`: successful renderer-only check.
- `verification-summary.json`: completed stage-A evidence, including preserved reader/pointer snapshots, exact geometry, user visual/status confirmations and click-receipt timing. The raw pointer snapshot initially says `visual_alignment_verified: false` because it is written before human inspection; the summary records the later verification separately.
- `fixture-layout.json`, `pointer-result.json`, `manual-click.json`, `submitted-question.json`: generated only when the corresponding GUI test runs. Their existence alone is not proof of the whole flow.

The PyObjC packages are core, Cocoa, Quartz, CoreText and ApplicationServices. The original clone is under `research-repos/h-companion`. Keep the clone as a reference; the new product should have its own source and configuration. A private ignored `.env` was prepared earlier with empty H/Gladia key slots and guidance-only settings; it is not evidence of working accounts. Inspect configuration names without printing secret values.

## 4. Permission lesson that cost us time

The host was checked with `sw_vers`: **macOS 27.2.1**. On this machine the relevant privacy setting is:

**System Settings → Privacy & Security → Device Control and Data Access**.

We repeatedly gave the older label “Privacy & Security → Accessibility,” which the user could not find. That instruction was wrong for this machine. The sidebar's general Accessibility page (VoiceOver, Zoom, etc.) and Screen & System Audio Recording are different settings.

Microsoft's [macOS 27 documentation](https://learn.microsoft.com/en-us/purview/endpoint-dlp-macos-27-changes) documents the renamed privacy permission and exact path. Apple's [16 November announcement](https://developer.apple.com/news/?id=oqng0zjk) describes a further split into System & App Protection Override and Accessibility in **27.3 beta 2**; those later labels should not be assumed on 27.2.1. Recheck OS version and current vendor instructions on another machine.

Permissions belong to the requesting process and its macOS attribution. Enabling the fixture does not establish that a terminal Python process or `osascript` can inspect/control apps. Our post-grant CLI trust check still returned false. A fresh test from the fixture established that its Python child is attributed to the fixture, and that the fixture's stored code requirement is stale. Use that specific diagnostic rather than granting Python or unrelated helpers access speculatively.

Build and sign the intended app before asking for its permission. Rebuilding an ad-hoc-signed executable may require removing and re-adding its permission entry; toggling an old entry cannot be assumed to refresh the stored requirement. This happened to our fixture. Freeze its executable now; changing the external probe script does not require rebuilding it. For the new app, establish a consistent signing/launch approach early and verify permission after updates. Keep a visible Stop control, and request microphone or screenshot capture access only when that feature is actually tested.

## 5. User flow and responsibility of each component

| Step | Component | What it must establish |
| --- | --- | --- |
| User asks for help | Utter dictates into a focused ordinary text field | Display the actual received question. Empty input asks for retry; typed input remains a fallback. |
| Observe the chosen app | Local macOS Accessibility reader | Visible controls, labels, roles, bounds, app/window identity and a fresh snapshot ID. Scope collection to the selected foreground app. |
| Decide one next step | Proposed Sarvam text planner | Select an existing control ID or return clarify/unsupported/completion proposal. No invented screen coordinates. |
| Validate selection | Local deterministic code | Check control ID, snapshot freshness, foreground window and visible bounds before showing guidance. |
| Show where to click | Local transparent overlay | Convert screen points correctly, highlight the selected rectangle, allow clicks through and support Stop. |
| Perform the action | Human user | User retains control in the first version. Automatic clicking is deferred. |
| Decide whether to continue | Fresh observation and task-specific check | Detect the expected visible change. A click or model claim does not prove success. |
| Optional spoken explanation | Text first; local Mac voice or later Sarvam Bulbul | TTS failure leaves readable guidance and does not block the core task. |
| Optional engineering repair | Later Devin job against our owned repository | Reproducible defect, reviewed case, bounded session, traceable PR, reviewed change and replayed verification. |

The Accessibility path does not need screenshot understanding for controls it can name. Holo replacement is first a **text planning/candidate-selection experiment**. Sarvam speech transcription, text reasoning and visual localization are separate capabilities. A document-vision API or an image-capable model listing does not prove accurate UI pointing. Screenshot/OCR fallback should be a separate experiment only if the chosen application's Accessibility data is insufficient.

## 6. What the original project taught us

The inspected [H Companion source](https://github.com/Tooom123/H-Company_Computer-Use_Hackathon/tree/287c4c1bd64f58869fc52db17aaa63f62744dbcb) has multiple paths. Its Finder launcher is a **read-only coach for Devin Desktop**, using `desktop/` Electron UI, autonomy zero, automatic repair disabled and a mock repair provider. The separate `app/` UI is another interface; avoid rebuilding both by accident.

Original request flow: push-to-talk → Gladia transcription → local Accessibility candidates → Holo next-step planning → overlay and narration → observe interaction → attempt outcome verification. Browser paths can have Holo screenshot fallback; native Devin coaching disables that fallback and screenshot verification. The native reader uses top-left-origin screen points and excludes editable input values; the broader browser path can read input values. Preserve the desired privacy behavior explicitly.

H authentication is constructed in backend/planner code. Swapping an API key or URL does not remove H dependencies. Even a `--mock` CLI run can start input listeners, and usage paths can make service requests. This is why we tested individual modules instead of running the whole original CLI.

The support backend can request a Devin repair for an approved repo. That does not establish a completed merge/deploy/retest workflow. “Devin Desktop is the app being explained” and “Devin is repairing code” are different roles.

## 7. Rebuild stages — complete one before the next

### A. Reader and pointer first

Finish the fixture tests before building a large app shell. With a fresh reader run, require Export PDF, Save draft, Preview invoice and Use question to be found; require valid positive rectangles and exclusion of the sentinel customer-field value. Record the result and timestamp.

Then point to Export PDF using its fresh reader bounds. Compare to the fixture's independently supplied own-view bounds, observe the highlight and manually click through it. These steps passed on 21 November; see the current-state table and verification summary. The fallback that uses fixture-supplied geometry is useful for an isolated pointer check; label it accordingly. **It cannot count as an Accessibility pass.**

Exit: reader evidence plus live correct alignment and manual click-through evidence. A renderer flag alone is insufficient. Current scope is a stationary main-display window; moving-window, scrolling and multi-monitor behavior need explicit later checks.

### B. Utter input

Dictate a real question into the field using the user's existing Utter shortcut. Submit it and inspect the received text. Reading historical transcripts or typing the intended sentence does not verify dictation. Input verification is separate from semantic planning.

Exit: actual dictated text arrives correctly and blank input has a useful retry path. No separate speech account is needed for this stage.

### C. Sarvam chooses controls

Define a small sanitized snapshot set and expected answers before connecting the live UI. Include similar labels, a missing control, a stale snapshot and an ambiguous request. Use a provider-neutral response containing a decision, snapshot ID, optional control ID and short instruction. Validate the returned control locally.

Measure correct selections, rejected invalid/stale IDs and latency. Preserve English control labels inside Malayalam-English explanations. Verify current Sarvam model/API support from official docs when implementing; earlier model names and pricing are research snapshots, not guaranteed current configuration.

Exit: demonstrated selection accuracy on the agreed cases, with failures surfaced honestly. No H client construction or H network fallback in the active path.

### D. One complete task in one app

Connect the verified pieces: Utter/typed question → current snapshot → Sarvam decision → validated pointer → human click → refreshed snapshot → positive completion check. A compact native macOS shell is a reasonable first choice given our working AppKit fixture; choose one UI stack and keep the first build small.

Invalidate guidance when the app/window changes or the target moves. Provide Stop and a clear unsupported state. Use the owned demo app for repeatable tasks and known expected results before claiming general desktop coverage.

Exit: finish two or three chosen tasks from different starting states; show a safe failure when a control is missing or permissions disappear. Record observation, planning and display latency separately.

### E. Add sponsor depth only after the core works

If useful, add Sarvam speech input (Saaras) or output (Bulbul) through separate adapters, preserving actual transcript display and interruption. Keep Utter as the working input fallback. Test real mixed-language microphone input; synthetic audio alone misses failures.

Devin can assist implementation/testing if authorized. An in-product repair workflow is a separate feature: restrict to an owned connected repository, distinguish product defects from reader/planner/permission failures, submit a reviewed case, persist one case-to-session mapping, show progress and PR evidence, review the change, then rerun the original failed task. Keep repair work asynchronous; immediate guidance must not wait several minutes for a PR.

Exit: show the actual provider call or engineering session and its verified result. Mark mock, recorded and live evidence distinctly.

## 8. Avoid repeating these mistakes

| What wasted time or would mislead us | Better path |
| --- | --- |
| Repeating an outdated macOS permission path | Read the OS version, inspect the actual screen and verify current vendor docs once. |
| Treating one app's permission as a grant for every helper | Test the exact launch/process path; report the specific denied process. |
| Calling component rendering an end-to-end success | Separate renderer, live geometry, manual click-through, dictation, planning and task-completion evidence. |
| Assuming the submitted question drives today's pointer | Today's pointer is fixed to Export PDF. Implement and test semantic selection explicitly. |
| Spending the first hours on unavailable H signup | Keep the active implementation independent of H credentials. |
| Installing/running the whole reference app to test one feature | Use the minimal component harness and add dependencies only for the next required feature. |
| Building voice, UI polish, gaze, repair and automation together | Follow stages A–E; keep human clicks and one target app first. |
| Treating Sarvam STT or document vision as a Holo replacement | Evaluate text candidate selection first; validate visual localization separately if needed. |
| Promising a bug repair because a PR exists | Reproduce, inspect the patch and verify the original condition on the resulting revision. |
| Reopening every winner repo on every turn | Read this handoff, then the relevant focused source study only when that branch of work begins. |

The earlier security review was **partial and static**, not a blanket “safe to run” certificate. It identified two medium findings in optional bare-server paths: unauthenticated task creation/approval, and caller-controlled report paths escaping the run directory. They were not runtime-reproduced or repaired. Keep that server out of the prototype; if a local API is introduced, authenticate it and constrain generated report paths. Keep service keys outside renderer/public configuration and exclude private screen content from shared traces.

The inspected winner snapshots did not establish a reusable top-level license for all product code. Build our own implementation; verify applicable licenses before copying code into a distributed submission. Downloadability does not establish reuse permission.

## 9. Research to reuse on demand

These are existing research snapshots; inspect their cited source and event-day commit if a specific claim matters. We did not execute the other winners locally.

| Reference | Lesson relevant to our app |
| --- | --- |
| H Companion, first overall at H Company × 42AI Paris | Grounded guidance and a local overlay; multiple execution paths must be distinguished. [Repo](https://github.com/Tooom123/H-Company_Computer-Use_Hackathon) · [demo](https://www.youtube.com/watch?v=jZL4C3UOBNY) |
| SADAK, Epoch third | Short voice turns; secondary grading outside the spoken response path. [Repo](https://github.com/mittal-parth/sadak) |
| Sahayak, Epoch second | Explicit action results, missing-information handling and readable output when TTS fails. [Repo](https://github.com/akashmeruva9/sahayak-ucxp-sarvam) |
| Quotra, BuildIn' Hours first | Visible transcript and evidence; real-microphone testing exposed failures clean synthetic tests missed. `quotra-sarvam-lane` is the studied Sarvam component, not proof that it is the entire product repo. [Repo](https://github.com/jenineeuq/quotra-sarvam-lane) |
| Player Two | Reproducible defect, independent verification and asynchronous Devin repair/replay; published timing is author evidence. [Repo](https://github.com/kaktamsdengami/player-two) |
| Mulligan | Typed actions and explicit before/after state checks; distinguish demo modes and test evidence from an independently observed live Devin run. [Repo](https://github.com/Manas-33/mulligan) |

Read [H Companion code study](outputs/h-companion-code-study.md) when investigating original modules or service construction; read [Sarvam winner study](outputs/sarvam-winning-code-study.md) when implementing language/voice behavior; read [Devin winner study](outputs/devin-winning-code-study.md) when implementing repair evidence and replay.

Read [the high-level architecture proposal](outputs/h-companion-sarvam-high-level-plan.md) for additional design context; its earlier typed-input recommendation is superseded by the user's current choice of Utter for input. Read [partial security findings](/Users/abinsaji/Documents/Codex/2026-11-08/https-www-hackathoni-in-https-www/outputs/h-companion-security-review-2026-11-21.md) before considering the original server/full runtime. Read [event, award and demo sources](outputs/sarvam-devin-hackathon-winners-2026-11-20.md) only when an event/result claim needs checking.

The old studies accurately describe work done at their own dates; statements such as “no dependencies installed” there refer to that earlier research stage. This document and current test artifacts govern the later component-test status.

## 10. Paste this into Conductor / Claude when ready

> Read `building companion app.md` in this workspace as the implementation handoff. Build a small macOS companion from scratch: Utter/typed question, selected-app Accessibility snapshot, Sarvam next-step selection, locally validated control ID, pointer, human click, fresh observation and positive task-completion evidence. Keep explanations short and work one component at a time.
>
> Start with the current evidence: stage A passed for the stationary main-display fixture. The original reader, independent live target geometry, visual alignment and manual click-through are verified. Inspect `verification-summary.json` for preserved evidence. Proceed to real Utter dictation, which is still untested, then evaluate Sarvam candidate selection separately. Keep the compiled fixture unchanged. macOS is 27.2.1: use Privacy & Security → Device Control and Data Access. Removing/re-adding only the current fixture fixed a stale code-hash requirement; Python needed no separate grant. A separate command-automation helper remains denied assistive access, so do not assume it can drive UI tests.
>
> Use the pinned H Companion clone and focused research notes as references. Keep the new runtime free of H Company authentication and avoid the original full CLI/server. Today's fixture pointer is fixed to Export PDF and its question field is not connected to a planner. Do not present that as semantic assistance. Choose one real target app and a few tasks before expanding scope.
>
> Maintain this handoff after each meaningful result: what changed, exact evidence, what remains unverified and the next concrete action. Read focused source files instead of repeatedly ingesting all logs/repos. Use one main builder and bounded reviews when useful. Keep credentials private and keep mocks/recordings visibly distinct from live integration evidence. Add voice-provider changes or Devin runtime repair only after the core flow works and the current hackathon brief justifies them.
