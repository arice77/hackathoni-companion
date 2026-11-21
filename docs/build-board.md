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

## Features

| Feature | Status | Owner | Files | Acceptance |
|---|---|---|---|---|
| Reader, scripted planner, validator, loop | merged | coordinator | `companion/*.py`, `companion/tasks/` | QA suite green (3/3 runs) |
| QA skill + runner | merged | coordinator | `.claude/skills/companion-qa/`, `scripts/qa/` | runs, grows per feature |
| AIMS fixture | prototype (reference) | coordinator | `apps/aims-training/`, `companion/tasks/aims.py` | e2e green |
| Web support (reader in browsers + practice web app) | building | Codex `gpt-6.2-sol` (workspace port-louis) | `companion/reader.py`, `apps/web-practice/`, `scripts/serve_web_practice.py`, `scripts/open_web_practice.sh`, `companion/tasks/web_practice.py` | reader sees page controls by DOM id without browser chrome; QA green |
| Language preference (panel + overlay) | merged | coordinator | `companion/app.py` | `--lang ml|en`, switch in panel, one language shown |
| Web QA coverage | planned | Sonnet QA | `scripts/drive_web*.py`, `scripts/qa/checks/web_*.py`, registry | e2e green 3/3 in Safari |
| GST practice portal | parked | — | — | — |
| Sketch overlay | building | Codex `gpt-6.2-astra` (workspace damascus) | `companion/overlay/**` | `PointerOverlay`; Malayalam renders; click-through proven on own window |
| Sarvam voice (ml/en ask + speak, mic) | building, needs key | Codex `gpt-6.2-sol` (workspace lome) | `companion/voice/**`, `scripts/sarvam_smoke.py` | live round trip both languages, or explicit BLOCKED |
