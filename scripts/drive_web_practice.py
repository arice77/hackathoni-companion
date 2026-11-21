"""TEST-ONLY driver for our synthetic web practice form in Safari.

Sets values, ticks the box and presses buttons through Accessibility so the companion's
step progression can be checked without a person. Not product behaviour: in the demo the
person clicks themselves.

Safety rules, enforced here:
  * Only Safari (com.apple.Safari), only a window titled like the practice page, and only
    inside the AXWebArea whose AXURL is exactly http://127.0.0.1:$CONDUCTOR_PORT/ .
  * Controls are found by DOM id inside that web area. No other window, tab or app is
    ever walked, read or pressed. Never point this at a personal browser profile.
  * Values written are obviously fake and live only in the practice page (nothing is sent).

    .venv/bin/python scripts/drive_web_practice.py [--delay 1.5] [--steps N] [--sample]
"""

import argparse
import os
import sys
import time
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ApplicationServices as AX  # noqa: E402

from companion import reader  # noqa: E402

BUNDLE = reader.SAFARI
TITLE = reader.PRACTICE_TITLES[BUNDLE]
MAX_NODES = 1500
# Synthetic, obviously fake. NAME doubles as a leak canary for the reader checks.
NAME = "QA-CANARY Lantern Shop 731"
# Safari does not expose <select> popup menus to Accessibility (AXPress opens nothing readable), so
# the two selects are filled by the page's own "Use Sample Details" button. The name is typed first
# so the companion sees a field become filled on its own, then the sample button fills the rest.
ORDER = ["business-name", "sample-details", "details-next",
         "attach-sample", "documents-next", "declaration", "save"]
SAMPLE_ORDER = ["sample-details", "details-next", "attach-sample", "documents-next", "declaration", "save"]
DOM_ATTRS = ("AXDOMIdentifier", "AXIdentifier")


def practice_url() -> str:
    return f"http://127.0.0.1:{os.environ.get('CONDUCTOR_PORT') or '8765'}/"


def _get(el, name):
    err, value = AX.AXUIElementCopyAttributeValue(el, name, None)
    return value if err == 0 else None


def web_areas() -> list:
    """Every practice web area in Safari whose title and URL match exactly (usually one)."""
    app = reader.find_app(BUNDLE)
    if app is None:
        return []
    root = AX.AXUIElementCreateApplication(app.processIdentifier())
    found = []
    for window in _get(root, "AXWindows") or []:
        if _get(window, "AXTitle") != TITLE:
            continue  # other windows are never walked
        queue, seen = deque([window]), 0
        while queue and seen < MAX_NODES:
            el = queue.popleft()
            seen += 1
            role = _get(el, "AXRole")
            if role == "AXWebArea":
                if str(_get(el, "AXURL")) == practice_url():
                    found.append(el)
                continue  # never descend into a non-matching page
            queue.extend(_get(el, "AXChildren") or [])
    return found


def page():
    areas = web_areas()
    if len(areas) != 1:
        raise SystemExit(f"expected exactly one practice page at {practice_url()} in Safari, found {len(areas)}")
    return areas[0]


def element_for(ident, area=None):
    queue, seen = deque([area or page()]), 0
    while queue and seen < MAX_NODES:
        el = queue.popleft()
        seen += 1
        for name in DOM_ATTRS:
            if _get(el, name) == ident:
                return el
        queue.extend(_get(el, "AXChildren") or [])
    raise SystemExit(f"no element with DOM id {ident!r} on the practice page")


def read_value(ident):
    """Test-side read of a control's value (the reader itself never exposes it)."""
    return _get(element_for(ident), "AXValue")


def act(ident):
    el = element_for(ident)
    role = _get(el, "AXRole")
    if role == "AXTextField":
        AX.AXUIElementSetAttributeValue(el, "AXFocused", True)  # WebKit ignores AXValue until focused
        time.sleep(0.2)
        err = AX.AXUIElementSetAttributeValue(el, "AXValue", NAME)
        if err or _get(el, "AXValue") != NAME:
            raise SystemExit(f"could not set {ident}: AX error {err}")
    elif role == "AXCheckBox":
        if not _get(el, "AXValue"):
            AX.AXUIElementPerformAction(el, "AXPress")
    else:
        AX.AXUIElementPerformAction(el, "AXPress")
    return role


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=1.5)
    ap.add_argument("--steps", type=int, default=None)
    ap.add_argument("--sample", action="store_true", help="fill with the page's Use Sample Details button")
    a = ap.parse_args()
    order = SAMPLE_ORDER if a.sample else ORDER
    for ident in order[: a.steps]:
        time.sleep(a.delay)
        print(ident, act(ident), flush=True)
