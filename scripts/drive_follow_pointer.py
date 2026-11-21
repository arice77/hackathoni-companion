"""TEST-ONLY follow-the-pointer driver for our local practice pages (pizza, KSEB Quick Pay) in Safari.

Tails the companion's session log (runs/session-*.jsonl). On each new `point` decision it acts ONLY
on the pointed control, the way a person following the pointer would, then waits for the next decision:

  text field / text area   types a short synthetic sample
  choice set (fieldset)    presses its first option (the user would choose; QA just needs progress)
  single radio option      presses it
  button                   presses it
  optional units           checkbox set, single checkbox, time input: presses the companion panel's Skip button
                           (AXIdentifier `companion-skip`, found only in the companion process given by
                           --companion-pid; Safari's time input cannot be driven, and nothing optional is ticked).
                           Without --companion-pid these are left alone and the stop rules below end the run.
  link                     does nothing (detours such as Refresh are never followed)
  clarify "Scroll down..."  scrolls ONLY our page: moves the vertical scrollbar of the web area's scroll area through
                           Accessibility by 60% of a viewport (no cursor, no keys, no other window), then waits for the
                           next decision. At most --max-scrolls per run; a scroll that cannot move ends the run.

Stops on: `complete` (done), any other terminal decision (a scroll clarify is not terminal), the same target pointed at `--repeat-limit`
times, no new decision within `--decision-timeout`, or `--total-timeout`.

Safety rules, enforced here (same as drive_web_practice.py):
  * Safari only; only the window titled like the chosen page (--page pizza|kseb); only the AXWebArea whose AXURL is
    exactly http://127.0.0.1:$CONDUCTOR_PORT/<path> . No other window, tab or app is walked or pressed.
  * The pointed control is found by the logged frame. If no control of this page matches it, nothing is
    pressed and the miss is recorded.
  * The only thing pressed outside the page is `companion-skip` in the companion's own window (our own app).
  * Writes only synthetic values into the page. Never run against a personal browser profile.

    .venv/bin/python scripts/drive_follow_pointer.py --log runs/session-XXXX.jsonl --out runs/follow.jsonl
"""

import argparse
import json
import os
import sys
import time
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ApplicationServices as AX  # noqa: E402

from companion import reader  # noqa: E402

BUNDLE = reader.SAFARI
PAGES = {"pizza": ("HackaThoni · Pizza Order Practice", "/pizza"),
         "kseb": ("HackaThoni · KSEB Quick Pay Practice", "/kseb-quickpay")}
TITLE, PATH = PAGES["pizza"]  # default; configure() switches (main() does it from --page)


def configure(page: str) -> None:
    global TITLE, PATH
    TITLE, PATH = PAGES[page]
MAX_NODES = 1500
TEXT_ROLES = {"AXTextField", "AXTextArea"}
CHOICE_ROLES = {"AXRadioButton", "AXCheckBox"}
TARGET_ROLES = TEXT_ROLES | CHOICE_ROLES | {"AXButton", "AXLink", "AXGroup", "AXRadioGroup", "AXDateTimeArea", "AXTimeField",
                                            "AXPopUpButton", "AXComboBox"}
MIN_IOU = 0.6


def page_url() -> str:
    return f"http://127.0.0.1:{os.environ.get('CONDUCTOR_PORT') or '8765'}{PATH}"


def _get(el, name):
    err, value = AX.AXUIElementCopyAttributeValue(el, name, None)
    return value if err == 0 else None


def _frame(el):
    pos, size = _get(el, "AXPosition"), _get(el, "AXSize")
    if pos is None or size is None:
        return None
    ok1, p = AX.AXValueGetValue(pos, AX.kAXValueCGPointType, None)
    ok2, s = AX.AXValueGetValue(size, AX.kAXValueCGSizeType, None)
    return (float(p.x), float(p.y), float(s.width), float(s.height)) if ok1 and ok2 else None


def iou(a, b) -> float:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    w = min(ax + aw, bx + bw) - max(ax, bx)
    h = min(ay + ah, by + bh) - max(ay, by)
    if w <= 0 or h <= 0:
        return 0.0
    inter = w * h
    return inter / (aw * ah + bw * bh - inter)


