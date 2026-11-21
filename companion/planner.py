"""Next-step planners.

`ScriptedPlanner` is a deterministic task guide for the crop-loss training form: it knows
the field order and picks the first unfinished control from the *live* snapshot. It does
not understand free-form language beyond a keyword check. It is labelled "scripted" in
the UI and logs so it is never mistaken for an AI planner. A Sarvam text planner can be
plugged in behind the same `decide()` signature (see planner_sarvam.py when present).

Malayalam wording below is a first draft and needs a native speaker's check.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

from .contracts import Control, Decision, Snapshot


class Planner(Protocol):
    name: str

    def decide(self, question: str, snap: Snapshot) -> Decision: ...


@dataclass(frozen=True)
class Step:
    identifier: str
    ml: str
    en: str


# (screen-title prefix, ordered steps, instruction for the screen's final button)
TASK = [
    ("Step 1 of 3", [
        Step("farmer-id", "‘Farmer Registration No.’ ബോക്സിൽ രജിസ്ട്രേഷൻ നമ്പർ ടൈപ്പ് ചെയ്യുക",
             "Type the registration number in ‘Farmer Registration No.’"),
        Step("panchayat", "‘Panchayat’ ലിസ്റ്റിൽ നിന്ന് നിങ്ങളുടെ പഞ്ചായത്ത് തിരഞ്ഞെടുക്കുക",
             "Choose your panchayat from ‘Panchayat’"),
        Step("krishi-bhavan", "‘Krishi Bhavan’ ലിസ്റ്റിൽ നിന്ന് കൃഷിഭവൻ തിരഞ്ഞെടുക്കുക",
             "Choose your Krishi Bhavan"),
        Step("survey-no", "നിലത്തിന്റെ ‘Survey Number’ ടൈപ്പ് ചെയ്യുക",
             "Type the field's ‘Survey Number’"),
        Step("land-area", "‘Land Area (ha)’ ബോക്സിൽ ആകെ സ്ഥലം ഹെക്ടറിൽ നൽകുക",
             "Enter the total land area in hectares"),
    ], Step("next", "എല്ലാം ശരിയാണോ എന്ന് നോക്കി ‘Next’ അമർത്തുക", "Check the details, then click ‘Next’")),
    ("Step 2 of 3", [
        Step("crop", "‘Crop’ ലിസ്റ്റിൽ ‘Paddy’ തിരഞ്ഞെടുക്കുക", "Choose ‘Paddy’ under ‘Crop’"),
        Step("season", "‘Season’ ലിസ്റ്റിൽ കൃഷി സീസൺ തിരഞ്ഞെടുക്കുക", "Choose the growing season"),
        Step("cause", "‘Cause of Loss’ ലിസ്റ്റിൽ നഷ്ടത്തിന്റെ കാരണം തിരഞ്ഞെടുക്കുക (ഉദാ: Flood)",
             "Choose what caused the loss, e.g. Flood"),
        Step("affected-area", "‘Affected Area (ha)’ ബോക്സിൽ നശിച്ച സ്ഥലം നൽകുക",
             "Enter the damaged area in hectares"),
    ], Step("next", "‘Date of Loss’ ശരിയാണോ എന്ന് നോക്കി ‘Next’ അമർത്തുക",
            "Check ‘Date of Loss’, then click ‘Next’")),
    ("Step 3 of 3", [
        Step("photo", "‘Field Photo’ എന്നതിന് അടുത്തുള്ള ബട്ടൺ അമർത്തി ഫോട്ടോ ചേർക്കുക",
             "Click the button next to ‘Field Photo’ to attach the photo"),
        Step("tax-receipt", "‘Land Tax Receipt’ ചേർക്കുക", "Attach the ‘Land Tax Receipt’"),
        Step("declaration", "വിവരങ്ങൾ ശരിയാണെന്ന് ഉറപ്പാക്കി ഈ ബോക്സ് ടിക്ക് ചെയ്യുക",
             "Tick the box once you're sure the details are correct"),
    ], Step("next", "‘Save Draft’ അമർത്തുക. ഒന്നും സമർപ്പിക്കില്ല.",
            "Click ‘Save Draft’. Nothing is submitted.")),
]

INTENT = re.compile(
    r"crop|loss|paddy|flood|claim|compensat|damage|apply|application|form|report|next|help|"
    r"നഷ്ട|നെല്ല്|കൃഷി|അപേക്ഷ|വെള്ളപ്പൊക്ക|ഫോം|nasht|krishi|nellu|apeksha",
    re.IGNORECASE,
)


def _by_ident(snap: Snapshot, ident: str) -> Control | None:
    return next((c for c in snap.controls if c.identifier == ident), None)


def _step_done(snap: Snapshot, ident: str) -> bool | None:
    file_note = _by_ident(snap, ident + "-file")
    if file_note is not None:  # attachment rows: the note next to the button says so
        return file_note.label.startswith("Attached")
    c = _by_ident(snap, ident)
    return None if c is None else bool(c.filled)


class ScriptedPlanner:
    name = "scripted"

    def decide(self, question: str, snap: Snapshot) -> Decision:
        sid = snap.snapshot_id
        q = question.strip()
        if not q:
            return Decision("clarify", sid, "എന്താണ് ചെയ്യേണ്ടത് എന്ന് പറയൂ.",
                            "Say or type what you want to do.", source="scripted")
        if not INTENT.search(q):
            return Decision("unsupported", sid,
                            "ഇപ്പോൾ വിളനഷ്ട അപേക്ഷയുടെ പരിശീലന ഫോം മാത്രമേ കാണിച്ചുതരാൻ കഴിയൂ.",
                            "Right now I can only guide the crop-loss training form.", source="scripted")

        status = _by_ident(snap, "status")
        if status and status.label.startswith("Draft saved"):
            return Decision("complete", sid, "ഡ്രാഫ്റ്റ് സേവ് ചെയ്തു. ഇത് പരിശീലനം മാത്രം — ഒന്നും സമർപ്പിച്ചിട്ടില്ല.",
                            "Draft saved. Training only — nothing was submitted.", source="scripted")

        title = _by_ident(snap, "screen-title")
        screen = next((s for s in TASK if title and title.label.startswith(s[0])), None)
        if screen is None:
            return Decision("unsupported", sid, "ഈ സ്ക്രീൻ തിരിച്ചറിയാൻ കഴിഞ്ഞില്ല.",
                            "I don't recognise this screen.", source="scripted")

        _, steps, final = screen
        for step in steps:
            done = _step_done(snap, step.identifier)
            if done is None:
                return Decision("unsupported", sid, "പ്രതീക്ഷിച്ച ബോക്സ് ഈ സ്ക്രീനിൽ കാണുന്നില്ല.",
                                f"Expected control ‘{step.identifier}’ is missing.", source="scripted")
            if not done:
                return Decision("point", sid, step.ml, step.en, _by_ident(snap, step.identifier).id, "scripted")
        target = _by_ident(snap, final.identifier)
        if target is None:
            return Decision("unsupported", sid, "‘Next’ ബട്ടൺ കാണുന്നില്ല.", "The Next button is missing.",
                            source="scripted")
        return Decision("point", sid, final.ml, final.en, target.id, "scripted")
