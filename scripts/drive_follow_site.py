"""TEST-ONLY follow-the-pointer driver for REAL sites (YouTube, Gmail) in ONE dedicated Safari window.

Tails the companion's session log (runs/session-*.jsonl). On each `point` decision it acts only on the pointed
control, the way a person following the pointer would, from an explicit allowlist, then waits for the next one.

Safety rules, enforced here:
  * Safari only, and only the window whose bounds equal --bounds (the QA check opened that window itself and
    set unusual bounds so it is unique). Zero or several matches: nothing is touched.
  * Only the AXWebArea of that window whose host is the chosen site's host.
  * The pointed control is found by the logged frame (hit-test, then a bounded walk of that window). No match:
    nothing is pressed.
  * "Scroll down" clarifies are answered by scrolling only our window's page (scrollbar of the web area's scroll
    area via Accessibility), at most --max-scrolls times.
  * Allowlist per site. Anything else the pointer lands on is NOT pressed and ends the run ("refused").
      youtube  type the song text into Search; press the Search button; press a result link only if it is a
               /watch link, names the song and is not an ad; press Play, Skip ad / Skip (ad button), Settings, Playback speed.
               Stops at the speed target (--stop-label) WITHOUT pressing it: no setting is applied.
               No like, subscribe or comment control is ever pressed.
      gmail    press Compose; type To (QA_GMAIL_TO), Subject, Message Body; say "Next" in the companion panel when the
               instruction asks for it (also to skip the optional "Attach files", which is never opened);
               press Send only with --allow-send
               AND QA_GMAIL_TO inside QA_GMAIL_ALLOWED (checked again here), at most once. If Send is gated, the
               driver stops before it and discards its own draft. Never opens, archives, deletes or marks mail.
  * Never prints or records typed values, addresses, subjects, senders or bodies. Gmail target labels are
    recorded only as fixed names from the reader's allowlist.
  * The only thing touched outside the page is the companion's own panel (--companion-pid): the question field
    and Ask button, to send the second question.

    .venv/bin/python scripts/drive_follow_site.py --site youtube --bounds L,T,R,B --log runs/session-X.jsonl
"""

import argparse
import json
import os
import re
import sys
import time
from collections import deque
from pathlib import Path
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import ApplicationServices as AX  # noqa: E402
from CoreFoundation import CFEqual  # noqa: E402

import drive_follow_pointer as base  # noqa: E402
from companion import reader  # noqa: E402

BUNDLE = reader.SAFARI
HOSTS = {"youtube": "youtube.com", "gmail": "mail.google.com"}
_get, _frame, iou, Tail = base._get, base._frame, base.iou, base.Tail
MIN_IOU = 0.6
MAX_NODES = 9000
TARGET_ROLES = {"AXTextField", "AXTextArea", "AXComboBox", "AXSearchField", "AXButton", "AXLink", "AXPopUpButton",
                "AXMenuButton", "AXMenuItem", "AXMenuItemRadio", "AXMenuItemCheckbox", "AXCheckBox", "AXRadioButton"}
SEARCH_ROLES = {"AXComboBox", "AXSearchField", "AXTextField"}
MENU_ROLES = {"AXMenuItem", "AXMenuItemRadio", "AXMenuItemCheckbox", "AXButton"}
FIELD_ROLES = {"AXComboBox", "AXTextField", "AXTextArea", "AXSearchField"}
SAY_NEXT = re.compile(r"say\s+[‘'\"]next[’'\"]", re.IGNORECASE)  # the pack asks the person to acknowledge a step
PLAYER_SHORTCUT = re.compile(r"(?:\s*\([a-z]\)|\s+keyboard shortcut\s+[a-z])$")
AD_WORDS = re.compile(r"\b(ad|ads|advert|advertisement|sponsored)\b", re.IGNORECASE)
SKIP_AD = re.compile(r"^(?:skip ads?\b|skip$)", re.IGNORECASE)  # "Skip ad(s)" and the bare "Skip" ad button (AXButton only)
SUBJECT_TEXT = "HackaThoni companion test"
BODY_TEXT = "This is a short test message from the HackaThoni companion check. Please ignore it."


# ---- pure helpers (unit-tested offline) --------------------------------------------------------------
def env_value(name: str) -> str:
    """Value from the environment, else repo-root .env (never printed)."""
    if os.environ.get(name):
        return os.environ[name].strip()
    env = HERE.parent / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            key, _, value = line.partition("=")
            if key.strip() == name:
                return value.strip().strip("'\"")
    return ""


