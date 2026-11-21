"""TEST-ONLY driver for our synthetic training form.

Fills fields and presses buttons through Accessibility so the companion's step
progression can be checked without a person. Only ever targets the training app's
bundle id. This is not product behaviour: in the demo the person clicks themselves.

    .venv/bin/python scripts/drive_training.py [--delay 1.5] [--steps N]
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ApplicationServices as AX  # noqa: E402

from companion import reader  # noqa: E402

BUNDLE = "in.hackathoni.crop-loss-training"
# Synthetic case: obviously fake identifiers.
CASE = {
    "classification": "Insurance & Calamity Relief Services",
    "service": "Crop Insurance Compensation",
    "calamity-date": "12-08-2026 (TEST FIR)",
    "calamity-type": "Flood",
    "calamity-description": "TRAINING: bund breach, field submerged 14 days",
    "insured-crop": "Paddy (TEST policy)",
    "crop-stage": "Mainfield",
    "quantity-applied": "100",
}
ORDER = ["classification", "service", "next",
         "calamity-date", "calamity-type", "calamity-description", "next",
         "insured-crop", "crop-stage", "quantity-applied", "crop-image", "add-crop", "next",
         "declaration"]


def element_for(ident):
    app = reader.find_app(BUNDLE)
    root = AX.AXUIElementCreateApplication(app.processIdentifier())
    stack = [root]
    while stack:
        el = stack.pop()
        err, v = AX.AXUIElementCopyAttributeValue(el, "AXIdentifier", None)
        if err == 0 and v == ident:
            return el
        err, kids = AX.AXUIElementCopyAttributeValue(el, "AXChildren", None)
        if err == 0 and kids:
            stack.extend(kids)
    raise SystemExit(f"no element {ident}")


def act(ident):
    el = element_for(ident)
    err, role = AX.AXUIElementCopyAttributeValue(el, "AXRole", None)
    if role == "AXTextField":
        AX.AXUIElementSetAttributeValue(el, "AXValue", CASE[ident])
    elif role == "AXPopUpButton":
        AX.AXUIElementPerformAction(el, "AXPress")
        items = []
        for _ in range(20):  # the menu can take a moment to open
            time.sleep(0.1)
            _, kids = AX.AXUIElementCopyAttributeValue(el, "AXChildren", None)
            if kids:
                _, items = AX.AXUIElementCopyAttributeValue(kids[0], "AXChildren", None)
                if items:
                    break
        if not items:
            raise SystemExit(f"menu for {ident} never opened")
        for it in items:
            _, title = AX.AXUIElementCopyAttributeValue(it, "AXTitle", None)
            if title == CASE[ident]:
                AX.AXUIElementPerformAction(it, "AXPress")
                break
    else:
        AX.AXUIElementPerformAction(el, "AXPress")
    return role


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=1.5)
    ap.add_argument("--steps", type=int, default=len(ORDER))
    a = ap.parse_args()
    for ident in ORDER[: a.steps]:
        time.sleep(a.delay)
        print(ident, act(ident), flush=True)
