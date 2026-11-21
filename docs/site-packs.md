# Site packs

Use `--task web_site` to guide a supported page in the front Safari window. The planner picks a pack from the host reported by the Accessibility reader. KSEB Quick Pay and YouTube also apply when `web_any` sees their hosts. A page on an unconfigured host gets a local response under `web_site`.

## KSEB Quick Pay

The real pack matches `wss.kseb.in`. The QA pack uses the loopback practice page and its recognizable Quick Pay controls. Known goals resolve locally, so the same question continues as the user fills each field. If the user starts on the KSEB home screen, the planner points at “Quick Pay”.

| Goal | Example |
|---|---|
| View the bill | “എന്റെ കറന്റ് ബിൽ എങ്ങനെ കാണാം?”, “How do I see my electricity bill?”, “Current bill engane nokkam?” |
| Find the consumer number field | “കൺസ്യൂമർ നമ്പർ എവിടെ ടൈപ്പ് ചെയ്യണം?” |
| Find the registered mobile field | “Registered mobile number evide kodukkanam?” |
| Enter the verification text | “Where do I type the verification text?” |
| Refresh an unreadable image | “ചിത്രം വായിക്കാൻ പറ്റുന്നില്ല” |

The order is **“13 digit Consumer number” → “Enter Mobile Number” → “Enter text shown below” → “Submit to see the bill”**. Guidance asks the user to copy the number from their electricity bill and use the mobile number registered to the connection. The user reads and enters the image text. A separate Refresh goal points at the link when requested. The final button opens the bill view. The practice page emits a synthetic receipt and a known success heading. [Safari probe](site-probes.md)

An off-script request can go to Sarvam once. The KSEB profile passes only exact, allowlisted control labels and headings. It masks mobile- and consumer-number-shaped digit strings in the question. Account-specific headings, bill values, registration hints, the verification image, and entered field values stay out of that payload. The allowlist cannot authorize an early Submit while a known prior field is unfinished.

## YouTube

The pack matches `youtube.com`, `www.youtube.com`, and `m.youtube.com`. A local guide follows the same question across search, results, playback, and menus. It binds each pointer to a visible control in the current snapshot. The guide tracks progress by the control's role and label as Accessibility IDs change.

| Goal | Example |
|---|---|
| Find and play a named video | “Find and play Darshana Hridayam”, “എനിക്ക് ഹൃദയം ദർശന പാട്ട് കേൾക്കണം”, “Darshana Hridayam paattu play cheyyu” |
| Bigger screen | “വീഡിയോ വലുതാക്കി കാണണം”. Use Esc to exit full screen. |
| Pause, play, mute, or unmute | “Video pause cheyyu”, “Resume the video”, “ശബ്ദം ഓഫ് ചെയ്യൂ”, “Sound unmute cheyyu” |
| Malayalam subtitles | “മലയാളം സബ്‌ടൈറ്റിൽ വേണം”. Follow CC and Settings → Subtitles/CC → Malayalam when the option is visible. |
| Slow or change playback speed | “Pathukke play cheyyu” offers 0.75×. “Set playback speed to 1.5” offers 1.5×. An unspecified faster request asks which visible speed the viewer wants. |

A search task points at the search box, then the Search button once the box is filled. If the box was already filled, the instruction asks the viewer to replace the text and press Return because the reader tracks only whether the input has a value. Search queries keep media terms such as “song”. A local alias maps “ദർശന പാട്ട്” to “darshana song”. The guide ranks verified watch links by title words and uses song, official, and video cues to break ties. Links labeled as mixes, playlists, or Shorts rank below regular videos. If only those links are visible and there are more results below the fold, the guide asks the viewer to scroll. [Safari probe](site-probes.md)