def send_allowed() -> bool:
    """QA_GMAIL_TO is set and is one of the comma-separated QA_GMAIL_ALLOWED addresses (case-insensitive)."""
    to = env_value("QA_GMAIL_TO").lower()
    return bool(to) and to in {a.strip().lower() for a in env_value("QA_GMAIL_ALLOWED").split(",") if a.strip()}


def host_ok(url: str, site: str) -> bool:
    host = (urlparse(str(url)).hostname or "").lower()
    want = HOSTS[site]
    return host == want or host.endswith("." + want)


def decide_action(site: str, role: str, label: str, url: str, opts) -> tuple[str, str]:
    """(verb, why). verb: type:<what> | press | skip | hold | refuse. `label` is the raw (YouTube) or normalized (Gmail) name."""
    low = (label or "").strip().lower()
    if site == "youtube":
        if role in SEARCH_ROLES and low == "search":
            return "type:song", "search box"
        if role == "AXButton" and low == "search":
            return "press", "search button"
        if role == "AXLink":
            path = urlparse(str(url or "")).path
            if AD_WORDS.search(label or ""):
                return "refuse", "link looks like an ad"
            if not path.startswith("/watch"):
                return "refuse", "link is not a /watch result"
            if opts.song_token and opts.song_token.lower() not in low:
                return "refuse", "link does not name the song"
            return "press", "matching result"
        if role == "AXButton" and (low.startswith("play") or SKIP_AD.match(low)):
            return "press", "play or skip ad"
        if role in {"AXPopUpButton", "AXButton"} and low == "settings":
            return "press", "settings"
        if role in MENU_ROLES and low.startswith("playback speed"):
            return "press", "playback speed menu"
        if low.startswith("decrease playback speed") and getattr(opts, "apply_speed", False):
            if opts.decreases >= opts.max_decreases:
                return "refuse", f"more than {opts.max_decreases} Decrease presses"
            return "press", "speed stepper (decrease)"
        if getattr(opts, "player_controls", False):
            pl = PLAYER_SHORTCUT.sub("", low)
            if role == "AXButton" and pl in {"pause", "play", "mute", "unmute"}:
                return "press", "player control"
            if role == "AXButton" and pl in {"full screen", "exit full screen"}:
                # AXPress would move Safari into its own full-screen Space; the pointer is asserted, nothing is pressed
                return "hold", "full screen pointer asserted; not pressed (it would move Safari to its own Space)"
            if role == "AXCheckBox" and pl.startswith("subtitles/closed captions") and "unavailable" not in pl:
                return "press", "captions button"
            if role in MENU_ROLES and pl.startswith("subtitles/cc"):
                return "press", "subtitles menu"
            if role in MENU_ROLES and re.fullmatch(r"(?:malayalam|മലയാളം)(?:\s*\([^)]*\))?", pl):
                return "press", "Malayalam subtitles row"
            if role == "AXButton" and low in set(getattr(opts, "allow_presets", ()) or ()):
                return "press", "speed preset"
        if opts.stop_label and re.search(opts.stop_label, low):
            return "hold", "speed target reached; not pressed"
        return "refuse", "control is outside the YouTube allowlist"
    if site == "gmail":
        if low == "compose" and role == "AXButton":
            return "press", "compose"
        if low == "to" and role in FIELD_ROLES:
            return "type:to", "recipient"
        if low == "subject" and role in FIELD_ROLES:
            return "type:subject", "subject"
        if low == "message body" and role in FIELD_ROLES:
            return "type:body", "body"
        if low == "attach files" and role in {"AXPopUpButton", "AXButton"}:
            return "skip", "optional attachment: skipped, the dialog is never opened"
        if low == "send" and role == "AXButton":
            if not opts.allow_send or not send_allowed():
                return "hold", "send gated: QA_GMAIL_TO is not in QA_GMAIL_ALLOWED"
            if opts.sends >= 1:
                return "refuse", "a send already happened in this run"
            return "press", "send"
        return "refuse", "control is outside the Gmail compose allowlist"
    raise ValueError(site)


def bounds_match(frame, bounds, tol: float = 4.0) -> bool:
    l, t, r, b = bounds
    want = (l, t, r - l, b - t)
    return frame is not None and all(abs(a - w) <= tol for a, w in zip(frame, want))


# ---- Accessibility lookups ---------------------------------------------------------------------------
def safari_app():
    app = reader.find_app(BUNDLE)
    if app is None:
        raise SystemExit("Safari is not running")
    return app


