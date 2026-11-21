# Sarvam planner

`SarvamPlanner(task)` implements the panel's `decide(question, snap) -> Decision` interface. The panel selects it with `--planner sarvam` and runs planning on a background thread. Pass `None` when calling the planner without a task. Named practice tasks contribute a goal. Typed questions can be native-only. Voice questions can contain the native wording followed by ` / ` and its English translation.

The request carries the question, optional task goal, visible heading or window title, and each control's `id`, `role`, `label`, `filled`, `enabled`, and reading rank. The rank orders controls top-to-bottom and then left-to-right. The prompt asks for the first unfinished required field, any visible prerequisite, and then the screen's primary action. It includes a worked example. Each request lists unfinished input IDs and allows only enabled, labeled controls that can be acted on as point targets. For recognized generic form-filling questions such as `ഈ ഫോം എങ്ങനെ പൂരിപ്പിക്കാം?`, filled inputs stay out of the point choices. Once the inputs are finished, an unambiguous enabled `Next`, `Continue`, or `Save` is the point choice. Specific edit requests can still target filled inputs.

Control identifiers, process metadata, geometry, and editable values stay out of the request. The prompt treats screen text as untrusted data and asks the model to decline decisions about payments, amounts, eligibility, and declarations.

The provider returns a strict schema with `kind`, `control_id`, `instruction_ml`, and `instruction_en`. The planner inserts the exact quoted label at the model's `[CONTROL]` marker. A valid target with missing or unbound wording gets a local instruction in that language. Unknown IDs, malformed replies, and unavailable targets return `unsupported`. The panel rebinds background decisions to the fresh snapshot, then the validator checks snapshot age, target presence, and on-window position.

For each active question, the planner caches decisions by window and the set of `(identifier or label, role, filled)` values. It also tracks visible label text, enabled states, and repeated controls. Safari uses status and enabled-state changes to mark progress after attachment and saving, so those changes need a fresh decision. On a cache hit the planner rebinds the target by identifier or by an unambiguous label and role and uses the current snapshot ID. Failed replies remain cached for that screen and question. Call logs in `runs/sarvam-planner-*.jsonl` contain model, timing, request ID, and outcome.

## Model choice

The default is **`sarvam-105b-conversations`** on `POST https://api.sarvam.ai/v1/chat/completions`. It met the 15/17 accuracy target with zero unknown IDs in the revised comparison. The alternate `sarvam-105b` uses `/v2/chat/completions` with `reasoning_effort: "none"`. Both use a 256-token budget, `response_format` with `json_schema` and `strict: true`, and the voice adapter's standard-library transport and `api-subscription-key` authentication. API documentation checked 21 November 2026. [Sarvam models](https://docs.sarvam.ai/api/token-factory/models/sarvam-105b) · [Chat V2](https://docs.sarvam.ai/api-reference/chat/chat-completions-v2) · [Chat V1](https://docs.sarvam.ai/api-reference/chat/chat-completions-v1)


## Fixture eval

`tests/fixtures/planner/screens.json` contains six AIMS and nine Safari practice snapshots captured using the Accessibility reader on 21 November 2026, plus five hand-made snapshots. The test driver used only the practice fixtures, with synthetic inputs and the worktree loopback URL for Safari. Captured controls are stored in visual reading order with their IDs, labels, state flags, and local identifiers. Replay uses synthetic geometry that preserves that order, with one deliberately stale snapshot.

The 30 cases keep the original 17 expected answers and add 13 cases covering crop details, photo attachment, declaration, completion, and partially filled business details. Questions include 6 Malayalam, 13 English, 6 Manglish, and 5 bilingual voice-style prompts.

```sh
.venv/bin/python scripts/eval_planner.py
.venv/bin/python -m unittest tests.test_planner_sarvam
.venv/bin/python scripts/qa/run.py
```

The eval defaults to a two-model comparison. Use `--model sarvam-105b-conversations` to replay the selected model alone. The target carries forward the original 15/17 ratio, which requires 27/30 exact matches with zero unknown IDs. The script checks the validator on the cold result and a cached, fresh replay with all IDs shifted. p50 and p95 use HTTP wall time. Reports go to gitignored `runs/sarvam-planner-eval-*.json` files.

### Expanded live stability eval