def pizza_area(wait: float = 3.0):
    """The single practice web area for the configured page in Safari (exact URL), or SystemExit.
    (Named for the first page; it serves every page in PAGES.) Safari's tree is briefly empty around window
    changes, so look for up to `wait` seconds."""
    end = time.time() + wait
    while True:
        try:
            return _pizza_area_once()
        except SystemExit:
            if time.time() >= end:
                raise
            time.sleep(0.4)


def _pizza_area_once():
    app = reader.find_app(BUNDLE)
    if app is None:
        raise SystemExit("Safari is not running")
    root = AX.AXUIElementCreateApplication(app.processIdentifier())
    found = []
    for window in _get(root, "AXWindows") or []:
        if _get(window, "AXTitle") != TITLE:
            continue  # other windows are never walked
        queue, seen = deque([window]), 0
        while queue and seen < MAX_NODES:
            el = queue.popleft()
            seen += 1
            if _get(el, "AXRole") == "AXWebArea":
                if str(_get(el, "AXURL")) == page_url():
                    found.append(el)
                continue
            queue.extend(_get(el, "AXChildren") or [])
    if len(found) != 1:
        raise SystemExit(f"expected exactly one pizza page at {page_url()} in Safari, found {len(found)}")
    return found[0]


def _label(el) -> str:
    for name in ("AXTitle", "AXDescription", "AXPlaceholderValue"):
        v = _get(el, name)
        if isinstance(v, str) and v.strip():
            return v.strip()
    rel = _get(el, "AXTitleUIElement")
    if rel is not None:
        v = _get(rel, "AXValue") or _get(rel, "AXTitle")
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def controls(area):
    """All candidate elements on the page: (element, role, label, frame)."""
    out, queue, seen = [], deque([area]), 0
    while queue and seen < MAX_NODES:
        el = queue.popleft()
        seen += 1
        role = _get(el, "AXRole")
        frame = _frame(el)
        if role in TARGET_ROLES and frame and frame[2] > 0 and frame[3] > 0:
            # Fieldsets are AXGroup with a description; anonymous wrapper groups have no label.
            label = _label(el)
            if role != "AXGroup" or label:
                out.append((el, role, label, frame))
        queue.extend(_get(el, "AXChildren") or [])
    return out


def match(area, frame):
    best, score = None, 0.0
    for item in controls(area):
        s = iou(frame, item[3])
        if s > score:
            best, score = item, s
    return (best, score) if best and score >= MIN_IOU else (None, score)


def descendants(el, roles):
    out, queue = [], deque(_get(el, "AXChildren") or [])
    while queue:
        e = queue.popleft()
        if _get(e, "AXRole") in roles:
            out.append(e)
        queue.extend(_get(e, "AXChildren") or [])
    return out


SCROLL_WORDS = ("scroll",)


def is_scroll_clarify(kind: str, text: str) -> bool:
    return kind == "clarify" and any(w in (text or "").lower() for w in SCROLL_WORDS)


def scroll_down(area, fraction: float = 0.6) -> str:
    """Scroll the page of `area` (an AXWebArea) down by `fraction` of its viewport via the scroll area's vertical
    scrollbar. Only our own window's page moves. Returns a result string starting 'scrolled' on success."""
    parent = _get(area, "AXParent")
    if parent is None or _get(parent, "AXRole") != "AXScrollArea":
        return "scroll failed: web area has no scroll area"
    bar = _get(parent, "AXVerticalScrollBar")
    page, view = _frame(area), _frame(parent)
    value = _get(bar, "AXValue") if bar is not None else None
    if bar is None or not isinstance(value, (int, float)) or not page or not view:
        return "scroll failed: no readable vertical scrollbar"
    room = page[3] - view[3]
    if room <= 1:
        return "scroll failed: page fits the window (nothing to scroll)"
    if value >= 0.999:
        return "scroll failed: already at the bottom"
    target = min(1.0, float(value) + fraction * view[3] / room)
    err = AX.AXUIElementSetAttributeValue(bar, "AXValue", target)
    if err:
        return f"scroll failed: scrollbar refused AXValue (AX error {err})"
    time.sleep(0.6)
    now = _get(bar, "AXValue")
    moved = isinstance(now, (int, float)) and now > value + 1e-4
    return f"scrolled page down to {float(now):.2f}" if moved else "scroll failed: scrollbar did not move"


