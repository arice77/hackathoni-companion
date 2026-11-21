"""Opt-in read-only GasUndo walk in one dedicated Safari window."""

import json
import os
import subprocess
import time
from urllib.parse import urlsplit

from _common import PY, ROOT, result, wait_for
import _follow
import _site

FEATURE = "web-support"
HOST = "gasundo.live"
URL = "https://gasundo.live/"
QUESTION = "ബെക്താഷ് കാക്കനാട് തുറന്നിട്ടുണ്ടോ എന്ന് അറിയണം / Is Bektash Kakkanad open?"


class WalkStopped(RuntimeError):
    pass


def _front_host(window):
    p = _site._osa(f'''tell application id "{_site.SAFARI}"
        if (id of front window) is {window} and (count of tabs of front window) is 1 then
            return URL of current tab of front window
        end if
    end tell''', timeout=5)
    return urlsplit(p.stdout.strip()).hostname if p.returncode == 0 else None


def _sample(window):
    from companion import reader
    from companion.sites.gasundo import HOSTS

    host = _front_host(window)
    if host not in HOSTS:
        return None
    started = time.perf_counter()
    try:
        snap = reader.snapshot(reader.SAFARI, page_url_prefix=f"https://{host}")
    except reader.ReaderError:
        return None
    if snap.window_title not in HOSTS:
        return None
    return snap, round(1000 * (time.perf_counter() - started), 1)


def _events(log):
    rows = []
    for line in log.read_text().splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # writer may still be appending the last line
    return rows


def _point(window, log, matches):
    def ready():
        row = next((r for r in reversed(_events(log)) if r["event"] == "decision"), None)
        if not row or row.get("kind") != "point" or row.get("valid") is not True:
            return None
        sample = _sample(window)
        if sample:
            snap, elapsed = sample
            controls = [c for c in snap.controls if matches(c) and c.enabled
                        and c.identifier == row.get("target") and list(c.frame) == row.get("frame")]
            if len(controls) == 1:
                return snap, elapsed, controls[0]
        return None

    return wait_for(ready, seconds=14, every=.25)


def _click(window, snap, control):
    import Quartz
    from companion import reader
    from companion.sites.gasundo import HOSTS

    if reader.frontmost_bundle_id() != reader.SAFARI or _front_host(window) not in HOSTS:
        raise WalkStopped("Safari’s dedicated GasUndo tab is no longer active.")
    x, y, width, height = control.frame
    point = x + width / 2, y + height / 2
    root = reader.AX.AXUIElementCreateApplication(snap.app_pid)
    status, element = reader.AX.AXUIElementCopyElementAtPosition(root, *point, None)
    if status != 0:
        raise WalkStopped("The pointer is no longer over an accessible Safari control.")
    for _ in range(4):
        role = reader._attr(element, "AXRole")
        if role == "AXButton" and reader._label(element, role).casefold().startswith("bektash kakkanad"):
            break
        element = reader._attr(element, "AXParent")
        if element is None:
            raise WalkStopped("The pointer is no longer over the expected restaurant suggestion.")
    else:
        raise WalkStopped("The pointer is no longer over the expected restaurant suggestion.")
    # GasUndo selects suggestions on mousedown. Click only a validated, re-read pointer.
    for event_type in (Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp):
        event = Quartz.CGEventCreateMouseEvent(None, event_type, point, Quartz.kCGMouseButtonLeft)
        Quartz.CGEventSetIntegerValueField(event, Quartz.kCGMouseEventClickState, 1)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)


def _type_bektash(window, snap, target):
    import Quartz
    from companion import reader
    from companion.sites.gasundo import HOSTS, SEARCH_IDS

    if reader.frontmost_bundle_id() != reader.SAFARI or _front_host(window) not in HOSTS:
        raise WalkStopped("The dedicated window lost focus before typing.")
    root = reader.AX.AXUIElementCreateApplication(snap.app_pid)
    page, _, _, _ = reader._selected_web_page(root, reader._attr)
    nodes = [element for element, role, _ in reader._walk(page, reader._attr, 700, reader.WEB_LEAVES)
             if role == target.role and reader._identifier(element) == target.identifier
             and target.identifier in SEARCH_IDS]
    if len(nodes) != 1:
        raise WalkStopped("Could not isolate the pointed restaurant search input.")
    field = nodes[0]
    reader.AX.AXUIElementSetAttributeValue(field, "AXFocused", True)
    if not wait_for(lambda: reader._attr(root, "AXFocusedUIElement") == field, seconds=2):
        raise WalkStopped("Could not focus the restaurant search input.")
    if reader._attr(field, "AXValue") not in ("", None):
        raise WalkStopped("The restaurant search stopped because the input was already filled.")
    for down in (True, False):
        event = Quartz.CGEventCreateKeyboardEvent(None, 0, down)
        Quartz.CGEventKeyboardSetUnicodeString(event, len("Bektash"), "Bektash")
        Quartz.CGEventPostToPid(snap.app_pid, event)
    if not wait_for(lambda: reader._attr(field, "AXValue") == "Bektash", seconds=2):
        reader.AX.AXUIElementSetAttributeValue(field, "AXValue", "Bektash")
    if not wait_for(lambda: reader._attr(field, "AXValue") == "Bektash", seconds=2):
        raise WalkStopped("Search input did not receive the expected test word.")