Two separate invocations used the same frozen 30 cases and the default `sarvam-105b-conversations` model. An exact match requires the expected decision kind and control ID. Both runs reused the local result for all 30 warm replays and rejected the deliberately stale snapshot.

| Run | Exact matches | Unknown IDs | HTTP p50 | HTTP p95 | Chat calls |
|---|---:|---:|---:|---:|---:|
| 1 | 28/30 | 0/30 | 557 ms | 1,509 ms | 30 |
| 2 | 28/30 | 0/30 | 531 ms | 4,034 ms | 30 |

The decisions agreed on 29/30 cases. All 13 additions matched in both runs, including the typed Malayalam question on the Documents screen after attachment. Both runs returned `unsupported` for “Can I use that one?” where `clarify` was expected. Both missed the case with a missing PDF export control, choosing “Print” in run 1 and “Download CSV” in run 2. The detailed reports are `runs/sarvam-planner-eval-20261121T153407.788675Z.json` and `runs/sarvam-planner-eval-20261121T153449.289292Z.json`.

The locked Safari walkthrough on the same planner confirmed all eight expected decisions with the typed Malayalam-only question. It selected “Next” after attachment and reached `complete` with visible status and a fresh local receipt. All pointers passed validation, including after a 2,484 ms planner call. See `runs/session-20261121-210521-546565.jsonl`. The expanded eval and walkthrough used 68 chat calls total (30 per eval and eight for Safari). Unit QA passed all 84 tests.

### Earlier 17-case eval

The first comparison after repairing the missing-label failure and adding reading order used 34 calls. The next full run used 17 calls with the actionable-control schema and explicit unfinished inputs. All 51 warm replays reused the cache and all three deliberately stale snapshots were rejected.

| Live run | Exact decisions | Unknown IDs | HTTP p50 | HTTP p95 | Calls |
|---|---:|---:|---:|---:|---:|
| `sarvam-105b`, reading order | 12/17 | 0% | 647 ms | 1,569 ms | 17 |
| `sarvam-105b-conversations`, reading order | 15/17 | 0% | 574 ms | 2,978 ms | 17 |
| `sarvam-105b-conversations`, actionable IDs and unfinished inputs | 15/17 | 0% | 664 ms | 1,920 ms | 17 |

The full reports are `runs/sarvam-planner-eval-20261121T151931.098629Z.json` and `runs/sarvam-planner-eval-20261121T152150.658980Z.json`. The selected arm fixed the read-only “2. Documents” progress-label selection. Its two misses were returning to a filled Business Name field on the bilingual question and returning `unsupported` for “Can I use that one?” where `clarify` was expected.

After excluding filled inputs from the recognized generic form questions, a one-call live replay of the bilingual case selected “Next” in 623 ms. See `runs/sarvam-planner-voice-replay-20261121T152315.907606Z.json`.

### Earlier locked Safari walkthrough

The muted panel used the typed Malayalam-only form question, and the test driver advanced the local practice page at six-second intervals. The session logged eight valid decisions and reached `complete` with both visible status and a fresh local receipt. The pointer sequence missed the Documents screen's `Next` step by repeating `Attach Sample Document` after attachment. The driver pressed `Next` and continued to Review. See `runs/session-20261121-205321-46a6cc.jsonl` and `runs/sarvam-planner-998ec2448cad441e9f5852cc6365ecbb.jsonl`.

The final primary-action filter has a mock regression replaying both Documents snapshots with the typed question. It allows attachment while `Next` is disabled and restricts pointing to `Next` after attachment enables it. This round used all **60 chat calls** (34 comparison, 17 selected-model eval, one bilingual replay, and eight panel calls).

### Regression QA

All 19 planner mock tests and 84 unit tests passed. The stock locked QA run passed the Safari and overlay checks and failed three AIMS checks when the reader opened a foreign-worktree instance sharing the fixture bundle ID. The locked AIMS rerun pinned the test reader to this worktree's app bundle and passed all seven automated checks. See `runs/qa/20261121-205611/report.md` and `runs/qa/20261121-205827/report.md`.

### Open issues

- The expanded eval missed the vague request and the missing PDF export in both runs. The provider selected IDs present on screen in the PDF case.
- Live browser evidence is limited to the local Safari practice page. Taskless planning was evaluated on captured and hand-made screens. Malayalam instruction quality still needs a native-speaker review.
