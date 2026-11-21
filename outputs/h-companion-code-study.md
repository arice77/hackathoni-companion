# H Companion: code study, accounts and adaptation points

Checked 20 November 2026. Only H Companion is cloned in the workspace, at `research-repos/h-companion`, commit `287c4c1bd64f58869fc52db17aaa63f62744dbcb` (8 November 2026). This is a static source study: no dependencies installed, launchers executed, API sessions created, or tests run. The other winners were inspected through public GitHub source.

## What the project actually contains

H Companion combines a user-facing desktop helper with a support backend. A user holds a shortcut, asks a question and receives spoken instructions with a pencil-style overlay marking the relevant control. Broader execution paths support guidance, takeover and agent-driven tasks. The support side stores cases, groups similar difficulties and can request a Devin repair for an approved repository. These are multiple execution paths, not one default configuration. [Repository](https://github.com/Tooom123/H-Company_Computer-Use_Hackathon/tree/287c4c1bd64f58869fc52db17aaa63f62744dbcb)

The most important discovery is the current Finder launcher. It starts a **read-only coach for the Devin Desktop application**, using the `desktop/` Electron UI, not the separate React `app/` UI. It forces autonomy zero, disables automatic fixing, uses a mock fix provider and defaults to the Mac's built-in speaking voice. In this path, Devin is the application being explained to the user; it is not automatically the coding agent repairing a bug. [Launcher](https://github.com/Tooom123/H-Company_Computer-Use_Hackathon/blob/287c4c1bd64f58869fc52db17aaa63f62744dbcb/scripts/start-devin-companion.py#L105) · [Pilot settings](https://github.com/Tooom123/H-Company_Computer-Use_Hackathon/blob/287c4c1bd64f58869fc52db17aaa63f62744dbcb/scripts/run-h-company-human.py#L80)

## How a spoken request travels through the code

1. `PushToTalk` captures microphone audio. Gladia streaming transcription is attempted first; prerecorded transcription provides a fallback. The temporary WAV is removed after processing. [voice.py](https://github.com/Tooom123/H-Company_Computer-Use_Hackathon/blob/287c4c1bd64f58869fc52db17aaa63f62744dbcb/agent/src/hcs_agent/voice.py#L556)
2. Native coaching bypasses the generic intent router. It preserves the user's question and selects the general Cognition guide. The broader non-coaching path separately uses a Holo router. [cli.py](https://github.com/Tooom123/H-Company_Computer-Use_Hackathon/blob/287c4c1bd64f58869fc52db17aaa63f62744dbcb/agent/src/hcs_agent/cli.py#L863)
3. macOS Accessibility supplies visible control names, roles and screen rectangles. Native mode limits collection to the expected foreground application's focused window. This is Accessibility data, not browser DOM access. [a11y.py](https://github.com/Tooom123/H-Company_Computer-Use_Hackathon/blob/287c4c1bd64f58869fc52db17aaa63f62744dbcb/agent/src/hcs_agent/a11y.py#L170)
4. The dynamic guide combines those candidates with scoped documentation and asks a text-based Holo planner to choose a control. It checks that the instruction and target agree and that the window has not changed while planning. [runner.py](https://github.com/Tooom123/H-Company_Computer-Use_Hackathon/blob/287c4c1bd64f58869fc52db17aaa63f62744dbcb/agent/src/hcs_agent/runner.py#L707)
5. The guide draws its overlay and speaks the instruction. Relevant user interaction or an explicit next command advances the process. A click is recorded as interaction, not proof the task succeeded. [Guide loop](https://github.com/Tooom123/H-Company_Computer-Use_Hackathon/blob/287c4c1bd64f58869fc52db17aaa63f62744dbcb/agent/src/hcs_agent/cli.py#L1506)
6. Reports distinguish what the user requested, what the agent declared and what verification observed. Optional background uploads send cases and events to the local support backend; the local report remains available if uploads fail. [Support uplink](https://github.com/Tooom123/H-Company_Computer-Use_Hackathon/blob/287c4c1bd64f58869fc52db17aaa63f62744dbcb/agent/src/hcs_agent/support.py#L40)

Browser-oriented paths can fall back from Accessibility to Holo screenshot grounding. Native Devin coaching deliberately disables that fallback. It also disables screenshot verification, so its current completion check can remain inconclusive and escalate. The broader browser verifier is another model check, not a deterministic external oracle. This qualifies the README's broad verified-results description. [Native boundaries](https://github.com/Tooom123/H-Company_Computer-Use_Hackathon/blob/287c4c1bd64f58869fc52db17aaa63f62744dbcb/agent/src/hcs_agent/backend.py#L701) · [Verification handling](https://github.com/Tooom123/H-Company_Computer-Use_Hackathon/blob/287c4c1bd64f58869fc52db17aaa63f62744dbcb/agent/src/hcs_agent/runner.py#L513)

## What Devin actually does in the repair backend

The separate `AutoFixer` accepts a case for software mapped to an allowed GitHub repository. Automatic triggering also requires a suspected-product-defect category and the auto-fix setting. The prompt includes the goal, observed failure, attempted steps and suspected cause. It asks Devin to reproduce the problem with a failing test, make a small fix, run tests and open a PR. A failure to reproduce should produce an explanation instead. [Prompt](https://github.com/Tooom123/H-Company_Computer-Use_Hackathon/blob/287c4c1bd64f58869fc52db17aaa63f62744dbcb/backend/src/hcs_backend/autofix.py#L66)

`DevinProvider` creates an API v3 organization session with a repository, structured output schema and configurable consumption cap. The backend polls it and surfaces PR links and questions awaiting an operator. This module does not itself merge, deploy and replay the user's task. Without credentials, its auto provider can use an explicitly labelled mock; the default Finder pilot fixes the provider to mock and disables auto-fix entirely. [Provider](https://github.com/Tooom123/H-Company_Computer-Use_Hackathon/blob/287c4c1bd64f58869fc52db17aaa63f62744dbcb/backend/src/hcs_backend/autofix.py#L123) · [Service](https://github.com/Tooom123/H-Company_Computer-Use_Hackathon/blob/287c4c1bd64f58869fc52db17aaa63f62744dbcb/backend/src/hcs_backend/autofix.py#L233)

The authors report an end-to-end test against a private sandbox with a planted date bug. Its private PR is not independently inspectable here. The public unit tests use fake providers and mocked network responses; they do not establish current account access or a live Devin run. [Backend documentation](https://github.com/Tooom123/H-Company_Computer-Use_Hackathon/blob/287c4c1bd64f58869fc52db17aaa63f62744dbcb/backend/README.md#auto-fix-with-devin-cognition) · [Tests](https://github.com/Tooom123/H-Company_Computer-Use_Hackathon/blob/287c4c1bd64f58869fc52db17aaa63f62744dbcb/backend/tests/test_autofix.py#L95)

## Accounts, free usage and local prerequisites

| Service | Required for what? | What is free or limited? |
|---|---|---|
| H Company | Real Holo planning/grounding; `HAI_API_KEY` or supported H login | H advertises a $0 Agents API plan with approximate session limits. Models API uses per-token pricing. The guide calls Models API too, so the Agents session allowance alone does not establish this app's free budget. Check the account's Models API allowance before a live run. |
| Gladia | Original microphone-to-text flow; `GLADIA_API_KEY` | Current public pricing offers €50 signup credits, followed by usage billing. |
| ElevenLabs | Optional alternative spoken output | Unnecessary for the basic Mac pilot: `make_speaker` supports local macOS `say` without an API account. |
| Devin | Real automated code-repair sessions; API credential, organization ID and connected repository access | Free and paid plans exist with quotas/credits. We have not verified which credentials or allowance your account has. Opening the native Devin coaching target is separate from authorizing API repairs. |
| Linkup | Optional external documentation search | Can be omitted; not needed merely to inspect the app or use its local knowledge path. |
| Stripe | Optional test billing demonstration | Not needed for assistance or the core prototype. |
| Sarvam | Not part of the original; proposed replacement voice/language layer | Sarvam's current docs advertise ₹100 signup credits for verified users. These are a starting allowance, not unlimited usage. |

Pricing checked 20 November 2026: [H Company](https://hcompany.ai/pricing) · [Gladia](https://www.gladia.io/pricing) · [Devin billing](https://docs.devin.ai/admin/billing) · [Devin API credentials](https://docs.devin.ai/api-reference/authentication) · [Sarvam credits](https://docs.sarvam.ai/api/getting-started/pricing). Original integration requirements: [.env.example](https://github.com/Tooom123/H-Company_Computer-Use_Hackathon/blob/287c4c1bd64f58869fc52db17aaa63f62744dbcb/.env.example). Local voice fallback: [speech.py](https://github.com/Tooom123/H-Company_Computer-Use_Hackathon/blob/287c4c1bd64f58869fc52db17aaa63f62744dbcb/agent/src/hcs_agent/speech.py#L330).

The source can be downloaded and studied without service accounts. Mock development paths are documented without H credentials. Live desktop use additionally needs macOS, Python 3.12+, its Python dependencies, Node/Electron and appropriate microphone/Accessibility permissions; screenshot paths also need screen capture permission. The Finder shortcut is tied to this checkout and is not a standalone packaged application. No root LICENSE file was found in the inspected snapshot. [Desktop setup](https://github.com/Tooom123/H-Company_Computer-Use_Hackathon/blob/287c4c1bd64f58869fc52db17aaa63f62744dbcb/desktop/README.md) · [Python dependencies](https://github.com/Tooom123/H-Company_Computer-Use_Hackathon/blob/287c4c1bd64f58869fc52db17aaa63f62744dbcb/agent/pyproject.toml)

## What a Sarvam version would actually require

These are proposed adaptations, not implemented changes:

- Replace the concrete Gladia transcription construction with a provider interface. Preserve streaming partials, finish/cancel, fallback and audio cleanup. An API-key substitution alone will not work.
- Add a Sarvam TTS provider at `make_speaker`. The existing synthesizer contract returns PCM audio bytes; preserve the existing playback interruption, caching and overlay timing. [Speech interface](https://github.com/Tooom123/H-Company_Computer-Use_Hackathon/blob/287c4c1bd64f58869fc52db17aaa63f62744dbcb/agent/src/hcs_agent/speech.py#L49)
- Choose the actual target application and guidance mode. The current French/English native Devin preset is unsuitable as the unchanged default for a Malayalam merchant demo.
- Treat replacing Holo as a separate problem from replacing the voice services. Accessibility candidate selection can use a text-model adapter, but screenshot grounding requires validated visual localization. Sarvam's documented Vision product focuses on document intelligence; its existence does not establish a drop-in computer-control replacement. [Sarvam Vision scope](https://docs.sarvam.ai/api/api-guides-tutorials/models/sarvam-vision)
- Keep internal control identities and reports canonical. The current support grouping tokenizer accepts Latin words and has English/French stopwords; it would discard Malayalam or Hindi blocker text. Either normalize internal reports into a shared language or change the tokenizer before expecting multilingual issue grouping. [grouping.py](https://github.com/Tooom123/H-Company_Computer-Use_Hackathon/blob/287c4c1bd64f58869fc52db17aaa63f62744dbcb/backend/src/hcs_backend/grouping.py#L32)
- Define completion checks for the chosen demo app. Preserve the separation between interaction, model declaration and observed outcome. A highlighted button or a click is not an invoice successfully saved.
- Add Devin as an asynchronous repair job against your own connected demo repository. Keep its session and PR state separate from the user's guidance session. The inspected backend provides a useful integration reference, not a completed repair/deploy/retest loop.

## Companion source studies

- [Sarvam-winning implementations](sarvam-winning-code-study.md): Sahayak, SADAK and Quotra.
- [Devin-winning implementations](devin-winning-code-study.md): Player Two and Mulligan.

The value to carry forward is the complete interaction: grounded instruction, user control, interruption, evidence, and a useful developer handoff. Merely changing voice providers would leave the original target, completion limits and repair configuration unresolved.
