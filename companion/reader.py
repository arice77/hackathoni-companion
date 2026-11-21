"""Accessibility reader: one fresh native-window or practice-page snapshot.

Our own implementation (the H Companion reader was studied, not copied). Privacy rule:
editable inputs report only whether they are filled, never their content. Static text
(screen titles, status lines, file notes) is UI text and is kept as the label.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
import uuid
from collections import deque

import ApplicationServices as AX
from AppKit import NSRunningApplication, NSWorkspace

from .contracts import Control, Rect, Snapshot

INPUT_ROLES = {"AXTextField", "AXTextArea", "AXComboBox", "AXPopUpButton", "AXCheckBox", "AXDateField"}
KEEP_ROLES = INPUT_ROLES | {"AXButton", "AXStaticText", "AXLink", "AXRadioButton", "AXMenuButton"}
MAX_ELEMENTS = 400
MAX_WEB_ELEMENTS = 1200
WEB_READ_BUDGET_S = 0.200
WEB_AX_TIMEOUT_S = 0.040
PRACTICE_TITLE = "HackaThoni · Business Form Practice"
SAFARI = "com.apple.Safari"
BRAVE = "com.brave.Browser"
PRACTICE_TITLES = {SAFARI: PRACTICE_TITLE, BRAVE: f"{PRACTICE_TITLE} - Brave"}
UNSUPPORTED_BROWSERS = {"com.apple.SafariTechnologyPreview", "com.google.Chrome", "com.google.Chrome.canary",
                        "org.chromium.Chromium", "com.microsoft.edgemac", "org.mozilla.firefox"}
WEB_TEXT_NOTES = {"status", "document-note"}


class ReaderError(RuntimeError):
    pass


def is_trusted() -> bool:
    return bool(AX.AXIsProcessTrusted())


def _attr(el, name):
    err, value = AX.AXUIElementCopyAttributeValue(el, name, None)
    return value if err == 0 else None


def _frame(el, get=_attr) -> Rect | None:
    pos, size = get(el, "AXPosition"), get(el, "AXSize")
    if pos is None or size is None:
        return None
    ok1, p = AX.AXValueGetValue(pos, AX.kAXValueCGPointType, None)
    ok2, s = AX.AXValueGetValue(size, AX.kAXValueCGSizeType, None)
    if not (ok1 and ok2):
        return None
    return (float(p.x), float(p.y), float(s.width), float(s.height))


def _label(el, role: str, get=_attr) -> str:
    for name in ("AXTitle", "AXDescription", "AXLabel"):
        v = get(el, name)
        if isinstance(v, str) and v.strip():
            return v.strip()
    if role == "AXStaticText":
        v = get(el, "AXValue")
        if isinstance(v, str):
            return v.strip()
    v = get(el, "AXPlaceholderValue")
    return v.strip() if isinstance(v, str) else ""


def is_placeholder_choice(value: str) -> bool:
    """'Select', '---Select My Service---', 'Choose...' and blanks mean nothing is chosen yet."""
    v = value.strip().strip("-").strip(" .…").lower()
    return v == "" or v.startswith("select") or v.startswith("choose")


def _filled(el, role: str, get=_attr) -> bool | None:
    if role not in INPUT_ROLES:
        return None
    v = get(el, "AXValue")
    if role == "AXCheckBox":
        return bool(v)
    if role == "AXPopUpButton":
        return isinstance(v, str) and not is_placeholder_choice(v)
    if role == "AXDateField":
        return v is not None
    return isinstance(v, str) and v.strip() != ""


def _identifier(el, get=_attr) -> str | None:
    for name in ("AXIdentifier", "AXDOMIdentifier"):
        value = get(el, name)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _intersection(first: Rect, second: Rect) -> Rect | None:
    left, top = max(first[0], second[0]), max(first[1], second[1])
    right = min(first[0] + first[2], second[0] + second[2])
    bottom = min(first[1] + first[3], second[1] + second[3])
    return (left, top, right - left, bottom - top) if left < right and top < bottom else None


def _walk(start, get, limit, leaf_roles):
    queue = deque([start])
    for seen in range(limit):
        if not queue:
            return
        el = queue.popleft()
        role = get(el, "AXRole") or ""
        yield el, role
        remaining = limit - seen - len(queue) - 1
        if remaining > 0 and (seen == 0 or role not in leaf_roles):
            children = get(el, "AXChildren") or []
            queue.extend(children[:remaining])


def _web_getter(started):
    def get(el, name):
        if time.monotonic() - started >= WEB_READ_BUDGET_S:
            raise ReaderError("Practice page Accessibility read exceeded its time budget.")
        AX.AXUIElementSetMessagingTimeout(el, WEB_AX_TIMEOUT_S)
        return _attr(el, name)
    return get


def _practice_url() -> str:
    return f"http://127.0.0.1:{os.environ.get('CONDUCTOR_PORT') or '8765'}/"


def _launch_isolated_brave(command: str) -> bool:
    return (not re.search(r"(?:^| )--type=", command)
            and len(re.findall(r"(?:^| )--user-data-dir(?:[= ]|$)", command)) == 1
            and bool(re.search(r"(?:^| )--user-data-dir=/tmp/hackathoni-brave\.[A-Za-z0-9_-]{6,12}(?: |$)", command))
            and "--force-renderer-accessibility=complete" in command.split())


def _browser_pid(bundle_id: str, pid: int | None) -> int:
    if bundle_id == BRAVE:
        app = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid) if pid and pid > 0 else None
        if app and app.bundleIdentifier() == bundle_id:
            try:
                command = subprocess.check_output(["/bin/ps", "-ww", "-p", str(pid), "-o", "command="],
                                                  text=True, stderr=subprocess.DEVNULL, timeout=0.05)
                if _launch_isolated_brave(command):
                    return pid
            except subprocess.SubprocessError:
                pass
        raise ReaderError("Brave requires --pid for the isolated practice instance; see docs/web-support.md.")
    if pid is not None:
        raise ReaderError("Explicit pid is only supported for the isolated Brave instance.")
    app = find_app(bundle_id)
    if app is None:
        raise ReaderError(f"{bundle_id} is not running.")
    return int(app.processIdentifier())


def _practice_page(root, title: str, url: str, get):
    for window in get(root, "AXWindows") or []:
        if get(window, "AXTitle") != title or get(window, "AXMinimized"):
            continue
        for el, role in _walk(window, get, MAX_WEB_ELEMENTS, INPUT_ROLES | {"AXToolbar", "AXWebArea"}):
            if role != "AXWebArea" or str(get(el, "AXURL")) != url:
                continue
            window_frame, frame = _frame(window, get), _frame(el, get)
            viewport = _intersection(window_frame, frame) if window_frame and frame else None
            parent = get(el, "AXParent")
            if viewport and parent is not None and get(parent, "AXRole") == "AXScrollArea":
                scroll_frame = _frame(parent, get)
                if scroll_frame:
                    viewport = _intersection(viewport, scroll_frame)
            if viewport:
                return el, window_frame, viewport
    raise ReaderError("No visible practice page found. Open it with scripts/open_web_practice.sh.")


def _web_note(el, get) -> str:
    children = get(el, "AXChildren") or []
    if len(children) == 1 and get(children[0], "AXRole") == "AXStaticText":
        return _label(children[0], "AXStaticText", get)
    return ""


def _collect(start, get, limit, viewport=None) -> tuple[Control, ...]:
    controls = []
    roles = KEEP_ROLES | {"AXHeading", "AXGroup"} if viewport else KEEP_ROLES
    leaves = INPUT_ROLES | ({"AXWebArea", "AXScrollArea"} if viewport else set())
    for el, role in _walk(start, get, limit, leaves):
        if role not in roles:
            continue
        if role == "AXGroup":
            ident = _identifier(el, get)
            if ident not in WEB_TEXT_NOTES:
                continue
            label = _web_note(el, get)
            if not label:
                continue
            role = "AXStaticText"
        else:
            ident, label = _identifier(el, get), None
        frame = _frame(el, get)
        if viewport and frame:
            frame = _intersection(frame, viewport)
        if not frame or frame[2] <= 0 or frame[3] <= 0:
            continue
        enabled = get(el, "AXEnabled")
        controls.append(Control(
            id=f"c{len(controls):02d}", role=role,
            label=_label(el, role, get) if label is None else label,
            frame=frame, enabled=enabled is None or bool(enabled),
            identifier=ident, filled=_filled(el, role, get),
        ))
    return tuple(controls)


def find_app(bundle_id: str) -> NSRunningApplication | None:
    apps = NSRunningApplication.runningApplicationsWithBundleIdentifier_(bundle_id)
    return apps[0] if apps else None


def frontmost_bundle_id() -> str | None:
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    return app.bundleIdentifier() if app else None


def snapshot(bundle_id: str, *, pid: int | None = None) -> Snapshot:
    started = time.monotonic()
    if not is_trusted():
        raise ReaderError("This process is not allowed to read other apps (Accessibility permission missing).")
    if bundle_id in PRACTICE_TITLES:
        browser_pid = _browser_pid(bundle_id, pid)
        get = _web_getter(started)
        root = AX.AXUIElementCreateApplication(browser_pid)
        title = PRACTICE_TITLES[bundle_id]
        page, window_frame, viewport = _practice_page(root, title, _practice_url(), get)
        controls = _collect(page, get, MAX_WEB_ELEMENTS, viewport)
        return Snapshot(uuid.uuid4().hex[:12], time.time(), bundle_id, browser_pid, title, window_frame, controls)
    if bundle_id in UNSUPPORTED_BROWSERS or pid is not None:
        raise ReaderError("This browser or pid is not a supported practice target.")
    app = find_app(bundle_id)
    if app is None:
        raise ReaderError(f"{bundle_id} is not running.")
    root = AX.AXUIElementCreateApplication(app.processIdentifier())
    window = _attr(root, "AXFocusedWindow") or _attr(root, "AXMainWindow")
    if window is None:
        windows = _attr(root, "AXWindows") or []
        window = windows[0] if windows else None
    if window is None:
        raise ReaderError("The target app has no readable window.")

    controls = _collect(window, _attr, MAX_ELEMENTS)
    return Snapshot(
        snapshot_id=uuid.uuid4().hex[:12],
        taken_at=time.time(),
        app_bundle_id=bundle_id,
        app_pid=int(app.processIdentifier()),
        window_title=str(_attr(window, "AXTitle") or ""),
        window_frame=_frame(window) or (0.0, 0.0, 0.0, 0.0),
        controls=controls,
    )


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle_id", nargs="?", default="in.hackathoni.crop-loss-training")
    parser.add_argument("--pid", type=int, help="PID of the isolated Brave practice instance")
    args = parser.parse_args()
    t0 = time.perf_counter()
    try:
        snap = snapshot(args.bundle_id, pid=args.pid)
    except ReaderError as exc:
        parser.exit(1, f"{exc}\n")
    ms = (time.perf_counter() - t0) * 1000
    print(json.dumps({"snapshot_id": snap.snapshot_id, "window": snap.window_title, "ms": round(ms, 1),
                      "controls": [c.__dict__ for c in snap.controls]}, indent=1, default=list))