def is_filled(el, role):
    """Test-side read of whether the control already holds something (None = unknown)."""
    if role in TEXT_ROLES:
        v = _get(el, "AXValue")
        return isinstance(v, str) and v.strip() != ""
    if role in CHOICE_ROLES:
        return bool(_get(el, "AXValue"))
    if role in {"AXGroup", "AXRadioGroup"}:
        return any(bool(_get(o, "AXValue")) for o in descendants(el, CHOICE_ROLES))
    return None


def sample_for(label: str) -> str:
    low = label.lower()
    if "consumer" in low:
        return "1234567890123"
    if "mobile" in low:
        return "9000000000"
    if "text shown" in low or "captcha" in low:
        return "PRACTICE"  # the practice page's fixed image text
    if "tel" in low or "phone" in low:
        return "0000000000"
    if "mail" in low:
        return "qa.sample@example.invalid"
    return "QA Sample"


SKIP_ID = "companion-skip"
SKIP_ROLES = {"AXCheckBox", "AXDateTimeArea", "AXTimeField"}


def is_optional_unit(el, role) -> bool:
    """Controls the driver never fills: a checkbox set (a group without radio options), a single checkbox,
    the time input. The planner offers them as optional; the driver presses Skip."""
    if role in SKIP_ROLES:
        return True
    return role in {"AXGroup", "AXRadioGroup"} and not descendants(el, {"AXRadioButton"})


def press_skip(pid: int) -> str:
    """AXPress the companion panel's Skip button. Looks only inside the given companion process."""
    root = AX.AXUIElementCreateApplication(pid)
    queue, seen = deque([root]), 0
    while queue and seen < MAX_NODES:
        el = queue.popleft()
        seen += 1
        if _get(el, "AXIdentifier") == SKIP_ID:
            err = AX.AXUIElementPerformAction(el, "AXPress")
            return "pressed Skip" if not err else f"Skip press failed (AX error {err})"
        queue.extend(_get(el, "AXChildren") or [])
    return "Skip button not found in the companion window"


def act(el, role, label):
    """Do what a person following the pointer would. Returns a short result string."""
    if role in TEXT_ROLES:
        AX.AXUIElementSetAttributeValue(el, "AXFocused", True)  # WebKit ignores AXValue until focused
        time.sleep(0.2)
        want = sample_for(label)
        err = AX.AXUIElementSetAttributeValue(el, "AXValue", want)
        return "typed sample" if not err and _get(el, "AXValue") == want else f"type failed (AX error {err})"
    if role in {"AXGroup", "AXRadioGroup"}:
        options = descendants(el, {"AXRadioButton"})
        if not options:
            return "set has no radio options (optional checkbox set left alone)"
        AX.AXUIElementPerformAction(options[0], "AXPress")
        return f"pressed first option {_label(options[0])!r}"
    if role == "AXRadioButton":
        AX.AXUIElementPerformAction(el, "AXPress")
        return "pressed radio option"
    if role == "AXButton":
        AX.AXUIElementPerformAction(el, "AXPress")
        return "pressed button"
    if role == "AXCheckBox":
        return "left unticked (optional)"
    if role == "AXLink":
        return "left alone (links are detours)"
    return f"cannot drive {role} through Accessibility"


