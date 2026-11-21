# Build board

Orchestrator: coordinator session (Opus) · Process: `/conductor-orchestrator` · QA: `companion-qa` skill.
Status words: planned · building · in QA · in review · merged · demo-ready.

## Current focus (Abin, 21 Nov 2026, later): get the basics right first

1. The companion works on **web apps in a browser** (real tasks such as GST are websites). Safari is proven readable
   (orchestrator probe, live-machine); Chromium/Brave needs work and is tested only with a throwaway profile.
2. **Language preference, Malayalam or English**: the user speaks in it, the overlay and panel show it, the voice
   answers in it (Sarvam STT, Malayalam->English for matching English labels, Bulbul TTS). Panel switch and
   overlay language: done (coordinator). Voice: building.
3. The problem domain (GST or something else) is chosen **after** these basics work. The GST plan below is parked.

## Sarvam credits

Organiser-provided: 600 credits (Abin, 21 Nov). Abin posts the remaining balance from the dashboard
(https://indus.sarvam.ai/rate-limits) from time to time; log it here with the time. Every agent that calls Sarvam
reports how many calls it made, by API. Rate limits: 60 req/min for speech-to-text, text-to-speech and translate.
Both Sarvam MCPs (`sarvam`, `sarvam-docs`) are installed at user scope for new Claude sessions.

| Time (IST) | Balance | Source |
|---|---|---|
| 21 Nov 20:10 | key verified with 1 chat call | orchestrator |
| 21 Nov 20:40 | ~48 calls used so far: 1 chat (key check), 5 voice smoke, 1 TTS (panel test), 39 planner eval, ~2 planner live | agents' reports; Abin to post dashboard balance |
| 21 Nov ~20:45 | **597 of 600 left** (~3 credits for ~48 calls: chat, STT, TTS are cheap; budget is not a constraint for testing) | Abin, dashboard |

## Parked: GST hero demo (decided earlier on 21 Nov, on hold)

**One person:** a Kerala shop owner (e.g. a hardware or textile shop in Alappuzha) on the GST
**regular scheme**, turnover **under ₹5 crore**, who files **GSTR-3B monthly** because B2B customers
want their input tax credit each month. The accountant usually prepares the numbers; the owner, or
a family member, wants to do the filing or check it on the shop computer. QRMP quarterly filers see
the same GSTR-3B screens, so the demo covers them too.

**One task:** file this month's GSTR-3B on a practice copy of the GST portal, guided in Malayalam:
Returns Dashboard → choose financial year and period → GSTR-3B "Prepare Online" → check the
auto-filled sales (Table 3.1) → check input tax credit against GSTR-2B (Table 4) → save → proceed to
payment and offset the liability → reach the file step (EVC/OTP), where training ends and nothing is filed.

**The companion explains, the owner decides.** It says in Malayalam what each table means and points
at the control. It never computes tax or tells the owner what number to enter; numbers come from the
owner's (synthetic) books.

**Out of scope:** GSTR-1 invoice entry, IMS accept/reject, e-invoice, e-way bills, composition
(CMP-08/GSTR-4), annual returns, refunds, real login, tax advice.

**Facts to verify from official GSTN sources before they appear on screen or in the pitch:**
GSTR-3B screen labels and order (GST portal user manual), the July 2025 lock on auto-filled Table 3
values (corrections via GSTR-1A), the QRMP ₹5 crore limit, the Kerala taxpayer count.

**Pitch numbers (checked so far):** 52.6% of Indian MSMEs find choosing digital tools difficult;
46.2% fully offline (India SME Forum, Dec 2025, n=7,835, sampling to confirm). Kerala adults: 26.4%
can create a document, 49.4% can email (MoSPI CMS 2025). No survey shows English causes the difficulty.

## Open risk: "build with Devin"

The official field guide says "Bring your own idea and build a project with Devin" (`.context/hackathon-brief.md`).
We build with Claude and Codex. Abin to confirm with organisers whether Devin must do the building, and whether
Sarvam must be called at runtime for the Sarvam prize (we do call it at runtime: speech in, speech out).

## Features

| Feature | Status | Owner | Evidence / next |
|---|---|---|---|
| Reader, scripted planner, validator, loop | merged | coordinator | QA green on merged tree (runs/qa/20261121-201515) |
| QA skill + runner | merged, growing | Sonnet QA | Web, overlay, opt-in voice checks + machine-wide lock; merged suite 18 pass / 0 fail |
| Web reader + practice web app (Safari; Brave isolated profile) | merged | Codex sol | Practice page only (title + local URL match). **Next: read any page in the front browser window when the user asks** |
| Sketch overlay | merged incl. taste pass (fc95633) | Codex astra | Offset rough strokes, 2° note with shadow, short arrow. Nit: Malayalam glyphs read slightly smaller than Latin |
| Sarvam voice (Saaras v4 ml/en + translate, Bulbul, mic helper) | merged + wired into panel | Codex sol + coordinator | Live: Malayalam reply spoken on Safari practice page. Real mic needs Abin to allow the macOS prompt |
| Language preference (panel + overlay + voice) | merged | coordinator | `--lang ml|en`, switch in panel |
| Sarvam planner (LLM picks the control on any page) | merged; fixing | Codex sol + coordinator (async in app) | 10/17 exact on first eval; live: rejected a valid target over label wording. Fix + accuracy push briefed |
| AIMS fixture | reference | coordinator | regression target in QA |
| GST practice portal | parked | — | — |
