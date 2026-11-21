# HackaThoni Companion

Local handoff for the overnight Alappuzha hackathon. Start with [the local research](outputs/alappuzha-problem-research-2026-11-21.md) and [the companion build notes](<building companion app.md>).

- The crop-loss application coach is the leading hypothesis. Pick the demo after checking where the real workflow stalls. The wage diary, houseboat receipt workflow, and ferry timetable are alternatives.
- The native component baseline passed Accessibility reading, live pointer alignment, and manual click-through on a controlled fixture. Utter dictation, Sarvam calls, and the complete application are pending.
- The selected sketch style is Plum `#674064`, roughness `1.9`, and playfulness `35`. The recorded [style settings](work/companion-style-preview/selected-style.json) and [verified visual preview](work/companion-style-preview/preview-selected.png) apply to the simulated screens.

The web style preview is self-contained. From the repository root, run:

```sh
python3 -m http.server "${CONDUCTOR_PORT:-8000}" --bind 127.0.0.1 --directory work/companion-style-preview
```

The native fixture sources and test evidence are in [work/companion-components](work/companion-components/README.md). To repeat the native test on this Mac, use the already registered fixture in the original workspace documented in the build notes. Its macOS permission was previously tied to the exact signed build. For a fresh environment, treat the existing probe as reference code that expects the pinned H Companion checkout, its own Python virtual environment, and a locally built test bundle.

In Conductor, choose the local project and start one coordinator chat using [HANDOFF.md](HANDOFF.md). The initial Git commit carries the selected notes, test evidence, fixture sources, and preview assets into any new worktree. Archived notes still link to some files in the original local workspace. The Git project starts without a remote.
