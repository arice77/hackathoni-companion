# Sarvam planner

`SarvamPlanner(task)` implements the panel's `decide(question, snap) -> Decision` interface. The panel selects it with `--planner sarvam` and runs planning on a background thread. Pass `None` when calling the planner without a task. Named practice tasks contribute a goal. Typed questions can be native-only. Voice questions can contain the native wording followed by ` / ` and its English translation.

The planner builds a `FormPlan` from visible controls and uses a `GuidanceSession` to track progress for one question. Plan units are inputs and choice sets in reading order, then the primary action. Session keys use role, normalized label, and group. The session observes filled-state changes and resets its progress on a page heading or title change. The provider is used once for intent that local rules cannot resolve. Its request includes the question, optional task goal, heading or window title, and a reading-order serialization with `##` headings, nested options, visible control labels, and a marker on controls whose state changed since the previous snapshot. The request includes the allowed target IDs and unfinished input IDs. Specific edit requests can still target filled inputs.

Control identifiers, process metadata, geometry, and editable values stay out of the request. The prompt treats screen text as untrusted data and asks the model to decline decisions about payments, amounts, eligibility, and declarations.

The provider returns a strict schema with `kind`, `control_id`, `instruction_ml`, and `instruction_en`. The planner inserts the exact quoted label at the model's `[CONTROL]` marker. A valid target with missing or unbound wording gets a local instruction in that language. Unknown IDs, malformed replies, and unavailable targets return `unsupported`. The panel rebinds background decisions to the fresh snapshot, then the validator checks snapshot age, target presence, and on-window or viewport position.

**Missing-control policy.** State that the requested control is absent and return `unsupported` with no pointer. For explicit label lookups, the planner allows matching labels. For explicit export, download, or save-as requests with a recognized file format, it allows visible output controls for that format. `Print`, `Download CSV`, and `Upload PDF` cannot stand in for a PDF export. Recognized button-action requests also require a visible button whose label names the action. These checks run locally. The prompt applies the same policy to other specific requests.

**Ambiguity policy.** Return `clarify` with a short question in the user's language and no pointer. Recognized standalone references to “this” or “that” in Malayalam, English, and Manglish get a local question asking which control the user means. The planner also asks when a target cannot be rebound uniquely. The prompt asks the model to clarify broader requests with competing goals.

**Broad web help.** Questions about using the site, which screen the companion can help with, or filling the form ask for a useful first step on the current page. For recognized English, Malayalam, and Manglish phrasing, the planner considers unfinished entry fields and choice sets together in reading order, followed by an unambiguous primary action. Explicit required markings override optional wording without changing the order of the remaining steps. Preferred values and supplemental instructions, notes, or comments are optional unless the label marks them required. The first distinct step introduces the page. On the httpbin capture it says “This is an order form. Start with ‘Customer name:’.” Later steps quote only the current target and any new guidance.

**Choice sets.** The user chooses the value. An unfinished radio set uses the group rectangle as its pointer target when it contains an enabled option. Accessibility reports the container as noninteractive. The reply lists the visible, enabled options in both languages and asks the user to choose. A clear preference can point at the requested option. The planner advances when the set or one of its radios reports a selection. It mentions an optional checkbox set once per question when progressing past it or when the user asks about it. The provider's allowed targets omit individual choices. If it still names a member of an eligible set, the planner points at the set and supplies neutral wording locally.

**Practice completion.** The AIMS and Safari practice tasks declare their own completion prefixes, “Training draft complete” and “Training complete”. When the fixture's static `status` text starts with its prefix, followed by punctuation or the end of the text, the planner returns a short bilingual congratulation with a null control ID. This consumes zero chat calls and the panel hides the pointer. Review and a checked declaration alone still allow the next step. Explicit control requests retain their grounding checks, and public pages use the model's visible-status rule.

For each active question, the planner caches decisions by window and the set of `(identifier or label, role, filled)` values. It also tracks visible label text, enabled state, group membership, and repeated controls. A change to either a radio or the set's `filled` flag invalidates the cached decision. Safari status and enabled-state changes also trigger replanning after attachment and saving. On a cache hit the planner rebinds the target by identifier or by an unambiguous label, role, and group and uses the current snapshot ID. Failed replies remain cached for that screen and question. Call logs in `runs/sarvam-planner-*.jsonl` contain model, timing, request ID, and outcome.

## Model choice

