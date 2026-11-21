# Site packs

Use `--task web_site --planner sarvam` to guide a supported page in the front Safari window. The planner picks a pack from the host reported by the Accessibility reader. KSEB Quick Pay is the first pack. A page on an unconfigured host gets a local response under `web_site`. KSEB's pack also applies when `web_any` sees the same host.

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

## Optional steps on general forms

The planner offers optional fields and sets in reading order. It names the checkbox choices and leaves each selection with the user. The panel's Skip action and the colloquial commands “skip”, “next”, “no”, “വേണ്ട”, “ഒഴിവാക്കൂ”, “adutha”, and “venda” advance an optional pointer under the same question. Filling a later unit also skips earlier optional units observed in that plan. Later instructions begin with “Next” or “അടുത്തത്”. A primary button whose visible label contains a recognized action phrase can be selected when it is the only candidate.

## QA

The KSEB eval has nine English, Malayalam, and Manglish replays based on the probe. The submit replay uses synthetic filled flags. The browser walkthrough uses the local `/kseb-quickpay` copy, including the fixture's sample verification text and local receipt.

On the merged reader, two consecutive locked runs each passed all eight KSEB checks and all eleven pizza checks. Both fixtures reached `complete` and wrote fresh local receipts. Both walkthroughs used zero chat calls. The pizza driver used Skip for toppings and time, then filled delivery instructions. The pure walk also exercises skipping delivery instructions and skipping earlier optional steps after filling a later one.

The 78-case live eval matched every expected decision, with zero unknown IDs or malformed replies. It made 26 chat calls, none for the nine local KSEB cases. All 148 unit tests passed. See `runs/qa/20261122-002807/report.md`, `runs/qa/20261122-002835/report.md`, `runs/qa/20261122-002751/report.md`, and `runs/sarvam-planner-eval-20261121T185740.158118Z.json`.