def our_window(bounds, wait: float = 10.0):
    """The single Safari AX window with exactly these bounds, or SystemExit."""
    end = time.time() + wait
    while True:
        pid = safari_app().processIdentifier()
        root = AX.AXUIElementCreateApplication(pid)
        hits = [w for w in _get(root, "AXWindows") or [] if bounds_match(_frame(w), bounds)]
        if len(hits) == 1:
            return pid, hits[0]
        if time.time() >= end:
            raise SystemExit(f"expected exactly one Safari window with bounds {bounds}, found {len(hits)}")
        time.sleep(0.4)


def walk(root, limit: int = MAX_NODES):
    queue, seen = deque([root]), 0
    while queue and seen < limit:
        el = queue.popleft()
        seen += 1
        yield el
        queue.extend(_get(el, "AXChildren") or [])


def web_area_url(window, site: str) -> str | None:
    for el in walk(window, 3000):
        if _get(el, "AXRole") == "AXWebArea":
            url = str(_get(el, "AXURL") or "")
            if host_ok(url, site):
                return url
    return None


def web_area_el(window, site: str):
    for el in walk(window, 3000):
        if _get(el, "AXRole") == "AXWebArea" and host_ok(str(_get(el, "AXURL") or ""), site):
            return el
    return None


def _candidate(el, window):
    role, frame = _get(el, "AXRole"), _frame(el)
    if role not in TARGET_ROLES or not frame or frame[2] <= 0 or frame[3] <= 0:
        return None
    return el, role, base._label(el), frame


def locate(pid, window, site, frame):
    """The control of OUR window under the logged frame: (el, role, label, frame, score) or None."""
    if web_area_url(window, site) is None:
        return None
    cx, cy = frame[0] + frame[2] / 2, frame[1] + frame[3] / 2
    err, el = AX.AXUIElementCopyElementAtPosition(AX.AXUIElementCreateApplication(pid), cx, cy, None)
    for _ in range(6):
        if err != 0 or el is None:
            break
        cand = _candidate(el, window)
        owner = _get(el, "AXWindow")
        if cand and owner is not None and CFEqual(owner, window) and iou(frame, cand[3]) >= MIN_IOU:
            return (*cand, iou(frame, cand[3]))
        el = _get(el, "AXParent")
    best, score = None, 0.0
    for el in walk(window):
        cand = _candidate(el, window)
        if cand and (s := iou(frame, cand[3])) > score:
            best, score = cand, s
    return (*best, score) if best and score >= MIN_IOU else None


def find_by_label(window, site, role_set, predicate):
    """First control in our window whose raw label satisfies predicate (test-side reads and cleanup)."""
    if web_area_url(window, site) is None:
        return None
    for el in walk(window):
        cand = _candidate(el, window)
        if cand and cand[1] in role_set and predicate(cand[2]):
            return cand
    return None


def any_text(window, needle: str) -> bool:
    """Does any element of our window carry `needle` in its title, description or value? (never printed)"""
    for el in walk(window):
        for attr in ("AXTitle", "AXDescription", "AXValue"):
            v = _get(el, attr)
            if isinstance(v, str) and needle.lower() in v.lower():
                return True
    return False


def gmail_name(el, role):
    try:
        return reader._gmail_label(el, role, _get)
    except Exception:  # noqa: BLE001
        return None


# ---- actions -----------------------------------------------------------------------------------------
def type_text(el, text: str) -> str:
    AX.AXUIElementSetAttributeValue(el, "AXFocused", True)  # WebKit ignores AXValue until focused
    time.sleep(0.25)
    err = AX.AXUIElementSetAttributeValue(el, "AXValue", text)
    return "typed (value not recorded)" if not err else f"type failed (AX error {err})"


def press(el) -> str:
    err = AX.AXUIElementPerformAction(el, "AXPress")
    return "pressed" if not err else f"press failed (AX error {err})"


def ask_companion(pid: int, text: str) -> str:
    """Type the next question into the companion panel's field and press Ask (our own app)."""
    root = AX.AXUIElementCreateApplication(pid)
    field = button = None
    for el in walk(root, 800):
        role = _get(el, "AXRole")
        if role == "AXTextField" and field is None:
            field = el
        if role == "AXButton" and _get(el, "AXTitle") in {"Ask", "ചോദിക്കൂ"}:
            button = el
    if field is None or button is None:
        return "companion question field or Ask button not found"
    AX.AXUIElementSetAttributeValue(field, "AXFocused", True)
    time.sleep(0.2)
    AX.AXUIElementSetAttributeValue(field, "AXValue", text)
    time.sleep(0.2)
    return "asked" if AX.AXUIElementPerformAction(button, "AXPress") == 0 else "Ask press failed"