The default is **`sarvam-105b-conversations`** on `POST https://api.sarvam.ai/v1/chat/completions`. It met the 15/17 accuracy target with zero unknown IDs in the revised comparison. The alternate `sarvam-105b` uses `/v2/chat/completions` with `reasoning_effort: "none"`. Both use a 256-token budget, `response_format` with `json_schema` and `strict: true`, and the voice adapter's standard-library transport and `api-subscription-key` authentication. API documentation checked 21 November 2026. [Sarvam models](https://docs.sarvam.ai/api/token-factory/models/sarvam-105b) · [Chat V2](https://docs.sarvam.ai/api-reference/chat/chat-completions-v2) · [Chat V1](https://docs.sarvam.ai/api-reference/chat/chat-completions-v1)


## Fixture eval

`tests/fixtures/planner/screens.json` contains six AIMS and nine Safari practice snapshots captured using the Accessibility reader on 21 November 2026, two public Safari snapshots, and six hand-made snapshots. The test driver used only the practice fixtures, with synthetic inputs and the worktree loopback URL for Safari. Captured controls are stored in visual reading order with their IDs, labels, state flags, and local identifiers. Replay uses synthetic geometry that preserves that order, with one deliberately stale snapshot.

The 69 cases cover progress through both practice fixtures, completion and still-actionable Review states, missing and present export controls, explicit labels, ambiguity, and public pages. The original public snapshots came from read-only Accessibility captures in new Safari windows. The httpbin choice cases annotate the capture with the choice-set contract and vary the `filled` flags to replay progress. Safari replays have synthetic viewports and public replays have host-only titles. All 19 public cases expect targets with no AX or DOM identifier. [httpbin order form](https://httpbin.org/forms/post) · [Wikipedia search](https://www.wikipedia.org/)

```sh
.venv/bin/python scripts/eval_planner.py
.venv/bin/python -m unittest tests.test_planner_sarvam
.venv/bin/python scripts/qa/run.py
```

The eval defaults to a two-model comparison. Use `--model sarvam-105b-conversations` to replay the selected model alone. The target carries forward the original 15/17 ratio, which requires 61/69 exact matches, zero unknown IDs, and zero malformed replies. Orientation and choice-set cases also check the expected wording and quoted targets in both languages. The script marks each decision as local or provider-backed and checks the validator on the cold result and a fresh replay with all IDs shifted. p50 and p95 use provider HTTP wall time. Reports go to gitignored `runs/sarvam-planner-eval-*.json` files.

### Choice-set eval

The six cases cover an undecided size in English and Malayalam, continuing after a selection, an explicit Large preference, an explicit Extra Cheese preference, and proceeding without optional toppings. The ready-to-submit replay notes that toppings are optional and asks the user to review the order before using “Submit order”.

| Run | Exact | Choice guidance | Unknown IDs | Malformed | HTTP p50 | HTTP p95 | Chat calls |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 69/69 | 6/6 | 0 | 0 | 528 ms | 1,571 ms | 28 |
| 2 | 69/69 | 6/6 | 0 | 0 | 1,091 ms | 6,807 ms | 28 |

Both live evals ran under the QA lock and passed all 69 warm replays. The six choice cases used zero calls, and all 109 unit tests passed. Grouped choice behavior was tested using the captured httpbin layout and synthetic selection flags. The separate reader change supplies the group metadata in Safari. See `runs/sarvam-planner-eval-20261121T173109.190116Z.json`, `runs/sarvam-planner-eval-20261121T173209.794809Z.json`, and `runs/qa/20261121-230042/report.md`.

### Whole-form walkthrough regression

The read-only session log showed that the early “Delivery instructions:” suggestion came from the local path. The upstream form has no required flags, and the Accessibility snapshot carries no required attribute. The historical snapshot is unavailable, so the earlier fields' visibility and filled state at that instant are unknown. A lower-only replay now asks the user to scroll up before it can suggest proceeding. [httpbin form source](https://github.com/postmanlabs/httpbin/blob/master/httpbin/templates/forms-post.html)

The pure walkthrough retains one planner and one question. It fills each pointed field and picks the first available option when pointed at a set. It expects Customer name → Telephone → E-mail address → Pizza Size → Submit order for the original labels. The required-delivery variant takes Preferred delivery time and Delivery instructions between Pizza Size and Submit order. The assertions also cover the once-only intro and optional toppings note, no repeated or filled targets, and the local success heading returning `complete`.

After a pointed web form action, the planner compares visible status to the status when it pointed. A new explicit success message ends the walk with `complete` even if the form and action remain visible. A generic confirmation heading asks the user to verify the result without highlighting the action again.

### Broad web help eval

Each of the following phrasings runs on both the httpbin order form and the Safari practice fixture, for 18 cases. The public cases start at “Customer name:”. The practice cases use “Business Name” on a blank form, “Next” after the required fields are filled, and “Save” on Review.

| English | Malayalam | Manglish |
|---|---|---|
| Can you tell me how do I use this website? | ഈ വെബ്‌സൈറ്റ് എങ്ങനെ ഉപയോഗിക്കാം? | Ee website engane use cheyyam? |
| Which screen can you help me with? | ഏത് സ്ക്രീനിൽ എന്നെ സഹായിക്കാനാകും? | Ethu screenil help cheyyan pattum? |
| Can you help me fill this form? | ഈ ഫോം പൂരിപ്പിക്കാൻ സഹായിക്കാമോ? | Ee form fill cheyyan sahayikkamo? |

| Run | Exact | Orientations | Unknown IDs | Malformed | HTTP p50 | HTTP p95 | Chat calls |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 63/63 | 18/18 | 0 | 0 | 604 ms | 1,551 ms | 30 |
| 2 | 62/63 | 18/18 | 0 | 0 | 683 ms | 14,113 ms | 30 |

Both locked runs used `sarvam-105b-conversations` and spent zero chat calls on the 18 new cases. The only miss was the recurring AIMS loss-description case. Run 2 pointed at “Save »” too early. Both runs selected “Category” on the specific Safari shop-category question. All 105 unit tests passed. See `runs/sarvam-planner-eval-20261121T172227.891276Z.json`, `runs/sarvam-planner-eval-20261121T172345.551613Z.json`, and `runs/qa/20261121-225202/report.md`.

### Completion regression eval

Both live runs used `sarvam-105b-conversations` inside the QA lock. All five practice completion cases returned `complete` locally with no control ID or marker, and both remaining-action Review cases pointed at the expected control. The hand-made saved screen also returned `complete` in both runs, using the provider. All 45 warm decisions rebound correctly in each run.

| Run | Exact | Unknown IDs | Malformed replies | HTTP p50 | HTTP p95 | Chat calls | Local decisions |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 43/45 | 0 | 0 | 603 ms | 2,572 ms | 33 | 12 |
| 2 | 44/45 | 0 | 0 | 721 ms | 4,400 ms | 33 | 12 |

Both runs asked for clarification when the user asked where to select the shop category. Run 1 also chose “Save »” too early on the AIMS loss-description question. Both cases had passed in the prior evals. The round spent 66 of the allotted 100 chat calls. See `runs/sarvam-planner-eval-20261121T171501.813130Z.json`, `runs/sarvam-planner-eval-20261121T171611.625106Z.json`, and `runs/qa/20261121-224424/report.md`.

Separate locked QA walkthroughs finished both fixtures and produced fresh practice receipts. A Sarvam planner read each live finished screen and returned `complete` with no pointer and zero chat calls. QA passed 21 checks, including all 102 unit tests and fixture cleanup. One opt-in voice check was blocked and three human checks were skipped. See `runs/qa/20261121-224542/report.md`.

### Earlier 41-case eval

Both runs used `sarvam-105b-conversations` and the same frozen cases after adding label, export-format, and button-action grounding. Exactness compares decision kind and target ID.

| Run | Exact | Public cases | Unknown IDs | HTTP p50 | HTTP p95 | Chat calls | Local decisions |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 37/41 | 3/4 | 0 | 584 ms | 2,605 ms | 34 | 7 |
| 2 | 39/41 | 4/4 | 0 | 798 ms | 3,513 ms | 34 | 7 |

Both runs passed every missing-control and ambiguity case, including both original misses. Both selected Wikipedia's “Search” button. Among the public cases, the first run asked for clarification on the Medium pizza choice. The second run selected “Medium”. Two Safari completion cases regressed to malformed replies in both runs. The AIMS completion question also selected “Print Application” in run 1 and returned `complete` in run 2.

The final runs agree on 39/41 decisions. Each used 34 chat calls and seven local decisions. A preliminary pair used 68 chat calls and exposed the Wikipedia donation-link substitution and an AIMS add-control miss. The final pair used another 68, for 136 chat calls in this round. The final reports are `runs/sarvam-planner-eval-20261121T155601.726907Z.json` and `runs/sarvam-planner-eval-20261121T155647.721698Z.json`.

Locked QA passed 18 checks with zero failures, one opt-in Sarvam voice check blocked, and three human checks skipped. All 99 unit tests passed. See `runs/qa/20261121-212527/report.md`.

### Earlier 30-case stability eval

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

- The AIMS loss-description question can still trigger a premature “Save »” suggestion.
- Public-page evidence uses read-only captures. The end-to-end driver checks use the local practice fixtures. Malayalam instruction quality still needs a native-speaker review.
