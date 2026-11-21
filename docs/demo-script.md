# Demo script and pitch (Track 02, "Voice & Language: Beyond English")

Draft, 22 Nov 2026. Target length 3 minutes. Status words follow the build board: what is shown live is
marked **live**; anything planned is said as planned.

## One-line pitch

Amma asks in Malayalam, and the companion shows her where to click on the real website. It never clicks for her.

## Setup before going on stage (5 minutes)

- Mac on charger, Do Not Disturb on, volume about 60%, Bulbul voice on (no `--mute`).
- Internet check: one Sarvam call (`scripts/sarvam_hello.py`). If the houseboat Wi-Fi is weak, use a phone
  hotspot. If there is no internet at all, play the backup recording (below) and say so.
- Safari, one window, three tabs in this order: local KSEB practice copy (`./scripts/open_web_practice.sh`, then
  `/kseb-quickpay`), YouTube home, Gmail inbox (Abin's account, inbox scrolled so no private subject is legible
  on the projector, or Gmail opened on the Sent folder).
- Start the companion: `.venv/bin/python -m companion.app --task web_site --lang ml`.
- Do one YouTube search beforehand, so an ad is less likely to play during the demo.
- Backup recording: one full screen capture of the three flows, recorded the evening before (Abin records it,
  because this Conductor shell has no screen-recording permission).

## Script

| Time | On screen | Say (presenter) |
|---|---|---|
| 0:00–0:20 | Title slide: a parent at a laptop, the KSEB site in English | "In Kerala, only about half of adults can send an email, and about a quarter can create a document (MoSPI CMS 2025). Our parents speak Malayalam. The websites they need speak English. So they wait for us to come home and click for them." |
| 0:20–0:35 | Companion panel beside Safari | "This is a companion for them. You ask in Malayalam, it reads the page, and draws a hand-drawn arrow at the next thing to click. You do the clicking. It never clicks or types for you." |
| 0:35–1:10 | KSEB tab. Press the mic: "എന്റെ കറന്റ് ബിൽ എങ്ങനെ അടയ്ക്കാം?" The arrow points at Consumer Number, the panel says it in Malayalam, Bulbul speaks. Type a sample number and follow it to the captcha. | "This is our local copy of KSEB Quick Pay, so we don't touch a real bill on stage. On the real site it guides the same way up to the captcha, and it stops there: paying stays with the person." |
| 1:10–1:50 | YouTube tab. Mic: "ദർശന പാട്ട് പ്ലേ ചെയ്യൂ". Arrow at Search, then the official video, playing. Then ask "പതുക്കെ ആക്കൂ" (make it slower): Settings, Playback speed, 0.75. | "This is the real YouTube. It picked the official video, not a random channel. If an ad plays, it points at Skip or tells you to wait. Slowing a song down is three menus deep, and it walks you through them one at a time." |
| 1:50–2:30 | Gmail tab. Mic: "എന്റെ മകന് ഒരു ഇമെയിൽ അയയ്ക്കണം". Compose, To, Subject, Body, Send. Panel: "ഇമെയിൽ അയച്ചു". | "This is my real Gmail. The companion only sees the buttons and field names, never the emails in my inbox or what I type. It confirms the email was sent because Gmail itself says so." |
| 2:30–2:50 | Diagram slide: voice → Sarvam Saaras (Malayalam speech to text) → Accessibility reader → site guide + Sarvam LLM → arrow + Bulbul voice | "Sarvam runs it end to end: Saaras turns Malayalam speech into text, the Sarvam model works out what you want, Bulbul speaks the reply. The steps themselves come from code we wrote for each site, so it doesn't make up buttons. Passwords, typed values and email content never leave the Mac." |
| 2:50–3:00 | Closing slide | "Today it runs on a Mac with three sites tuned: KSEB, YouTube and Gmail. Next comes Android, where our parents actually are, and more Kerala sites. We'd like help testing it with real families in Alappuzha." |

## What we can claim, and what we can't

| Claim | Can we say it? |
|---|---|
| Works on KSEB, YouTube, Gmail | Yes, for the tasks shown. KSEB is shown on our practice copy; the real site was guided up to the captcha in one manual test. |
| Works on any website | No. Say "three sites tuned; other forms work in a basic way" (only the generic form planner is tested, on a practice form). |
| Understands Malayalam speech | Yes (Saaras v4). Tested with synthetic audio and typed questions; the real-mic test is still pending (see below). |
| Runs on phones | No. Mac only today; Android is planned, not built. |
| Never clicks for you | Yes, by design: it only draws an arrow and speaks. |
| Privacy | Passwords, typed values and Gmail message text are not read or sent. URLs are reduced to the site name. On YouTube, ad text is reduced to fixed labels. |

## Questions judges may ask

- **Why not just click for them?** Because they learn, and nothing is paid or sent without their own click.
- **What if the site changes?** The reader works from Accessibility names, not screen pixels, and the guide
  checks each step against the live page before drawing anything. A changed page gets "I can't see that button",
  not a wrong arrow.
- **Where is Sarvam used?** Speech to text (Saaras v4, Malayalam → English), intent and wording (sarvam-105b),
  speech (Bulbul). Credits used so far: about 4 of 600.
- **How was it built?** Claude and Codex agents in Conductor, with a QA agent that walks each site by following
  the arrow. (Devin: see the open question below.)

## Before the demo: still open

1. **Devin rule.** The field guide says "build a project with Devin". We built with Claude and Codex. Ask the
   organisers whether Devin is required. If yes: push the branch (with Abin's OK) and give Devin one
   self-contained task that ends in a PR.
2. **Human tests not yet done:** real microphone in Malayalam and English; arrow lands on the right control when
   checked by eye; clicks pass through the overlay; a native speaker reviews the Malayalam wording in the panel
   and voice; Abin tries the new panel.
3. Record the backup video.
