# Safari site probes for Malayalam-first guidance

**Live-machine, 22 November 2026 (IST).** Opened each page by URL in a dedicated Safari window and closed that window afterward. No site controls were operated, no form values were entered, and nothing was submitted or sent. These are Accessibility observations and candidate tasks, not end-to-end guidance tests. No Sarvam calls were made.

## Reader timings

Times are for successful reads after the browser began exposing the page, not page load or planner latency. Counts are reader entries, not unique tasks. Below-fold counts are lower bounds from the bounded AX traversal; they can include navigation, suggestions, or other non-task controls.

| Page | Successful reads | Median / max | Snapshot entries | Below fold |
| --- | ---: | ---: | ---: | ---: |
| YouTube watch, pointer outside viewport | 6 | 88.9 / 138.7 ms | 60 | 200 |
| YouTube search results | 6 | 56.3 / 94.8 ms | 40 | 131 |
| KSEB Quick Pay | 7 | 15.4 / 27.1 ms | 28 | 5 |
| Gmail inbox, privacy-filtered | 5 | 73.2 / 197.3 ms | 91 | 52 |
| Gmail compose, open and privacy-filtered | 5 | 64.1 / 83.5 ms | 96 (cap) | 5 |

## YouTube

Pages: Think Music's official [Darshana video from *Hridayam*](https://www.youtube.com/watch?v=epAFDEJImrU) and its [search results](https://www.youtube.com/results?search_query=Darshana+Hridayam+official). The pointer was outside the watch-page viewport for all six successful samples; the player controls did not require hover to enter the snapshot in this session.

| UI | Observed |
| --- | --- |
| Play/pause | `AXButton`, `Pause (k)` in the observed playback state. The alternate Play label was not exercised. |
| Subtitles/CC | `AXCheckBox`, `Subtitles/closed captions unavailable` on this video. The control is identifiable, not evidence that Malayalam captions are available. |
| Gear, speed and quality | `Settings` is `AXPopUpButton`. Speed and quality weren't exposed with the menu closed; no submenu was opened. |
| Full screen | `AXButton`, `Full screen (f)`. |
| Volume and seeking | `Mute (m)` is `AXButton`. Safari exposes `Volume` and `Seek slider` as `AXSlider`; the follow-up below verifies both in the reader. |
| Search and results | `Search` is both `AXComboBox` and a distinct submit `AXButton`; `Search with your voice` is separate. The public video title appears as an `AXHeading` and an `AXLink` on the results page. A few actions lacked labels (two on watch, one on results). |

**Shorts markers, automated:** visible Shorts links use `youtube-short:<video-hash>:<anchor-hash>`, including when Safari exposes no label. Watch links use `youtube-watch:` and share the video hash for the same video. Link URLs and raw IDs stay internal to the reader.

**Candidate parent tasks:** search for a Malayalam song and find the named result; find play/pause on the current video; go full screen; find the mute toggle. Changing playback speed or quality and enabling available captions need a separate read of those states before claiming support.

**Closed-menu baseline, live and read-only:** the reader retained both sliders with labels and visible frames, without reading their values. Four watch-page reads took 88.1 ms median / 134.5 ms max and reported 199 below-fold controls. With Settings untouched, its `AXPopUpButton` advertised `AXPress`, reported `AXExpanded=false`, had no `AXMenu` and had zero children. No speed or quality action appeared elsewhere in the closed tree.

