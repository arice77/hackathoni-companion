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
| Volume and seeking | `Mute (m)` is `AXButton`. Safari's raw AX tree had a `Volume` and a `Seek slider` (`AXSlider`), but the current reader excludes sliders. |
| Search and results | `Search` is both `AXComboBox` and a distinct submit `AXButton`; `Search with your voice` is separate. The public video title appears as an `AXHeading` and an `AXLink` on the results page. A few actions lacked labels (two on watch, one on results). |

**Candidate parent tasks:** search for a Malayalam song and find the named result; find play/pause on the current video; go full screen; find the mute toggle. Changing playback speed or quality and enabling available captions need a separate read of those states before claiming support.

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

**Candidate parent tasks:** find mail search; navigate standard folders such as Sent or Starred; find Compose; find Subject, message body or Attach files in an already-open composer. Treat these as candidates for a sandbox mailbox first. A deployed Gmail path needs a chrome-only gate before using the real account with the planner; the general reader still accepts arbitrary on-page labels. Reply and recipient entry need their own verification.

## Reader cleanup and QA

The reader drops labels consisting only of Private Use Area glyphs and filters numbered carousel dot actions such as `1 of 5`; if dots are the only retained content, it keeps one. A fake tree covers mixed Malayalam or ordinary text, normal pagination, and a dot-only page. `scripts/qa/run.py unit`: **118 unit tests passed**, one suite check passed, zero failed. Live QA was not run.
