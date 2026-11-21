# Build board

Orchestrator: coordinator session (Opus) · Process: `/conductor-orchestrator` · QA: `companion-qa` skill.
Status words: planned · building · in QA · in review · merged · demo-ready.

## Hero demo (decided 21 Nov 2026)

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
| GST practice portal + task script | planned | Codex builder | `apps/gst-practice/`, `companion/tasks/gst.py`, `scripts/restart_gst.sh` | labels cited to GSTN manual; reader sees all step controls; task script reaches file step |
| GST QA coverage | planned | Sonnet QA | `scripts/drive_gst.py`, `scripts/qa/checks/gst_*.py`, registry | e2e green 3/3 |
| Sketch overlay | planned | Codex builder | `companion/overlay/**` | `PointerOverlay`; Malayalam renders; click-through proven on own window |
| Sarvam voice | planned, needs key | Codex builder | `companion/voice/**`, `scripts/sarvam_smoke.py` | live round trip or explicit BLOCKED |