class Tail:
    def __init__(self, path: Path):
        self.path, self.offset = path, 0

    def new_events(self):
        events = []
        if self.path.exists():
            with self.path.open() as fh:
                fh.seek(self.offset)
                for line in fh:
                    if not line.endswith("\n"):
                        break  # half-written line; read it next time
                    self.offset += len(line.encode())
                    try:
                        events.append(json.loads(line))
                    except ValueError:
                        pass
        return events


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--page", choices=sorted(PAGES), default="pizza", help="which local practice page to act on")
    ap.add_argument("--log", type=Path, required=True, help="companion session log to tail")
    ap.add_argument("--out", type=Path, help="write one JSON line per handled decision plus a final summary")
    ap.add_argument("--decision-timeout", type=float, default=45.0)
    ap.add_argument("--total-timeout", type=float, default=300.0)
    ap.add_argument("--repeat-limit", type=int, default=3)
    ap.add_argument("--poll", type=float, default=0.3)
    ap.add_argument("--companion-pid", type=int, help="pid of the companion app whose Skip button may be pressed")
    ap.add_argument("--settle", type=float, default=0.6, help="pause after acting so the page redraws")
    ap.add_argument("--max-scrolls", type=int, default=4, help="most 'Scroll down' clarifies answered with a scroll")
    a = ap.parse_args(argv)
    configure(a.page)

    tail, records, seen_targets, scrolls = Tail(a.log), [], {}, 0
    start = last_decision = time.time()
    stop = None

    def emit(rec):
        records.append(rec)
        print(json.dumps(rec, ensure_ascii=False), flush=True)

    while stop is None:
        now = time.time()
        if now - start > a.total_timeout:
            stop = "total-timeout"
            break
        if now - last_decision > a.decision_timeout:
            stop = "decision-timeout"
            break
        for ev in tail.new_events():
            if ev.get("event") == "reader_error":
                emit({"event": "reader_error", "error": ev.get("error")})
            if ev.get("event") != "decision":
                continue
            last_decision = time.time()
            rec = {"event": "decision", "index": sum(r["event"] == "decision" for r in records),
                   "kind": ev["kind"], "valid": ev.get("valid"), "instruction_en": ev.get("instruction_en", ""),
                   "frame": ev.get("frame"), "source": ev.get("source")}
            if ev["kind"] == "complete":
                emit({**rec, "action": "none"})
                stop = "complete"
                break
            if is_scroll_clarify(ev["kind"], rec["instruction_en"]):
                scrolls += 1
                result = scroll_down(pizza_area()) if scrolls <= a.max_scrolls else "scroll limit reached"
                emit({**rec, "action": result})
                if not result.startswith("scrolled"):
                    stop = "scroll-failed"
                    break
                time.sleep(a.settle)
                continue
            if ev["kind"] != "point":
                emit({**rec, "action": "none"})
                stop = f"terminal-decision:{ev['kind']}"
                break
            if not ev.get("valid") or not ev.get("frame"):
                emit({**rec, "action": "skipped: decision failed validation"})
                continue
            area = pizza_area()
            hit, score = match(area, tuple(ev["frame"]))
            if hit is None:
                emit({**rec, "action": "no matching control on the pizza page (nothing pressed)", "iou": round(score, 2)})
                stop = "unmatched-target"
                break
            el, role, label, frame = hit
            key = (role, label)
            seen_targets[key] = seen_targets.get(key, 0) + 1
            filled = is_filled(el, role)
            skipping = a.companion_pid is not None and is_optional_unit(el, role)
            result = press_skip(a.companion_pid) if skipping else act(el, role, label)
            if skipping and result != "pressed Skip":
                emit({**rec, "target_role": role, "target_label": label, "action": result})
                stop = "no-skip-button"
                break
            emit({**rec, "target_role": role, "target_label": label, "filled_before": filled,
                  "times_pointed": seen_targets[key], "action": result, "iou": round(score, 2)})
            if seen_targets[key] >= a.repeat_limit:
                stop = f"repeat:{label or role}"
                break
            time.sleep(a.settle)
        time.sleep(a.poll)

    summary = {"event": "stop", "reason": stop, "seconds": round(time.time() - start, 1),
               "decisions": sum(r["event"] == "decision" for r in records)}
    emit(summary)
    if a.out:
        a.out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n")
    return 0 if stop == "complete" else 1


if __name__ == "__main__":
    sys.exit(main())