**Approved menu-opening follow-up:** AXPress opened Settings on [Darshana](https://www.youtube.com/watch?v=epAFDEJImrU) and [TED's The Power of Vulnerability](https://www.youtube.com/watch?v=iCvmsMzlF7o). Safari exposed the visible entries separately from the gear, even though the gear still reported `AXExpanded=false` and zero children. The reader now keeps `AXMenuItem` and its checkbox/radio variants. On the TED page, it retained all three top-level entries (`Playback speed`, `Quality`, `Subtitles/CC`) and the controls exposed by one more AXPress on each:

| Panel | Live reader controls |
| --- | --- |
| Playback speed | `AXButton` presets, including 1.0, 1.25, 1.5, 2.0, and 3.0, plus increase/decrease buttons in 0.05 steps. |
| Quality | `AXMenuItem` choices including Auto and resolutions from 144p through 1080p. |
| Subtitles/CC | `AXMenuItem` language choices on TED; Off, English (auto-generated), and Auto-translate on one Darshana load. Malayalam availability was not verified. |

Menus were closed through Settings and the dedicated windows were closed. No setting option, like, subscribe, or comment control was pressed. This verifies AX visibility and submenu navigation, not applying a new setting.

## GasUndo

**Anonymous HTTP and source inspection, 22 November 2026 IST.** GasUndo shows crowd reports about restaurants during Kerala’s LPG shortage. The Ernakulam catalog returned 2,736 places. The Alappuzha catalog returned HTTP 500 during the probe. The status snapshot was generated on 21 November UTC, and its newest included restaurant report was dated 25 May UTC. [GasUndo](https://gasundo.live/) · [Ernakulam catalog](https://gasundo.live/api/catalog?district=ernakulam) · [Alappuzha catalog](https://gasundo.live/api/catalog?district=alappuzha) · [Status snapshot](https://gasundo.live/api/status-snapshot)

The desktop sidebar and mobile layout expose **Select district** and **Search restaurants** in HTML. Focused search shows matching buttons as the query changes. Selecting a result opens its name, address when available, report status and freshness in a sidebar or sheet. The site's **Open**, **Limited**, and **Closed** filters change the map. Reports older than 24 hours are labeled **Stale**. Adding reports, confirming reports, commenting, and voting require sign-in. [Search and filter implementation](https://github.com/vaishakh3/gasundo/blob/e266b7a53f1bd02c2f8cf9e363ea135440559502/src/components/FilterBar.jsx#L108-L251) · [Deployed app](https://gasundo.live/_next/static/chunks/a6ca469f9bc42c3f.js) · [Deployed status and freshness logic](https://gasundo.live/_next/static/chunks/aa53402c9aa86c37.js)

**Automated:** Synthetic AX trees replay district selection, search, the matching suggestion, and the detail report. They also cover stale and missing reports and the catalog error. Safari AX labels, frame placement, and a person's walkthrough are pending live verification.

## KSEB Quick Pay

The official [self-service home page](https://wss.kseb.in/selfservices/) links to [Quick Pay](https://wss.kseb.in/selfservices/quickpay). The dedicated Quick Pay window was opened directly by that URL. The reader retained these three `AXTextField` labels, each next to its own heading:

| Heading | Field label |
| --- | --- |
| Consumer No | `13 digit Consumer number` |
| Registered Mobile Number | `Enter Mobile Number` |
| Enter the text in image | `Enter text shown below` |

The captcha text field and the `Refresh` `AXLink` are separately identified. The bitmap itself is not a pointer target in the reader; no challenge was interpreted or refreshed. A raw AX check observed four labeled images, but did not positively identify the challenge image by ID. `Submit to see the bill` is an `AXButton`; it was not pressed. A generic `here` registration link and an unlabeled link remain weak targets without nearby context. No icon-font-only labels appeared in the filtered snapshot.

**Candidate parent tasks:** find Quick Pay in the navigation; find where to copy the consumer number from the paper bill; find the registered-mobile field; find the verification field or Refresh link and let the user read the image. Stop at the verification step in a guided test; bill retrieval, payment, and receipts are unverified.

## Gmail

Only fixed, allowlisted UI labels and aggregate role/geometry counts were retained. Reads used the reader's bounded AX walk with a local filter that blocked value and ID reads and removed non-allowlisted labels. No raw snapshots were serialized, and no message content or account identifiers were logged or sent. A separate structure-only inbox query counted **50 exposed `AXRow` entries in the message `AXTable`, 17 intersecting the viewport**; this is the loaded page, not the mailbox total.

| Surface | Retained standard UI, one of each listed role unless noted |
| --- | --- |
| Inbox | Compose (`AXButton`); Search mail (`AXTextField` and `AXButton`); Sent, Starred, Snoozed (`AXLink`); Labels (`AXHeading`); Primary (`AXHeading` and `AXRadioButton`). |
| Compose | Subject (`AXTextField`); Message Body (`AXTextArea`); Attach files (`AXPopUpButton`); Send (`AXButton`). Standard background folder links Inbox, Drafts, Sent, Starred and Snoozed also appeared. |

Compose was opened only by the [requested new-compose URL](https://mail.google.com/mail/u/0/#inbox?compose=new). The first attempt exposed inbox only; the confirmed-open timings in the table are from a later attempt, with three reader misses before the successful samples. The raw compose check included an extra `AXComboBox`, but the reader did not return a confirmed, allowlisted To/Recipients target. Reply was not observed on either tested surface; no conversation was opened to check it. The compose window was closed without typing, pressing Send, or pressing Discard.

**Candidate parent tasks:** find mail search; navigate standard folders such as Sent or Starred; find Compose; find To, Subject, message body or Attach files in an already-open composer. Treat these as candidates for a sandbox mailbox first; no guidance, recipient entry, reply or sending was exercised on the real account.

### Gmail gate follow-up

The production reader now uses a separate projection on `mail.google.com`. It emits fixed chrome names, one structural message-list count, and `Open email` plus allowlisted actions on recognized conversation routes. It uses values from allowlisted editable fields only to calculate filled flags and checks the To row for committed recipient chips. Values and control IDs stay out of snapshots, and message rows still contribute only to the aggregate count. Fake trees cover inbox rows, private header and body text, compose occupancy, recipient chips, and dispatch at the Gmail host. Neither raw mailbox snapshots nor conversation URLs were saved or logged.

- **Inbox, live:** one `AXTable` labeled `Inbox: 50 messages`, plus 13 standard chrome controls. Four reads took 24.3 ms median / 49.1 ms max; below-fold count was 0. The first message row and its links yielded no conversation `AXURL`. No conversation was opened and Reply remains unverified live; a synthetic conversation test exposes it without the header or body.
- **Compose, live:** the same direct new-compose URL exposed a labeled recipient `AXComboBox`, normalized to `To` from its recipient accessibility name. Four reads retained all five expected controls (To, Subject, Message Body, Attach files, Send), took 29.3 ms median / 141.6 ms max, and reported zero below-fold controls. The dedicated window was closed without entering anything or operating its controls.

- **Sent conversation, live:** opened the [Sent view](https://mail.google.com/mail/u/0/#sent), checked the first row's already-read indicator, and opened only that row with AXPress. The gate returned `Open email` and `Reply`. `Back to Sent Mail` was exposed as `AXButton` and pressed to return to Sent; a repeat confirmed the gate now normalizes it to `Back`. Neither `Reply all` nor `Forward` was visible on the sampled conversation; no message action menu was opened. No subject, recipient, body, or conversation URL was recorded, and no mail actions besides opening the read row and navigating Back were taken.

## Reader cleanup and QA

The reader drops labels consisting only of Private Use Area glyphs and filters numbered carousel dot actions such as `1 of 5`; if dots are the only retained content, it keeps one. A fake tree covers mixed Malayalam or ordinary text, normal pagination, and a dot-only page. `scripts/qa/run.py unit`: **118 unit tests passed**, one suite check passed, zero failed. Live QA was not run.

Gmail gate and slider follow-up: `scripts/qa/run.py unit` passed **131 tests** (one suite check, zero failures). No paid requests or live QA were run.

## Reader timeout follow-up

The retest log had two AX messaging timeouts. Browser reads now have a shared **750 ms** deadline and at most **120 ms** per AX request. A timeout triggers one fresh traversal; it does not publish a partial snapshot. If both attempts time out, the reader may reuse a snapshot younger than **1.5 s** only after confirming the same browser scope, AX page, URL, viewport and any exposed scrollbar positions. It preserves the original snapshot ID and timestamp. An unverified or changed page still fails closed.

**Live-machine:** 20 fresh reads per already-open site, nearest-rank p95, excluding page load. The error column counts unsuccessful reads during sampling; their causes were not classified. No natural cached reads occurred in these samples.

| Site | Median | p95 | Max | Unsuccessful reads |
| --- | ---: | ---: | ---: | ---: |
| YouTube watch | 85.6 ms | 115.4 ms | 274.3 ms | 3 |
| Gmail inbox, gated | 19.3 ms | 83.4 ms | 110.2 ms | 3 |
| KSEB Quick Pay | 15.3 ms | 16.0 ms | 18.9 ms | 1 |

Two injected traversal timeouts on each of the three live pages returned the original snapshot after a real AX identity check. This exercises fallback without claiming the original machine load was reproduced. Automated tests cover the retry with a simulated slow AX getter, rejection after page or scroll changes, cache expiry, and the remaining deadline. Unit QA: **138 tests passed**, zero failed. All probe windows were closed; no form controls were operated.
