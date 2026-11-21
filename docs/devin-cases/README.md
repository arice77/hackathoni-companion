# Devin repair cases

The case tool demonstrates a developer-approved repair from a synthetic reproduction through review of an open PR. Its default adapter applies a known fix from the team and labels the real GitHub PR **SIMULATED Devin**. It makes no Devin API calls in that mode.

## Reproduce the case locally

```sh
.venv/bin/python -m tools.devin_case.replay make-it-faster 329cc68
.venv/bin/python -m tools.devin_case.replay make-it-faster 93c6dea
```

At `329cc68` the pinned player snapshot yields a clarification, no local intent, and one blocked intent call. At `93c6dea` it yields a pointer at Settings, a local speed intent for 1.25×, and zero intent calls. The command checks out the requested commit in a disposable detached worktree, launches isolated Python with a scrubbed environment, and blocks Sarvam and outbound connections in the replay. Python isolation is not an operating-system sandbox. Run the replay against trusted team revisions.

## Run the simulation

```sh
.venv/bin/python -m tools.devin_case.cli make-it-faster
```

Check the printed baseline evidence, then type `fix make-it-faster 329cc68` at the prompt. The case tool publishes the pinned base to `devin-case/make-it-faster`, cherry-picks the builder's fix and tests onto a separate branch, and opens a PR into the case branch. It replays the exact GitHub PR head and writes `<case-id>-<mode>-<date>.md` here. Review and merge are manual on GitHub.

The gitignored `tools/devin_case/state.json` records one attempt per case and mode in this checkout. Rerunning resumes the saved session. If a start was reserved but no ID was saved, check the remote outcome before changing the state file.

## Live adapter

`--live` opts into a real, paid Devin session. Set `DEVIN_API_KEY` in the environment or repo-root `.env` after connecting the repository. A `cog_` key also requires `DEVIN_ORG_ID` and selects API v3. Legacy `apk_` keys use the v1 session endpoints. Both use a five-ACU cap. The tool saves the session ID before polling every 15 seconds for up to 30 minutes. The case branch is specified in the prompt, and GitHub must confirm that the open PR targets that branch at the pinned base. [Devin authentication](https://docs.devin.ai/api-reference/authentication) · [v3 session creation](https://docs.devin.ai/api-reference/v3/sessions/post-organizations-sessions) · [v3 session details](https://docs.devin.ai/api-reference/v3/sessions/get-organizations-session) · [v1 session creation](https://docs.devin.ai/api-reference/v1/sessions/create-a-new-devin-session) · [v1 session details](https://docs.devin.ai/api-reference/v1/sessions/retrieve-details-about-an-existing-session)

This flow adapts Player Two’s case evidence, approval and independent replay pattern to the Companion. [Player Two client](https://github.com/kaktamsdengami/player-two/blob/84a947382abd6ee04226b027b3fcf823960f6808/devin/client.py#L36-L55) · [Player Two verification loop](https://github.com/kaktamsdengami/player-two/blob/84a947382abd6ee04226b027b3fcf823960f6808/agents/fix_loop.py#L114-L148)
