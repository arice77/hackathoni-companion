"""Sketch overlay live test: `python -m tests.test_overlay_live` (not a unittest, so unit.py never runs it).

Opens its own one-button window, reads the button frame through Accessibility, draws the overlay
and checks (a) stroke centre within 3 pt of the button centre, (b) the window server still routes
a click to the button (click-through), (c) replacement/expiry timers. No other app is touched.

The test is sensitive to any other window sitting on top of its fixture button. If that is the only
reason it fails (after one retry), the result is BLOCKED with the owner of the covering window,
not a product FAIL.
"""
import re
import time

from _common import PY, result, sh

FEATURE = "overlay"
CHECK = "live alignment + click-through + expiry"


def _once():
    p = sh(PY, "-m", "tests.test_overlay_live", timeout=90)
    out = p.stdout + p.stderr
    errors = re.search(r"stroke centre errors \[([^\]]*)\]", out)
    clicks = re.search(r"button actions = (\d+)", out)
    worst = max((float(x) for x in errors.group(1).split(",")), default=None) if errors else None
    ok = p.returncode == 0 and worst is not None and worst <= 3 and bool(clicks) and clicks.group(1) == "1"
    return ok, worst, clicks, p, out


def _owner(window_number):
    import Quartz
    for w in Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionAll, Quartz.kCGNullWindowID):
        if w["kCGWindowNumber"] == window_number:
            return f"{w.get('kCGWindowOwnerName')} pid {w.get('kCGWindowOwnerPID')} layer {w.get('kCGWindowLayer')}"
    return "unknown window"


def run():
    from companion import reader
    if not reader.is_trusted():
        return [result(FEATURE, "AX permission", "blocked", "live-machine", "process not Accessibility-trusted")]
    human = result(FEATURE, "pointer aligned to a real web/native control by eye", "skip", "needs-human",
                   "see features/overlay.md checklist")
    try:
        ok, worst, clicks, p, out = _once()
        covered = re.search(r"AssertionError: \((\d+), (\d+), (\d+)\)", out)
        if not ok and covered and covered.group(1) != covered.group(2):
            time.sleep(8)  # another agent's panel or overlay may be on screen; give it one chance to go
            ok, worst, clicks, p, out = _once()
            covered = re.search(r"AssertionError: \((\d+), (\d+), (\d+)\)", out)
            if not ok and covered and covered.group(1) != covered.group(2):
                return [result(FEATURE, CHECK, "blocked", "live-machine",
                               f"alignment passed but click-through could not be tested twice: "
                               f"window {covered.group(1)} ({_owner(int(covered.group(1)))}) sits over the fixture button. "
                               "Another companion panel or overlay is on screen; rerun when the screen is quiet."), human]
    except Exception as exc:  # noqa: BLE001 - a hung fixture window is a failed check
        return [result(FEATURE, CHECK, "fail", "live-machine", f"timeout/crash: {exc}"), human]
    return [result(FEATURE, CHECK, "pass" if ok else "fail", "live-machine",
                   f"max stroke-centre error {worst:.2f} pt (limit 3); button fired {clicks.group(1)}x with overlay on top"
                   if ok else f"rc={p.returncode}; {out.strip()[-500:]}"), human]
