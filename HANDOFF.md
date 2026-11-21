# Start here in Conductor

State as of 21 Nov 2026, ~20:30 IST. Coordinator branch: `arice77/hackathoni-companion-build-coordinate` (local only, not pushed).
Process: `/conductor-orchestrator` (Opus orchestrates and reviews; Codex Sol/Astra build; Sonnet QA). QA: `companion-qa` skill.
Live plan and owners: [docs/build-board.md](docs/build-board.md).

## Direction (Abin)

Get the basics right before choosing the problem: the companion guides a person **on websites**, they ask by **voice in
Malayalam or English**, and the overlay text and spoken reply follow their language preference. The GST GSTR-3B demo
(Kerala shop owner, regular scheme, under ₹5 crore, monthly filer) is parked until the basics work.

## What works (with evidence)

| Piece | Evidence | Label |
|---|---|---|
| Accessibility reader, native apps | `scripts/qa/checks/aims_reader_live.py`, green | live-machine |
| Reader on web pages | Safari practice page: step ids via `AXDOMIdentifier`, no browser chrome, no typed values, 75–113 ms (`docs/web-support.md`) | live-machine |
| Brave | Readable only in an isolated profile launched with `--force-renderer-accessibility=complete` | live-machine |
| Scripted planner + validator + loop | AIMS e2e: 15 steps, every pointer validated, completion via status text + fresh receipt; green 3× in a row | live-machine (driver clicks) |
| Sketch overlay (Plum, Shantell Sans, Malayalam Sangam MN fallback) | click-through and alignment asserted on a self-owned window; renders in `docs/overlay-renders/` | live-machine + automated |
| Sarvam voice | Key verified (chat reply in Malayalam). Saaras v4 transcribe/translate + Bulbul round trip, both languages (`docs/sarvam-voice.md`) | live (synthetic audio) |
| Voice in the panel | Spoken Malayalam instruction on the Safari practice page, sketch pointer on "Business Name" (1 TTS call) | live-machine |
| Language switch | `--lang ml|en` and a panel switch; one language shown and spoken | live-machine |

## Not yet verified / open issues

- **No person has used it yet.** Real microphone (needs Abin to allow the macOS prompt), pointer alignment by eye, click-through by hand, Malayalam wording by a native speaker.
- **The web reader only accepts our practice page** (title + local URL match). Reading any page in the front browser window, on request, is next.
- **The planner is scripted.** A Sarvam LLM planner for pages without step scripts is being built and evaluated.
- **Overlay taste:** outline too clean, note should be slightly crooked with a shadow, closer to the target. Being fixed.
- **Hackathon rule risk:** the field guide says "build a project with Devin" (`.context/hackathon-brief.md`). Confirm with the organisers.
- Utter dictation into the panel field is untested.

## Run it

```sh
./scripts/bootstrap.sh                                   # once per worktree
./scripts/open_web_practice.sh                           # Safari practice page
.venv/bin/python -m companion.app --task web_practice    # add --lang en, --mute, --planner sarvam
.venv/bin/python scripts/qa/run.py                       # full QA (silent: spends no credits)
```

Run from an Accessibility-trusted process (a Conductor terminal on this Mac). `SARVAM_API_KEY` lives in the git-ignored
`.env`; never print or commit it. Credits: track on the board.