Player controls match both “Play (k)” and “Play keyboard shortcut k”. When controls are temporarily hidden, the guide waits for another snapshot and can ask the viewer to move the pointer over the player. It handles “Skip”, “Skip ad”, and “Skip ads” and asks the viewer to wait if the player exposes an ad countdown. Subtitles and speed options depend on the current video and menu. [YouTube keyboard shortcuts](https://support.google.com/youtube/answer/7631406?hl=en-IN) · [YouTube subtitle settings](https://support.google.com/youtube/answer/100078?hl=en-UK) · [YouTube playback speed](https://support.google.com/youtube/answer/7509567?hl=en)

If the requested video is outside the visible results and the reader reports more below the fold, the guide asks the viewer to scroll down. It suggests searching again once the results are exhausted. Known goals require zero chat calls. For an off-script request, the provider can see an allowlist of standard search and player controls. Video result titles and account labels stay out of that payload. The recorded-state eval exercises 33 multilingual cases with 100 expected decisions in [`tests/fixtures/planner/youtube.json`](../tests/fixtures/planner/youtube.json).

## Gmail

This pack matches `mail.google.com` and uses the reader’s Gmail chrome gate. It never uses an inbox row as a pointer target. Use a fresh email composer or a conversation the user has already opened. Recognized requests resolve locally and no question or snapshot is sent to the Sarvam chat planner. The profile permits fixed chrome labels, masks email addresses and number-shaped strings, and strips identifiers and group metadata.

| Goal | Malayalam / other examples | Guidance |
| --- | --- | --- |
| Write an email | “പുതിയ ഇമെയിൽ എങ്ങനെ എഴുതാം?”, “Oru mail ayakkanam” | Compose → To → Subject → Message Body → optional Attach files → Send. The user checks the address and content, then decides whether to press Send. |
| Reply | “ഈ മെയിലിന് മറുപടി എഴുതണം”, “Reply engane cheyyam” | Reply → Message Body → Send. Never opens a conversation for the user. |
| Find an email | “മെയിൽ എങ്ങനെ തിരയാം?”, “Find an email” | Point to the editable Search mail field. The user types a remembered name or word and presses Enter. |
| Attach a photo | “ഫോട്ടോ എങ്ങനെ ചേർക്കാം?”, “Photo engane attach cheyyam” | Point to Attach files. Explain how to choose the photo and click Open. No picker pointer without a supported reader. |

The local guide can follow confirmed filled flags or an explicit, one-time “Next” acknowledgement for unknown field state. A known empty field cannot be skipped. The locked Safari driver uses the Gmail reader, guide, validator and real overlay, and acknowledges each private field after typing the known test text. The standard companion panel still needs to route acknowledgements to the same Gmail guide session and stop logging raw question/transcript text before offering a real-mail rehearsal from the panel.

`.venv/bin/python -m tests.test_site_gmail_live` uses a placeholder and stops at Send. The explicitly opted-in `--send` route requires `QA_GMAIL_TO` and the comma-separated `QA_GMAIL_ALLOWED`, from the environment or git-ignored `.env`. The driver checks the committed recipient and verifies the synthetic subject and body before attempting Send. It cannot retry Send, even on an uncertain result, and never logs either the recipient or the draft text.

The locked Safari draft walkthrough validated six pointers through Send and closed its own window. Sending to Abin's address and dismissing the composer still need a confirmed result.

## Optional steps on general forms

The planner offers optional fields and sets in reading order. It names the checkbox choices and leaves each selection with the user. The panel's Skip action and the colloquial commands “skip”, “next”, “no”, “വേണ്ട”, “ഒഴിവാക്കൂ”, “adutha”, and “venda” advance an optional pointer under the same question. Filling a later unit also skips earlier optional units observed in that plan. Later instructions begin with “Next” or “അടുത്തത്”. A primary button whose visible label contains a recognized action phrase can be selected when it is the only candidate.

## QA

The KSEB eval has nine English, Malayalam, and Manglish replays based on the probe. The submit replay uses synthetic filled flags. The browser walkthrough uses the local `/kseb-quickpay` copy, including the fixture's sample verification text and local receipt.

On the merged reader, two consecutive locked runs each passed all eight KSEB checks and all eleven pizza checks. Both fixtures reached `complete` and wrote fresh local receipts. Both walkthroughs used zero chat calls. The pizza driver used Skip for toppings and time, then filled delivery instructions. The pure walk also exercises skipping delivery instructions and skipping earlier optional steps after filling a later one.

The 78-case live eval matched every expected decision, with zero unknown IDs or malformed replies. It made 26 chat calls, none for the nine local KSEB cases. All 148 unit tests passed. See `runs/qa/20261122-002807/report.md`, `runs/qa/20261122-002835/report.md`, `runs/qa/20261122-002751/report.md`, and `runs/sarvam-planner-eval-20261121T185740.158118Z.json`.