def discard_draft(pid, window) -> str:
    cand = find_by_label(window, "gmail", {"AXButton"}, lambda l: l.lower().startswith("discard draft"))
    if cand is None:
        return "draft discard button not found; a draft may remain"
    return "draft discarded" if press(cand[0]) == "pressed" else "draft discard failed"


MENU_NAMES = ("settings", "playback", "quality", "subtitles", "ambient", "annotations", "sleep", "skip", "play", "pause")


AD_HINT = re.compile(r"^(skip|ad\b|my ad centre|video will play after|ad will end|sponsored)", re.IGNORECASE)


def ad_hints(window) -> list[str]:
    """Raw labels in our window that suggest an ad is playing (public YouTube UI strings, never page content)."""
    out = []
    for el in walk(window):
        label = base._label(el)
        if label and AD_HINT.match(label) and not label.lower().startswith("skip navigation") and label[:40] not in out:
            out.append(label[:40])
    return out[:8]


def reader_diagnostic() -> dict:
    """What the reader itself reports for the player menu right now: role, label, enabled (public YouTube labels)."""
    try:
        snap = reader.snapshot(BUNDLE, page_url_prefix="https://www.youtube.com/")
    except Exception as exc:  # noqa: BLE001
        return {"event": "diagnostic", "error": str(exc)[:160]}
    rows = [[c.role, c.label[:50], c.enabled, c.filled] for c in snap.controls
            if c.role.startswith("AXMenu") or c.label.lower().startswith(MENU_NAMES)]
    return {"event": "diagnostic", "controls": len(snap.controls), "rows": rows}


SPEED_SLIDER = re.compile(r"^playback speed slider\s*([\d.]+)", re.IGNORECASE)


def speed_now(window):
    """Playback speed read from the slider (the reader's name 'Playback speed slider <n>', else its AXValue), or None."""
    for el in walk(window):
        if _get(el, "AXRole") == "AXSlider":
            m = SPEED_SLIDER.match(base._label(el) or "")
            if m:
                return float(m.group(1))
    for el in walk(window):  # the panel's unlabelled slider carries the value
        if _get(el, "AXRole") == "AXSlider" and not (base._label(el) or "").strip():
            v = _get(el, "AXValue")
            if isinstance(v, (int, float)) and 0.1 <= float(v) <= 4:
                return float(v)
    return None


def panel_open(window) -> bool:
    return find_by_label(window, "youtube", {"AXButton"}, lambda l: l.lower().startswith("decrease playback speed")) is not None


def menu_open(window) -> bool:
    return find_by_label(window, "youtube", {"AXMenuItem"}, lambda l: l.lower().startswith(("ambient mode", "playback speed"))) is not None


def restore_speed(bounds) -> dict:
    """Put the speed back to Normal (the 1.0 preset, reopening the panel if needed) and close the Settings menu.
    The slider only exists while the speed panel is open, so the last value it showed is what counts."""
    last = None
    for _ in range(6):
        pid, window = our_window(bounds)
        now = speed_now(window)
        if now is not None:
            last = now
        opened = panel_open(window) or menu_open(window)
        if last == 1.0 and not opened:
            break
        gear = find_by_label(window, "youtube", {"AXPopUpButton"}, lambda l: l.strip().lower() == "settings")
        if panel_open(window) and now != 1.0:
            preset = find_by_label(window, "youtube", {"AXButton"}, lambda l: l.strip() in {"1.0", "1", "Normal"})
            if preset:
                press(preset[0])
        elif opened and last == 1.0:
            if gear:
                press(gear[0])  # closes the open menu
        elif not opened and gear:  # reopen: Settings, then Playback speed
            press(gear[0])
            time.sleep(1.2)
            pid, window = our_window(bounds)
            item = find_by_label(window, "youtube", {"AXMenuItem"}, lambda l: l.lower().startswith("playback speed"))
            if item:
                press(item[0])
        elif menu_open(window):  # Settings menu open but not the panel: open Playback speed
            item = find_by_label(window, "youtube", {"AXMenuItem"}, lambda l: l.lower().startswith("playback speed"))
            if item:
                press(item[0])
        time.sleep(1.2)
    pid, window = our_window(bounds)
    return {"speed_restored": last == 1.0, "speed_after": last,
            "menu_closed": not panel_open(window) and not menu_open(window)}


