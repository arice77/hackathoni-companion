# Start here in Conductor

State as of **22 Nov 2026, 02:10 IST**. Coordinator branch `arice77/hackathoni-companion-build-coordinate`
(local only, not pushed). Orchestrator detail (agents, session ids, what to review next):
`.context/orchestrator-state.md` (git-ignored, in the coordinator worktree). Ledger of features, bugs, decisions
and credits: [docs/build-board.md](docs/build-board.md). Process: `/conductor-orchestrator` skill (Opus
orchestrates and reviews; Codex Sol/Astra build; Sonnet QA with the `companion-qa` skill).

## What we're building

Track 02 "Voice & Language: Beyond English" (HackaThoni, Alappuzha). A macOS companion that makes websites
usable for **Malayalis who aren't comfortable with tech (parents, grandparents)**:

1. They ask by voice, in Malayalam or English (Sarvam Saaras v4 speech-to-text; Malayalam → English translate).
2. The Accessibility reader reads the page in Safari (no typed values, no passwords, URLs reduced to host;
   Gmail reduced to UI chrome only).
3. Site packs (KSEB, YouTube, Gmail) plus a form planner plan the steps in code; the Sarvam LLM handles
   intent and wording only.
4. A hand-drawn Plum overlay points at the exact control, and a cream "paper note" panel shows the step. Bulbul
   speaks it in the chosen language.
5. The person clicks. The companion re-reads the screen and moves on.

## What works (evidence)

| Piece | Evidence | Label |
|---|---|---|
| KSEB Quick Pay pack | follow-the-pointer on the practice copy, 2× green (runs/qa/20261122-014339) | live-machine (practice copy) |
| Generic forms (pizza) | optional units offered, Skip, "Next…", complete (same run) | live-machine |
| Gmail compose → send | passed on Abin's real account (runs/qa/20261122-012836); 1 test mail to his own address | live |
| YouTube "play <song>" (Malayalam), with ads | official Darshana video, pre-roll ad skipped (runs/qa/20261122-020709) | live |
| YouTube "make it slower" | Settings → Playback speed → − ×5 with countdown → 0.75×, restored (same run) | live |
| New panel (Direction A "Paper note") | 12 renders in `docs/panel-renders/`; Safari keeps focus; QA green with it | live-machine |
| Sarvam voice | Saaras/Bulbul round trip in both languages; mic helper | live (synthetic audio) |
| Default QA suite | 20 pass / 0 fail on the coordinator branch | automated + live-machine |

## Not done / open

- YouTube Malayalam subtitles not yet walked live. Gmail "Your email was sent" merged but not yet seen live.
- No person has done the full flows yet with the real mic. Malayalam wording needs a native speaker's review.
- **Devin rule**: the field guide says "build a project with Devin". Abin to confirm with the organisers.
- Demo script drafted: `docs/demo-script.md`. Option for a 4th site from the hosts' own projects: `.context/organiser-projects.md` (Abin to choose).

## Run it

```sh
./scripts/bootstrap.sh                                    # once per worktree
.venv/bin/python -m companion.app --task web_site         # KSEB / YouTube / Gmail in the front Safari window
.venv/bin/python -m companion.app --task web_practice     # local practice form (./scripts/open_web_practice.sh)
.venv/bin/python scripts/qa/run.py                        # default QA (no Sarvam calls)
QA_LIVE_SARVAM=1 .venv/bin/python scripts/qa/run.py kseb_follow pizza_follow   # live walks
```

Run from an Accessibility-trusted process (a Conductor terminal on this Mac). Secrets live only in the
git-ignored `.env` (`SARVAM_API_KEY`, `QA_GMAIL_TO`, `QA_GMAIL_ALLOWED`). Commit messages are plain: no AI
co-author lines.
