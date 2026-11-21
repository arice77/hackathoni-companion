# Sarvam planner

`SarvamPlanner(task)` implements the panel's `decide(question, snap) -> Decision` interface. The panel selects it with `--planner sarvam`. Pass `None` when calling the planner without a task. Named practice tasks contribute a goal, and all control selection comes from the supplied snapshot and question. The voice panel supplies the native question and its English translation together.

The request carries the question, optional task goal, and each control's `id`, `role`, `label`, `filled`, and `enabled`. Identifiers, app and window metadata, geometry, and editable values stay out of the request. The prompt treats screen labels as untrusted data, limits the reply to one next step, and instructs the model to decline decisions about payments, amounts, eligibility, and declarations.

The provider returns a strict schema with `kind`, `control_id`, `instruction_ml`, and `instruction_en`. For pointing instructions it writes `[CONTROL]` where the real label belongs. The adapter inserts the exact visible label in quotes in both languages. Unknown IDs, malformed replies, unavailable targets, and instructions that cannot be tied to the selected control return `unsupported`. The existing validator checks snapshot age, target presence, and on-window position.

For each active question, the planner caches decisions by window and the set of `(identifier or label, role, filled)` values. It also tracks visible label text, enabled states, and repeated controls. Safari uses status and enabled-state changes to mark progress after attachment and saving, so those changes need a fresh decision. On a cache hit the planner rebinds the target by identifier or by an unambiguous label and role and uses the current snapshot ID. Failed replies remain cached for that screen and question. Call logs in `runs/sarvam-planner-*.jsonl` contain model, timing, request ID, and outcome.

## Model choice

The default is **`sarvam-105b`** on `POST https://api.sarvam.ai/v2/chat/completions`, with `reasoning_effort: "none"` and a 256-token budget. The comparison uses `sarvam-105b-conversations` on `/v1/chat/completions`, the route documented in its model guide. Both routes accept `response_format` with `json_schema` and `strict: true`. The adapter reuses the voice adapter's standard-library transport and `api-subscription-key` authentication. API documentation checked 21 November 2026. [Sarvam models](https://docs.sarvam.ai/api/token-factory/models/sarvam-105b) · [Chat V2](https://docs.sarvam.ai/api-reference/chat/chat-completions-v2) · [Chat V1](https://docs.sarvam.ai/api-reference/chat/chat-completions-v1)

Both models tied on the full comparison. The flagship had the lower observed p95 and produced zero wrong valid targets. Conversations had the faster median and one wrong valid target, selecting “Apply for New” before the AIMS classification step. These are measurements on 17 cases per model.

## Fixture eval

`tests/fixtures/planner/screens.json` contains two AIMS and seven Safari practice snapshots captured using the Accessibility reader on 21 November 2026. Test-only AXPress advanced the AIMS training form and used the local browser fixture's sample details, sample document, declaration, and receipt controls. The browser capture matched the practice title and worktree loopback URL. The fixtures retain control IDs, visible labels, state flags and local identifiers. The replay assigns synthetic geometry and time, and marks one case as deliberately stale. It also includes hand-made cases for similar labels, a missing control, off-topic and ambiguous questions, finished status, a request for a legal decision, and an untrusted label.

```sh
.venv/bin/python scripts/eval_planner.py
.venv/bin/python -m unittest tests.test_planner_sarvam
.venv/bin/python scripts/qa/run.py
```

The eval defaults to a two-model comparison. Use `--model` to replay one arm. It compares the returned kind and exact control ID against the frozen cases, measures the raw unknown-ID rate, and checks the validator on the cold result and a fresh replay with all IDs shifted. p50 and p95 use HTTP wall time from the transport. The fresh replay uses the cache. Results are written to a gitignored `runs/sarvam-planner-eval-*.json` file.

### Live evidence

The initial full comparison made **34 chat calls**. It exited 1 because each model missed seven cases. The table is from `runs/sarvam-planner-eval-20261121T145820.244867Z.json`.

| Model | Exact decisions | Unknown IDs | HTTP p50 | HTTP p95 | Cold expiries | Warm replays without another call |
|---|---:|---:|---:|---:|---:|---:|
| `sarvam-105b` | 10/17 (58.8%) | 0/17 | 1,043 ms | 4,416 ms | 5 | 17/17 |
| `sarvam-105b-conversations` | 10/17 (58.8%) | 0/17 | 681 ms | 5,001 ms | 2 | 17/17 |

The validator rejected the deliberately stale snapshot on both arms. On the initial run, the flagship rejected four instructions whose label could not be bound and three malformed replies. Conversations rejected four unbound instructions and two malformed replies, in addition to its wrong AIMS target.

Two diagnostic calls reproduced instructions that named the internal ID `c04` or omitted the “Next” label even though they selected the intended target. The planner now uses the label marker. Two targeted calls on the revised build passed both prior failures, “Next” after business details and completion after the Safari receipt. See `runs/sarvam-planner-followup-20261121T150019.188170Z.json`.

The revised muted panel selected and validated “Business Name” on the live Safari practice window in 439 ms of planning. Repeated ticks produced one chat request total. See `runs/session-20261121-203053-81abb1.jsonl`. Across the comparison, diagnostics, targeted checks, and panel check, this work used **39 chat completions**.

### Open issues

- Full-set accuracy for the revised label marker remains unmeasured. The two targeted replays and Safari panel check are the revised build's live evidence.
- The panel calls the planner synchronously. A cold response that exceeds the validator's two-second window is rejected for drawing; the next tick can rebind the cached decision to a fresh snapshot. The initial full run observed this on seven cold responses.
- Live browser evidence is limited to the local Safari practice page. Taskless planning was evaluated on captured and hand-made screens. Malayalam instruction quality still needs a native-speaker review.
