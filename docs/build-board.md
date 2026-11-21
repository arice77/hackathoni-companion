# Build board

> **Snapshot 22 Nov 02:10 IST:** KSEB, pizza and Gmail pass live; YouTube Q1 passes. YouTube ad handling,
> Settings retry, ad markers and Gmail "sent" wording merged (unit 207/0); YouTube passes live end to end (play with ad + make it slower to 0.75 with countdown), QA and orchestrator reruns.
> Panel revamp merged. Orchestrator state:
> `.context/orchestrator-state.md`.


Orchestrator: coordinator session (Opus) · Process: `/conductor-orchestrator` · QA: `companion-qa` skill.
Status words: planned · building · in QA · in review · merged · demo-ready.

## Product direction (Abin, 21 Nov ~23:45): Track 02 "Beyond English" (primary)

Make websites usable for Malayalis who aren't comfortable with tech (parents, grandparents). Malayalam first; other
languages mentioned in the demo only. Refine on three real sites, not "works on any website":

| Site | Parent tasks (draft) | Limits for tests |
|---|---|---|
| YouTube | search, play, Malayalam subtitles, full screen, slower speed, like, subscribe | like/subscribe/comment allowed (Abin, 22 Nov ~00:40); tests undo likes/subscriptions and delete test comments |
| Gmail (Abin's real account) | write, reply, search, attach | Send allowed only to Abin's own two addresses (exact spelling pending his confirmation), via `QA_GMAIL_TO` + `QA_GMAIL_ALLOWED`, max one per run; never delete/archive/mark; never log subjects, senders or bodies |
| KSEB Quick Pay (wss.kseb.in) | open Quick Pay, enter consumer number, see bill | stop at the captcha; never submit or pay |

Privacy note: on Gmail, on-screen subjects/senders become control labels and reach Sarvam in planner prompts.
Site packs must summarise message lists instead of sending rows. Probe in progress (web builder, `docs/site-probes.md`).

## Current focus (Abin, 21 Nov 2026, later): get the basics right first

1. The companion works on **web apps in a browser** (real tasks such as GST are websites). Safari is proven readable
   (orchestrator probe, live-machine); Chromium/Brave needs work and is tested only with a throwaway profile.
2. **Language preference, Malayalam or English**: the user speaks in it, the overlay and panel show it, the voice
   answers in it (Sarvam STT, Malayalam->English for matching English labels, Bulbul TTS). Panel switch and
   overlay language: done (coordinator). Voice: building.
3. The problem domain (GST or something else) is chosen **after** these basics work. The GST plan below is parked.

## Bugs from Abin's hands-on test (21 Nov ~22:50)

| Bug | Cause | Fix | Owner | Status |
|---|---|---|---|---|
| Every question after the first got the same refusal | app reused the background answer on an unchanged screen, ignoring the new question | new question clears the result; late answers dropped | coordinator | fixed + live-verified |
| Broad questions ("how do I use this site?", "help me fill this form") refused | planner policy too strict | orientation line + point at the first sensible step | Codex sol (planner) | fixed (9a41569), eval pass; needs Abin retest |
| Pizza size: "select Small", "select Medium", back and forth (and the whole-form misorder from the 23:05 retest) | reader reports no radio state; planner picks an option for the user | reader: radio `filled` + `group` label + group control filled when any option selected; planner: point at the whole choice set, list the options, user decides, move on once any is chosen | Codex sol (reader + planner) + coordinator | fixed: form plan in code (`companion/guidance.py`); pizza follow-the-pointer 8/8 in 2 consecutive orchestrator runs (runs/qa/20261122-000933, -000942); needs Abin retest |

### Retest 21 Nov ~23:05 (httpbin pizza form, `web_any`, "Can you help me fill this form?")
Failed: started at Delivery instructions, skipped Pizza Size, repeated "This is an order form" every step.
Why our checks missed it: each fix was tested alone on single or replayed snapshots; nothing walked a whole
real-shaped form by following the pointer. Orchestrator asked Abin to retest without running an integrated test first.
**New rule:** a feature isn't ready for Abin until a follow-the-pointer walk on a local copy of the real page passes,
run by the orchestrator. Fixes: planner (orientation once, one ordered step list incl. choice sets) + QA (local
`/pizza` copy, `drive_follow_pointer.py`, `pizza_follow_pointer_e2e.py`).

## Prior-art decisions (21 Nov ~23:15, report: `.context/prior-art-report.md`)

| # | Finding | Decision | Owner |
|---|---|---|---|
| 1 | Form plan + guidance session in code (units, stable keys, done on `filled` flip, intro once, separate completion) | adopt now | planner builder (`companion/guidance.py`) |
| 2 | Reading-order serialization with headings, nested choice sets, change markers | adopt now | planner builder |
| 3 | Visible-bbox clipping + "scroll down" signal (macapptree idea, MIT) | adopt now | web builder |
| 8 | Union-rect choice-set highlight + "Step 2 of 6" counter | next, after #1 | coordinator / overlay |
| 4 | Saaras `codemix` mode | next, after Abin's real-voice test | voice |
| 5–7 | Streaming barge-in, AXObserver window tracking, Chrome `AXManualAccessibility` | deferred | — |
| — | Shepherd / Intro.js / Skyvern code | idea-only (AGPL) | — |

### Retest 22 Nov ~00:15 (`runs/session-20261122-001418-3c4e76.jsonl`)
| Bug | Fix | Owner |
|---|---|---|
| Optional units (toppings, delivery time, instructions) skipped silently: my earlier policy, wrong for parents | offer every visible unit in order, mark optional, done when filled/skipped/a later unit filled; panel Skip button + spoken "skip" | planner builder + coordinator (Skip button done) + QA (test expectations) |
| "Start with" on every step | "Next, …" from step 2 | planner builder |
| KSEB: `clarify` instead of pointing at "Submit to see the bill" | wider primary-action detection; no mid-walk clarify | planner builder (with KSEB pack) |
| "Browser Accessibility did not respond in time" on real pages | larger budget, one retry, keep last good snapshot | web builder: merged (b0b1c9b): 750 ms deadline, retry, verified 1.5 s reuse; p95 YouTube 115 ms, Gmail 83 ms, KSEB 16 ms |

### Live site runs 22 Nov ~01:05 (QA)
| Site | Result | Next |
|---|---|---|
| YouTube Q1 (Malayalam "play Darshana") | PASS (2nd run picks "Darshana - Official Video Song") | done |
| YouTube Q2 ("play it slower") | FAIL ×3: opens Settings; menu reduced to 2 rows (likely during an ad) | ad-state guidance + reopen Settings if reduced (planner builder) |
| Gmail compose → send | **PASS** live (runs/qa/20261122-012836): Compose → To → Subject → Body → Attach skipped → Send; 1 test mail to Abin | say "sent" when Gmail shows "Message sent" (web builder) |

### Fixes merged 22 Nov ~01:51 (orchestrator review; unit 207/0)
| Commit | What | Review notes |
|---|---|---|
| 4eb0d64 (planner) | YouTube ads: point at Skip when enabled, else "The ad will finish in a few seconds"; no "playing" while ad markers show. Reduced Settings menu with no ad: wait 3 s, then one close-and-reopen pointer (`retry_at` cleared on every decide; fires once). Ad text sent to Sarvam only as fixed marker names | replay eval 37 cases / 122 decisions |
| 02d6576 (web) | Gmail: "Message sent" notice (fixed labels only: Message sent / Sending… / Undo) → complete "Your email was sent"; only counts if it appears after a draft was seen | no mail text retained |
| 49d4b42 (web) | Reader keeps YouTube static texts only when they match "Ad", "Sponsored", "Ad N of M" or an ad timer, as fixed labels, never pointable | compatible with planner markers |

Next: QA reruns `youtube_follow_pointer_e2e` once, then orchestrator reruns it before Abin retests.

QA rerun 22 Nov ~01:53 (runs/qa/20261122-015201): **FAIL at step 1**. A home-page display ad's "My Ad Centre" button was read as a player ad, so the guide said "wait for the ad" and never pointed at Search. Fix routed to planner builder: ad handling only in player context; feed/results ads ignored.

- 5652053 (planner) merged: ad handling only near the player. 4d215de (planner) merged: natural speed/captions/play/pause/full-screen phrases in Malayalam and English (61 replays / 152 decisions).
- QA rerun ~02:00 (runs/qa/20261122-015556): **Q1 PASS with an ad** (Skip pointed and pressed). Q2: Settings → Playback speed OK, then stalled: YouTube's speed panel has **no 0.75 preset** (presets 1.0/1.25/1.5/2.0/3.0, ±0.05 buttons, unlabelled slider). Decision: point at "−" with a countdown ("press N more times"), never at the slider (dragging is hard for older users). Reader exposes the slider value as fixed "Playback speed slider <n>" (web builder); planner counts down (planner builder). QA driver fixed (aec2be7).
- c2bb575 (reader: speed slider value), e437e68 (planner: "Press − to slow down (N more times)"), 8da979b (orchestrator: slider has no identifier so value changes re-plan) merged; unit 212/0.
- **YouTube PASS live, both questions.** QA (runs/qa/20261122-020602) and orchestrator rerun (runs/qa/20261122-020709): 10 pass / 0 fail / 1 needs-human. Q1 Malayalam "play Darshana" with a pre-roll ad (wait → Skip → playing); Q2 "make it slower": Settings → Playback speed → − ×5 with countdown 5,4,3,2,1 → "The video is set to 0.75×"; speed restored to Normal, Settings closed.

## Site packs (started 22 Nov ~00:15)

| Piece | Owner | Status |
|---|---|---|
| Site-pack framework + KSEB Quick Pay pack + `web_site` task; optional units offered, Skip, "Next…" | Codex sol (planner) | merged (f8af958). Orchestrator runs ×2: KSEB 8/8, pizza 11/11 (runs/qa/20261122-003028, -003100); eval 78/78 |
| Local KSEB Quick Pay copy + KSEB follow-pointer check; flake hardening | Sonnet QA | building |
| Gmail privacy gate (chrome-only labels, inbox = one 'Inbox: N messages' control), To in compose, Reply on a Sent conversation; YouTube sliders + Settings menu items (speed, quality, subtitles) | Codex sol (web) | merged (8b0d1d8, 28ad214) |
| YouTube site pack (search+play, full screen, pause/mute, Malayalam subtitles, speed) + generic `start_guidance` hook | Codex sol (planner) | merged (24f4fe9 … a0872e7); 29 replay cases / 81 decisions. First live run picked a channel → reader marker merged (8ea4463); live rerun queued with QA |
| Gmail site pack (compose, reply, search, attach) | Codex sol (web) | merged (180cf8a); live walk may Send once to Abin's allowlisted address; QA running it |

Commit messages: AI co-author trailers stripped from all local branches on 22 Nov 00:13 (message-only rewrite,
trees unchanged, base still origin/main e542f90). Backup refs in refs/original until Abin confirms.

## Panel revamp (decided 22 Nov ~01:25) — merged 22 Nov ~01:42 (b8f19c0, e9a49ce); default QA 20/0, live KSEB+pizza 21/21 with it

Research: `.context/ui-research/` (3 mockups). Decision: **A "Paper note", with restraint**. Rough pen only on panel
edge, mic, step card and primary action; flat cream inputs/Skip/Stop; 96 pt idle mic → 56 pt while guiding; step text
26–28 pt; replay in card; "on screen: <label>" chip; wide plum "new question" button on done (from C); dev timings
behind ⋯. Builder: Codex astra (`companion/panel/**`, limited `app.py` edits). Must keep `companion-skip`, first
AXTextField, and an "Ask"/"ചോദിക്കൂ" button in every state; must not steal focus from Safari.

## Shared-Mac rule

Abin uses this Mac during the build. Live checks fail when he moves windows; rerun on an idle screen before calling a
failure a product bug (21 Nov 22:35: 4 fails while he worked, 0 on the idle rerun). Ask before long live runs.

## Sarvam credits

Organiser-provided: 600 credits (Abin, 21 Nov). Abin posts the remaining balance from the dashboard
(https://indus.sarvam.ai/rate-limits) from time to time; log it here with the time. Every agent that calls Sarvam
reports how many calls it made, by API. Rate limits: 60 req/min for speech-to-text, text-to-speech and translate.
Both Sarvam MCPs (`sarvam`, `sarvam-docs`) are installed at user scope for new Claude sessions.

| Time (IST) | Balance | Source |
|---|---|---|
| 21 Nov 20:10 | key verified with 1 chat call | orchestrator |
| 21 Nov 20:40 | ~48 calls used so far: 1 chat (key check), 5 voice smoke, 1 TTS (panel test), 39 planner eval, ~2 planner live | agents' reports; Abin to post dashboard balance |
| 21 Nov ~21:20 | **596 of 600 left** (~1 credit for ~75 calls since 597: about 0.013 credit per call) | Abin, dashboard |
| 21 Nov 21:15 | +68 planner calls, +5 voice smoke, +2 live httpbin (chat + TTS) | agents + orchestrator |
| 21 Nov ~20:45 | **597 of 600 left** (~3 credits for ~48 calls: chat, STT, TTS are cheap; budget is not a constraint for testing) | Abin, dashboard |

## Parked: GST hero demo (decided earlier on 21 Nov, on hold)

**One person:** a Kerala shop owner (e.g. a hardware or textile shop in Alappuzha) on the GST
**regular scheme**, turnover **under ₹5 crore**, who files **GSTR-3B monthly** because B2B customers
want their input tax credit each month. The accountant usually prepares the numbers; the owner, or
a family member, wants to do the filing or check it on the shop computer. QRMP quarterly filers see
the same GSTR-3B screens, so the demo covers them too.

**One task:** file this month's GSTR-3B on a practice copy of the GST portal, guided in Malayalam:
Returns Dashboard → choose financial year and period → GSTR-3B "Prepare Online" → check the
auto-filled sales (Table 3.1) → check input tax credit against GSTR-2B (Table 4) → save → proceed to
payment and offset the liability → reach the file step (EVC/OTP), where training ends and nothing is filed.

**The companion explains, the owner decides.** It says in Malayalam what each table means and points
at the control. It never computes tax or tells the owner what number to enter; numbers come from the
owner's (synthetic) books.

**Out of scope:** GSTR-1 invoice entry, IMS accept/reject, e-invoice, e-way bills, composition
(CMP-08/GSTR-4), annual returns, refunds, real login, tax advice.

**Facts to verify from official GSTN sources before they appear on screen or in the pitch:**
GSTR-3B screen labels and order (GST portal user manual), the July 2025 lock on auto-filled Table 3
values (corrections via GSTR-1A), the QRMP ₹5 crore limit, the Kerala taxpayer count.

**Pitch numbers (checked so far):** 52.6% of Indian MSMEs find choosing digital tools difficult;
46.2% fully offline (India SME Forum, Dec 2025, n=7,835, sampling to confirm). Kerala adults: 26.4%
can create a document, 49.4% can email (MoSPI CMS 2025). No survey shows English causes the difficulty.

## Open risk: "build with Devin"

The official field guide says "Bring your own idea and build a project with Devin" (`.context/hackathon-brief.md`).
We build with Claude and Codex. Abin to confirm with organisers whether Devin must do the building, and whether
Sarvam must be called at runtime for the Sarvam prize (we do call it at runtime: speech in, speech out).

## Features

| Feature | Status | Owner | Evidence / next |
|---|---|---|---|
| Reader, scripted planner, validator, loop | merged | coordinator | QA green on merged tree (runs/qa/20261121-201515) |
| QA skill + runner | merged, growing | Sonnet QA | Web, overlay, opt-in voice checks + machine-wide lock; merged suite 18 pass / 0 fail |
| Web reader (any page in the front Safari window, on request; Brave isolated) | merged (9ea4e8e) | Codex sol | httpbin form: 12 controls, ~66 ms; Wikipedia 23 controls ~74 ms; passwords skipped; URLs kept to host; worktree-scoped fixtures |
| Sketch overlay | merged incl. taste pass (fc95633) | Codex astra | Offset rough strokes, 2° note with shadow, short arrow. Nit: Malayalam glyphs read slightly smaller than Latin |
| Sarvam voice (Saaras v4 ml/en + translate, Bulbul, mic helper) | merged + wired into panel | Codex sol + coordinator | Live: Malayalam reply spoken on Safari practice page. Real mic needs Abin to allow the macOS prompt |
| Language preference (panel + overlay + voice) | merged | coordinator | `--lang ml|en`, switch in panel |
| Sarvam planner (LLM picks the control on any page) | merged (ccaa970) | Codex sol + coordinator (async in app) | 28/30 exact in 2 runs, 0 unknown ids, p50 ~550 ms; Safari practice walk 8/8 to complete; live on httpbin: Malayalam question → "Customer name:". Now: missing control → unsupported, ambiguous → clarify (all cases pass); 37/41 and 39/41; Wikipedia Search correct. Completion detected locally (ae74bd1). Latest: 69/69 exact in 2 runs, 0 malformed, 0 unknown ids |
| AIMS fixture | reference | coordinator | regression target in QA |
| GST practice portal | parked | — | — |

## Organiser-project option (research 22 Nov ~02:08, `.context/organiser-projects.md`)

Abin asked for options for a 4th demo site built/promoted by the HackaThoni hosts. Not started; Abin decides.
Candidates: Kochi Buzz (kochi.buzz, host Vaishakh Suresh), GasUndo (gasundo.live, hosts Vaishakh + Viswanatha),
mashi.guru (Malayalam fonts, Viswanatha). None tested in Safari / our reader yet.

## Live runs 22 Nov ~03:00 (Mac free; QA + GasUndo builder)
| Check | Result | Run |
|---|---|---|
| YouTube player controls (mute, pause, resume, faster 1.25, full screen pointed + "Press Esc"; subtitles unavailable on this video) | PASS 13/0 (tidy-up read back) | runs/qa/20261122-025719 |
| YouTube follow-pointer (driver regression) | PASS 11/0 | runs/qa/20261122-025812 |
| Gmail compose → Send → "Your email was sent" | PASS 7/0 (2 test mails to the allowlisted address across 2 runs; first run's driver crashed after sending) | runs/qa/20261122-025950 |
| GasUndo Ernakulam → Search → Bektash Kakkanad → status read, stale-report wording | PASS (live Safari) | port-louis runs/qa/20261122-030324 |
| YouTube Abin's utterances | FLAKY: intent call unstable ("make it faster" → none 5/5), home feed "scroll down" then silent, a wrong pick ("Nagumo … Darshana") | …025345, …030011, …030234 → planner builder fixing (local phrases first, ask when unclear, home→Search, title-first ranking) |

GasUndo pack merged (122ea48, 5ebe19e, 11a9b38); demo script now opens with GasUndo (71d6eb1). Pushed to GitHub main.

## Devin bug-repair case (decided 22 Nov ~03:40, grill with recommended answers, Abin: "do whatever is best")
Internal QA tool modelled on Player Two (outputs/devin-winning-code-study.md), not part of the companion app.
Case: real baseline "make it faster" on a synthetic player screen fails at 329cc68 (no local intent; live intent call none 5/5), passes at 93c6dea.
Flow: replay at base → developer approves the case → Devin adapter → PR into `devin-case/make-it-faster` (never main) → same replay at the PR head → review card in docs/devin-cases/. Merge stays manual.
Mode: SIMULATED by default (a real PR with our builder's 93c6dea patch, labelled "[SIMULATED Devin]"); LiveDevin behind `--live`, after checking the current API and credits. No DEVIN_API_KEY yet.
Builder: web builder (Codex sol), new files in tools/devin_case/. Hindi + Kannada languages: panel builder (Codex astra), offline only.

### Devin case: simulated rehearsal 22 Nov ~03:42
PR #1 [SIMULATED Devin] https://github.com/arice77/hackathoni-companion/pull/1 (base `devin-case/make-it-faster`, open for review).
Replay `make-it-faster`: 329cc68 FAIL (clarify, no target, 1 intent call) → PR head edd27ae PASS (Settings pointer, local 1.25×, 0 intent calls). Re-verified independently by the orchestrator.
Record: docs/devin-cases/make-it-faster-2026-11-22.md. Live run pending: Abin confirms the GitHub repo connection in Devin + credits, then types the live approval himself.
Also merged: Hindi + Kannada (fa1f7e0, offline-tested), pitch script docs/pitch-script.md (0c7e84c + 21b5dcb), YouTube utterances: zero intent calls in all runs; last run 3/3 pairs pass.

### Devin case: LIVE run 22 Nov ~03:48 (Abin approved; repo connected, $20 credit, 5-ACU cap)
Devin session devin-7ce62d4e… (API v1) opened PR #2 https://github.com/arice77/hackathoni-companion/pull/2 by `app/devin-ai-integration`, about 1 minute after start. +16/-1: adds "make it faster" to the local faster phrases + a unit test.
Replay `make-it-faster`: 329cc68 FAIL (1 intent call) → PR head 68090ec PASS (Settings pointer, local 1.25×, 0 intent calls). Re-verified independently by the orchestrator. Open for Abin's review/merge into `devin-case/make-it-faster`.