def final_tidy(bounds, speed_touched: bool = False) -> dict:
    """Leave the account as found after a player-controls walk: captions off, speed Normal, menus closed, unmuted, paused."""
    out = {}
    try:
        pid, window = our_window(bounds)
    except SystemExit as exc:
        return {"error": f"window gone: {str(exc)[:60]}"}

    def reread():
        return our_window(bounds)[1]

    cc = find_by_label(window, "youtube", {"AXCheckBox"}, lambda l: l.lower().startswith("subtitles/closed captions") and "unavailable" not in l.lower())
    if cc is not None and bool(base._get(cc[0], "AXValue")):
        press(cc[0])
        time.sleep(1.0)
    cc = find_by_label(reread(), "youtube", {"AXCheckBox"}, lambda l: l.lower().startswith("subtitles/closed captions") and "unavailable" not in l.lower())
    out["captions_off"] = cc is None or not bool(base._get(cc[0], "AXValue"))
    out.update(restore_speed(bounds) if panel_open(reread()) or menu_open(reread()) or speed_touched else {"speed_restored": True, "menu_closed": True})
    window = reread()
    if panel_open(window) or menu_open(window):
        gear = find_by_label(window, "youtube", {"AXPopUpButton"}, lambda l: l.strip().lower() == "settings")
        if gear:
            press(gear[0])
            time.sleep(1.0)
    window = reread()
    out["menu_closed"] = not panel_open(window) and not menu_open(window)
    unmute = find_by_label(window, "youtube", {"AXButton"}, lambda l: l.lower().startswith("unmute"))
    if unmute:
        press(unmute[0])
        time.sleep(0.8)
    out["unmuted"] = find_by_label(reread(), "youtube", {"AXButton"}, lambda l: l.lower().startswith("unmute")) is None
    pause = find_by_label(reread(), "youtube", {"AXButton"}, lambda l: l.lower().startswith("pause"))
    if pause:
        press(pause[0])
        time.sleep(0.8)
    out["paused"] = find_by_label(reread(), "youtube", {"AXButton"}, lambda l: l.lower().startswith("pause")) is None
    return out



def tidy_kind(phase: int, asks) -> str:
    """The tidy-up kind for the question that just ended (phase 2 is the first follow-up), or '' (never raises: Gmail has no
    follow-up list but its 'Next' acknowledgements still start new phases)."""
    return asks[phase - 2][1] if 2 <= phase <= len(asks) + 1 else ""


def next_ask(phase: int, asks):
    """The follow-up question to ask once `phase` ends, or None when there is none."""
    return asks[phase - 1][0] if 0 <= phase - 1 < len(asks) else None


