"""Voice keyterms regression (offline): labels with a comma or semicolon never reach Saaras (they made it return HTTP 400).

Calls the app's own `Companion.keyterms` on a synthetic snapshot (no window is created, no Sarvam call). Also checks the
provider-side limits the voice client enforces (at most 50 distinct terms, 64 characters) so a long page cannot break speech.
"""
from types import SimpleNamespace as NS

from _common import result
from companion.contracts import Control, Snapshot

FEATURE = "voice-sarvam"
CHECK = "keyterms: labels with , or ; are skipped, limits respected"


def run():
    from companion.app import Companion
    labels = ["Save Draft", "Search, filters", "Next; step", "Settings", "Settings", "x" * 41, "Playback speed Normal",
              "ഒഴിവാക്കൂ", "Sign in, or sign up"]
    controls = [Control(f"c{i}", "AXButton", label, (0, 0, 1, 1)) for i, label in enumerate(labels)]
    controls.append(Control("t", "AXStaticText", "Static headline", (0, 0, 1, 1)))
    controls += [Control(f"m{i}", "AXLink", f"Link {i}", (0, 0, 1, 1)) for i in range(80)]
    snap = Snapshot("s", 0, "com.apple.Safari", 1, "www.youtube.com", (0, 0, 1, 1), tuple(controls))
    terms = Companion.keyterms(NS(last_snapshot=snap))
    problems = []
    if any("," in t or ";" in t for t in terms):
        problems.append(f"comma/semicolon label kept: {[t for t in terms if ',' in t or ';' in t]}")
    for kept in ("Save Draft", "Settings", "Playback speed Normal", "ഒഴിവാക്കൂ"):
        if kept not in terms:
            problems.append(f"{kept!r} was dropped")
    if "Static headline" in terms or any(len(t) > 40 for t in terms):
        problems.append("static text or an over-long label was kept")
    if len(terms) > 50 or len(set(terms)) != len(terms):
        problems.append(f"{len(terms)} terms ({len(set(terms))} distinct) exceeds the provider limit of 50 distinct")
    if Companion.keyterms(NS(last_snapshot=None)) != []:
        problems.append("no snapshot did not give an empty list")
    return [result(FEATURE, CHECK, "fail" if problems else "pass", "automated",
                   "; ".join(problems) if problems else f"{len(terms)} terms kept, none with , or ;")]