def run():
    from companion import reader
    from companion.sites.gasundo import PACK, SEARCH, STATUS_NOTES, SUGGESTION_PREFIX, REPORT_AGE

    name = "GasUndo Malayalam follow-the-pointer walkthrough"
    if os.environ.get("QA_LIVE_SARVAM") != "1":
        return [result(FEATURE, name, "blocked", "blocked", "Set QA_LIVE_SARVAM=1 for the Safari and spoken check.")]
    prerequisites = _site.pack_landed("GasUndo", "gasundo")
    if prerequisites or not reader.is_trusted() or not _follow.key_available():
        return [result(FEATURE, name, "blocked", "blocked",
                       prerequisites or "This check requires Accessibility trust and a Sarvam key for speech.")]
    window, _bounds, error = _site.open_own_window(URL, HOST)
    if error:
        return [result(FEATURE, name, "blocked", "live-machine", error)]
    app = None
    try:
        sample = wait_for(lambda: _sample(window), seconds=12)
        if not sample or not any(c.label == "Select district: Ernakulam" for c in sample[0].controls):
            raise WalkStopped("The reader did not expose Ernakulam as the selected district.")
        existing = set((ROOT / "runs").glob("session-*.jsonl"))
        app = subprocess.Popen([PY, "-m", "companion.app", "--task", "web_site", "--lang", "ml",
                                "--planner", "sarvam", "--question", QUESTION], cwd=ROOT, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL)
        log = wait_for(lambda: next(iter(set((ROOT / "runs").glob("session-*.jsonl")) - existing), None), seconds=8)
        if not log:
            raise WalkStopped("The companion did not start.")
        _site._osa(f'tell application id "{_site.SAFARI}" to activate', timeout=5)
        point = _point(window, log, SEARCH.matches)
        if not point:
            raise WalkStopped(f"Missing validated Search restaurants pointer. Session: {log.name}")
        snap, search_ms, target = point
        _type_bektash(window, snap, target)
        point = _point(window, log, lambda c: c.role == "AXButton"
                       and (c.label.casefold() + " ").startswith("bektash kakkanad ")
                       and (c.identifier or "").startswith(SUGGESTION_PREFIX))
        if not point:
            sample = _sample(window)
            if sample:
                print("[gasundo] visible suggestion labels:", [
                    c.label for c in sample[0].controls if (c.identifier or "").startswith(SUGGESTION_PREFIX)
                ], flush=True)
            raise WalkStopped(f"Missing validated Bektash Kakkanad suggestion pointer. Session: {log.name}")
        snap, suggestion_ms, target = point
        _click(window, snap, target)

        final = wait_for(lambda: next((r for r in _events(log) if r["event"] == "decision"
                                       and r.get("kind") == "complete" and r.get("valid")), None), seconds=14)
        if not final:
            raise WalkStopped(f"No validated report after selecting Bektash. Session: {log.name}")
        sample = wait_for(lambda: _sample(window), seconds=5)
        if not sample:
            raise WalkStopped(f"Could not reread the selected card. Session: {log.name}")
        snap, detail_ms = sample
        report = PACK.start_guidance(QUESTION).decide(snap)
        if report.kind != "complete" or report.instruction_en != final["instruction_en"]:
            raise WalkStopped(f"Completion did not match the visible card. Session: {log.name}")
        spoken = wait_for(lambda: any(r["event"] == "spoke" and r.get("lang") == "ml-IN"
                                     and r["t"] > final["t"] and r.get("chars") == len(report.instruction)
                                     for r in _events(log)), seconds=27)
        if not spoken:
            raise WalkStopped(f"Missing Malayalam playback of the completed report. Session: {log.name}")
        notes = [c.label for c in snap.controls if c.role == "AXStaticText"
                 and (c.label in STATUS_NOTES or REPORT_AGE.fullmatch(c.label))]
        return [result(FEATURE, name, "pass", "live-machine",
                       f"Search, suggestion and detail reads {search_ms}/{suggestion_ms}/{detail_ms} ms. "
                       f"Ernakulam verified. AX details: {notes}. {final['instruction_en']} "
                       f"Malayalam playback logged. Session: {log.name}"),
                result(FEATURE, "person follows the pointer and understands the wording", "skip", "needs-human")]
    except WalkStopped as exc:
        return [result(FEATURE, name, "fail", "live-machine", str(exc))]
    finally:
        if app is not None:
            app.terminate()
            try:
                app.wait(timeout=3)
            except subprocess.TimeoutExpired:
                app.kill()
                app.wait()
        print(f"[gasundo] dedicated window: {_site.close_own_window(window, HOST)}", flush=True)