# ---- main --------------------------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--site", choices=sorted(HOSTS), required=True)
    ap.add_argument("--bounds", required=True, help="L,T,R,B of the dedicated Safari window (AppleScript bounds)")
    ap.add_argument("--log", type=Path, required=True)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--companion-pid", type=int)
    ap.add_argument("--song-text", default="Darshana Hridayam", help="youtube: what the driver types into Search")
    ap.add_argument("--type-from-instruction", action="store_true",
                    help="youtube: type the text the planner's instruction quotes (between curly quotes) instead of --song-text")
    ap.add_argument("--song-token", default="darshana", help="youtube: a result link must contain this")
    ap.add_argument("--stop-label", default="", help="youtube: regex; stop (not pressing) when the pointer lands on it")
    ap.add_argument("--then-ask", action="append", default=[],
                    help="after the previous question completes, ask this in the panel; repeatable; 'text::kind' (kind: speed|menu) "
                         "runs that tidy-up when the question ends")
    ap.add_argument("--player-controls", action="store_true",
                    help="youtube: also press pause/play/mute/unmute, the captions button and Subtitles rows, allowed speed presets; "
                         "Full screen is pointed at but never pressed; an honest 'unsupported' ends a question without failing the run")
    ap.add_argument("--allow-presets", default="", help="youtube: comma-separated speed preset labels the driver may press, e.g. 1.25")
    ap.add_argument("--allow-send", action="store_true", help="gmail: Send may be pressed (needs the env gate too)")
    ap.add_argument("--keep-playing", action="store_true", help="youtube: do not pause the video between questions")
    ap.add_argument("--max-scrolls", type=int, default=4)
    ap.add_argument("--apply-speed", action="store_true",
                    help="youtube: press 'Decrease playback speed 0.05' each time it is pointed (max --max-decreases), "
                         "then restore Normal speed and close Settings")
    ap.add_argument("--max-decreases", type=int, default=6)
    ap.add_argument("--max-next", type=int, default=3, help="most times the driver says 'Next' in the panel (runaway guard)")
    ap.add_argument("--decision-timeout", type=float, default=45.0)
    ap.add_argument("--total-timeout", type=float, default=300.0)
    ap.add_argument("--repeat-limit", type=int, default=3)
    ap.add_argument("--poll", type=float, default=0.3)
    ap.add_argument("--settle", type=float, default=1.0)
    a = ap.parse_args(argv)
    a.sends = 0
    a.allow_presets = {x.strip().lower() for x in a.allow_presets.split(",") if x.strip()}
    asks = [tuple((item.split("::", 1) + [""])[:2]) for item in a.then_ask]
    a.decreases = 0
    nexts = 0
    bounds = tuple(float(x) for x in a.bounds.split(","))
    site = a.site

    tail, records = Tail(a.log), []
    phase, awaiting_q, scrolls = 0, False, 0
    phase_end, seen = {}, {}
    state = {"sends": 0, "sent_seen": None, "draft": None, "playing": None, "paused": None, "search_fallback": None,
             "decreases": 0, "speed_touched": False, "speed_restored": None, "menu_closed": None, "speed_after": None}
    start = last = time.time()
    dt = a.decision_timeout

    def emit(rec):
        records.append(rec)
        print(json.dumps(rec, ensure_ascii=False), flush=True)

    def finish_phase(reason: str, fatal: bool = False):
        """Record why this question's walk ended. Returns True when the whole run is over."""
        nonlocal awaiting_q, last
        phase_end[phase] = reason
        if site == "youtube" and reason in {"decision-timeout", "total-timeout"}:
            try:
                emit({**reader_diagnostic(), "ad_hints": ad_hints(our_window(bounds)[1])})
            except SystemExit:
                emit(reader_diagnostic())
        ok_reasons = {"complete", "reached-target"} | ({"unsupported"} if a.player_controls else set())
        if fatal and not (a.player_controls and reason == "unsupported") or reason not in ok_reasons:
            return True
        if (kind := tidy_kind(phase, asks)):
            emit({"event": "tidy", "after": asks[phase - 2][0][:40], **tidy(kind)})
        if next_ask(phase, asks) is None:
            return True
        if phase == 1:
            pid, window = our_window(bounds)
            if site == "youtube":
                url = web_area_url(window, site) or ""
                pause = find_by_label(window, site, {"AXButton"}, lambda l: l.lower().startswith("pause"))
                state["playing"] = pause is not None and "/watch" in url
                emit({"event": "state", "name": "after-find", "playing": state["playing"],
                      "url_watch": "/watch" in url})
                if state["playing"] and not a.keep_playing:
                    state["paused"] = press(pause[0]) == "pressed"  # keep the Mac quiet; not an account action
                    time.sleep(0.8)
        if a.companion_pid is None:
            phase_end[phase + 1] = "no --companion-pid to ask the next question"
            return True
        result = ask_companion(a.companion_pid, next_ask(phase, asks))
        emit({"event": "ask", "result": result, "n": phase})
        if result != "asked":
            phase_end[phase + 1] = result
            return True
        awaiting_q, last = True, time.time()
        return False

    def tidy(kind: str) -> dict:
        """Per-question tidy-up. speed: back to Normal and menus closed. menu: close an open Settings menu."""
        try:
            if kind == "speed":
                return restore_speed(bounds)
            pid, window = our_window(bounds)
            if kind == "menu" and (panel_open(window) or menu_open(window)):
                gear = find_by_label(window, "youtube", {"AXPopUpButton"}, lambda l: l.strip().lower() == "settings")
                if gear:
                    press(gear[0])
                    time.sleep(1.0)
            pid, window = our_window(bounds)
            return {"menu_closed": not panel_open(window) and not menu_open(window)}
        except SystemExit as exc:
            return {"error": str(exc)[:80]}

    def say_next() -> str:
        nonlocal nexts
        if not a.companion_pid:
            return "no companion pid"
        if nexts >= a.max_next:
            return "not asked: Next limit reached"
        nexts += 1
        return ask_companion(a.companion_pid, "Next")

    done = False
    while not done:
        now = time.time()
        if now - start > a.total_timeout:
            finish_phase("total-timeout", fatal=True)
            break
        if now - last > dt:
            finish_phase("sent" if state["sends"] else "decision-timeout", fatal=True)
            break
        for ev in tail.new_events():
            name = ev.get("event")
            if name == "question":
                phase += 1
                awaiting_q, last = False, time.time()
                if site == "youtube":
                    seen.clear()  # a new YouTube question starts a new walk; Gmail "Next" acknowledgements must not reset it
            elif name == "reader_error":
                emit({"event": "reader_error", "error": str(ev.get("error"))[:200]})
            if name != "decision" or awaiting_q or phase == 0:
                continue
            last = time.time()
            rec = {"event": "decision", "phase": phase, "kind": ev["kind"], "valid": ev.get("valid"),
                   "instruction_en": ev.get("instruction_en", ""), "frame": ev.get("frame"), "source": ev.get("source"),
                   "index": sum(r["event"] == "decision" for r in records)}
            if ev["kind"] == "complete":
                emit({**rec, "action": "none"})
                done = finish_phase("complete")
            elif ev["kind"] == "unsupported":
                emit({**rec, "action": "none"})
                done = finish_phase("unsupported") if a.player_controls else finish_phase("terminal-decision:unsupported", fatal=True)
            elif base.is_scroll_clarify(ev["kind"], rec["instruction_en"]):
                scrolls += 1
                pid, window = our_window(bounds)
                area = web_area_el(window, site)
                result = base.scroll_down(area) if area is not None and scrolls <= a.max_scrolls else "scroll limit reached or no page"
                emit({**rec, "action": result})
                if not result.startswith("scrolled"):
                    done = finish_phase("scroll-failed", fatal=True)
                time.sleep(a.settle)
            elif ev["kind"] != "point":
                emit({**rec, "action": "waiting (clarify): nothing pressed"})
            elif not ev.get("valid") or not ev.get("frame"):
                emit({**rec, "action": "skipped: decision failed validation"})
            else:
                pid, window = our_window(bounds)
                hit = locate(pid, window, site, tuple(ev["frame"]))
                if hit is None:
                    emit({**rec, "action": "no matching control in the dedicated window (nothing pressed)"})
                    done = finish_phase("unmatched-target", fatal=True)
                else:
                    el, role, raw, frame, score = hit
                    label = raw
                    if site == "gmail":
                        label = gmail_name(el, role) or "<other>"
                    url = _get(el, "AXURL") if role == "AXLink" else ""
                    verb, why = decide_action(site, role, label, url, a)
                    key = (role, label)
                    seen[key] = seen.get(key, 0) + 1
                    out = {**rec, "target_role": role, "target_label": label[:100], "times_pointed": seen[key],
                           "iou": round(score, 2), "why": why}
                    if site == "youtube" and role == "AXLink":
                        path = urlparse(str(url or "")).path
                        out["url_watch"], out["url_path"] = path.startswith("/watch"), path[:30]  # public path, no query
                    if verb == "refuse":
                        emit({**out, "action": f"refused: {why}"})
                        done = finish_phase("refused", fatal=True)
                    elif verb == "skip":
                        asked = say_next()
                        emit({**out, "action": f"skipped optional step, said 'Next' in the panel ({asked})"})
                        awaiting_q = asked == "asked"
                        last = time.time()
                    elif verb == "hold":
                        emit({**out, "action": f"held: {why}"})
                        done = finish_phase("reached-target" if site == "youtube" else "send-gated", fatal=site == "gmail")
                    else:
                        if verb.startswith("type:"):
                            what = verb.split(":")[1]
                            quoted = re.search(r"Type ‘([^’]{1,60})’", rec["instruction_en"])
                            song = quoted.group(1) if a.type_from_instruction and quoted else a.song_text
                            text = {"song": song, "to": env_value("QA_GMAIL_TO"), "subject": SUBJECT_TEXT,
                                    "body": BODY_TEXT}[what]
                            result = type_text(el, text)
                        else:
                            speed_before = speed_now(window) if why == "speed stepper (decrease)" else None
                            result = press(el)
                            if why == "speed preset":
                                state["decreases"] = max(state.get("decreases", 0), 0)
                                state["speed_touched"] = True
                            if why == "speed stepper (decrease)":
                                state["speed_touched"] = True
                                a.decreases += 1
                                # A person presses again when nothing happened: if the slider did not move (the panel may still
                                # have been animating), press up to twice more. Recorded, never hidden.
                                tries, before = 1, speed_before
                                while tries < 3 and result.startswith("pressed") and before is not None:
                                    time.sleep(1.2)
                                    win = our_window(bounds)[1]
                                    now = speed_now(win)
                                    if now is not None and now != before:
                                        break
                                    again = find_by_label(win, site, {"AXButton"}, lambda l: l.lower().startswith("decrease playback speed"))
                                    if again is None or press(again[0]) != "pressed":
                                        break
                                    tries += 1
                                    state["decrease_retries"] = state.get("decrease_retries", 0) + 1
                                if tries > 1:
                                    result += f" (slider had not moved: pressed {tries} times)"
                                time.sleep(0.8)
                                state["decreases"] = a.decreases
                                time.sleep(0.8)
                            if site == "youtube" and why == "settings" and seen[key] >= 2 and result == "pressed":
                                # the pack's intentional recovery for a reduced menu: close it, then reopen it
                                time.sleep(1.0)
                                again = find_by_label(window, site, {"AXPopUpButton", "AXButton"},
                                                      lambda l: l.strip().lower() == "settings")
                                result = "pressed (retry: closed" + (
                                    ", reopened)" if again and press(again[0]) == "pressed" else ", reopen failed)")
                            if site == "gmail" and why == "send":
                                a.sends += 1
                                state["sends"] = a.sends
                                time.sleep(3.0)
                                state["sent_seen"] = any_text(window, "Message sent")
                                result = "pressed Send"
                                dt = 15.0  # the pack may not say anything more; do not wait the full timeout
                            if site == "youtube" and why == "search button" and result == "pressed":
                                time.sleep(3.0)
                                url_now = web_area_url(window, site) or ""
                                if "/results" not in url_now:  # typed text may not have reached the page: Return
                                    box = find_by_label(window, site, SEARCH_ROLES, lambda l: l.strip().lower() == "search")
                                    if box and AX.AXUIElementPerformAction(box[0], "AXConfirm") == 0:
                                        state["search_fallback"] = "pressed Return (AXConfirm) after the button did not search"
                                        time.sleep(2.0)
                                        result += "; then Return"
                                    else:
                                        state["search_fallback"] = "search did not run"
                        if verb == "type:to":
                            AX.AXUIElementPerformAction(el, "AXConfirm")  # "then press Enter"
                        if verb.startswith("type:") and SAY_NEXT.search(rec["instruction_en"]) and a.companion_pid:
                            asked = say_next()
                            result += f"; said 'Next' in the panel ({asked})"
                            awaiting_q = asked == "asked"
                        emit({**out, "action": result})
                        if seen[key] >= (a.max_decreases + 1 if why == "speed stepper (decrease)" else a.repeat_limit):
                            done = finish_phase(f"repeat:{label}", fatal=True)
                        time.sleep(a.settle)
            if done:
                break
        time.sleep(a.poll)

    if site == "youtube" and a.decreases > 0 and not a.player_controls:
        try:
            pid, window = our_window(bounds)
            state.update(restore_speed(bounds))
        except SystemExit as exc:
            state["speed_restored"], state["menu_closed"] = False, f"window gone: {exc}"
        emit({"event": "restore", **{k: state[k] for k in ("speed_restored", "menu_closed", "speed_after")}})
    if site == "gmail" and a.sends == 0:
        try:
            pid, window = our_window(bounds)
            state["draft"] = discard_draft(pid, window)
        except SystemExit as exc:
            state["draft"] = f"window gone: {exc}"
    first, second = phase_end.get(1), phase_end.get(2)
    ok = first == "complete" and (not a.then_ask or second in {"reached-target", "complete"})
    if site == "youtube" and a.player_controls:
        state["tidy"] = final_tidy(bounds, bool(state.get("speed_touched")))
        emit({"event": "final-tidy", **state["tidy"]})
        good = {"complete", "reached-target", "unsupported"}
        ok = first == "complete" and len(phase_end) == 1 + len(asks) and all(r in good for r in phase_end.values())
    if site == "gmail":
        ok = list(phase_end.values())[-1:] and list(phase_end.values())[-1] in {"complete", "send-gated", "sent"}
    stop = {"event": "stop", "reason": f"phase1={first}" + (f" phase2={second}" if a.then_ask else "") + (f" last={list(phase_end.values())[-1]}" if len(phase_end) > 2 else "") + (f" last={list(phase_end.values())[-1]}" if site == "gmail" else ""),
            "phases": phase_end, "seconds": round(time.time() - start, 1),
            "decisions": sum(r["event"] == "decision" for r in records), **state}
    emit(stop)
    if a.out:
        a.out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
