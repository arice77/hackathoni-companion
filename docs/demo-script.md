# Demo script and pitch (Track 02, "Voice & Language: Beyond English")

Draft, 22 Nov 2026. Target length 3 minutes. Status words follow the build board: what is shown live is
marked **live**; anything planned is said as planned.

## One-line pitch

Amma asks in Malayalam, and the companion shows her where to click on the real website. It never clicks for her.

## Setup before going on stage (5 minutes)

- Mac on charger, Do Not Disturb on, volume about 60%, Bulbul voice on (no `--mute`).
- Internet check: one Sarvam call (`scripts/sarvam_hello.py`). If the houseboat Wi-Fi is weak, use a phone
  hotspot. If there is no internet at all, play the backup recording (below) and say so.
- Safari, one window, four tabs in this order: gasundo.live/?district=ernakulam, then the local KSEB practice copy (`./scripts/open_web_practice.sh`, then
  `/kseb-quickpay`), YouTube home, Gmail inbox (Abin's account, inbox scrolled so no private subject is legible
  on the projector, or Gmail opened on the Sent folder).
- Start the companion: `.venv/bin/python -m companion.app --task web_site --lang ml`.
- Do one YouTube search beforehand, so an ad is less likely to play during the demo.
- Backup recording: one full screen capture of the four flows, recorded the evening before (Abin records it,
  because this Conductor shell has no screen-recording permission).

## Script

| Time | On screen | Say (presenter) |
|---|---|---|
| 0:00–0:15 | Title slide: a parent at a laptop, an English website | "In Kerala, only about half of adults can send an email (MoSPI CMS 2025). Our parents speak Malayalam. The websites they need speak English. So they wait for us to come home and click for them." |
| 0:15–0:25 | Companion panel beside Safari | "This companion fixes that. You ask in Malayalam, it reads the page and draws an arrow at the next thing to click. You do the clicking; it never clicks for you." |
| 0:25–0:55 | **GasUndo** (gasundo.live, Ernakulam). Mic: "ബെക്താഷ് കാക്കനാട് തുറന്നിട്ടുണ്ടോ?" Arrow at Search restaurants → the suggestion → the panel reads the report, and says it is old, so today's status is unknown. | "Let's start with an app the organisers built: GasUndo, by Vaishakh and Viswanatha. My mother wants to know whether her hotel is open. She asks in Malayalam. Notice it tells her the report is old instead of guessing." |
| 0:55–1:35 | YouTube tab. Mic: "ദർശന പാട്ട് പ്ലേ ചെയ്യൂ". Arrow at Search, then the official video (Skip if an ad plays). Then "എനിക്ക് ഈ വീഡിയോ സ്ലോ ആക്കണം": Settings → Playback speed → "−" with countdown 5…1 → 0.75×. | "Real YouTube. It picks the official video, handles ads, and walks you three menus deep, counting down the presses." |
| 1:35–2:15 | Gmail tab. Mic: "എന്റെ മകന് ഒരു ഇമെയിൽ അയയ്ക്കണം". Compose, To, Subject, Body, Send. Panel: "ഇമെയിൽ അയച്ചു". | "My real Gmail. The companion sees only buttons and field names, never my emails or what I type. It confirms the email was sent because Gmail says so." |
| 2:15–2:35 | KSEB practice copy. Mic: "എന്റെ കറന്റ് ബിൽ എങ്ങനെ അടയ്ക്കാം?" Arrow at Consumer Number, then Next steps to the captcha. | "And paying the electricity bill. This is our copy of KSEB Quick Pay; on the real site it stops at the captcha, so paying stays with the person." |
| 2:35–2:50 | Diagram: voice → Saaras → Accessibility reader → site guide (+ Sarvam LLM for intent) → arrow + Bulbul | "Sarvam runs it end to end: Saaras hears Malayalam, the Sarvam model works out what you meant, Bulbul speaks. Each site's steps are code we wrote, so it never invents buttons. Passwords, typed text and email content never leave the Mac." |
| 2:50–3:00 | Closing slide | "Four sites today on a Mac: GasUndo, YouTube, Gmail, KSEB. Next: Android, where our parents are. We'd love to test it with families here in Alappuzha." |

## What we can claim, and what we can't

| Claim | Can we say it? |
|---|---|
| Works on GasUndo, KSEB, YouTube, Gmail | Yes, for the tasks shown. GasUndo: view only; its reports are from March–May, and the guide says so. KSEB is shown on our practice copy; the real site was guided up to the captcha in one manual test. |
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
