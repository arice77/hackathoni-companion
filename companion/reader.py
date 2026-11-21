"""Accessibility reader: one fresh native-window or selected-browser-page snapshot.

Our own implementation (the H Companion reader was studied, not copied). Privacy rule:
editable inputs report only whether they are filled, never their content. Browser
snapshots omit password fields, page prose, and URL paths and queries.
"""

from __future__ import annotations

import os
import re
import subprocess
import time
import uuid
from collections import deque
from pathlib import Path
from urllib.parse import urlsplit

import ApplicationServices as AX
from AppKit import NSRunningApplication, NSWorkspace

from .contracts import Control, Rect, Snapshot

INPUT_ROLES = {"AXTextField", "AXTextArea", "AXComboBox", "AXPopUpButton", "AXCheckBox", "AXDateField"}
KEEP_ROLES = INPUT_ROLES | {"AXButton", "AXStaticText", "AXLink", "AXRadioButton", "AXMenuButton"}
MAX_ELEMENTS = 400
MAX_WEB_ELEMENTS = 1200
MAX_WEB_CONTROLS = 96
MAX_WEB_HEADINGS = 12
MAX_WEB_LABEL_LENGTH = 160
WEB_READ_BUDGET_S = 0.300
WEB_AX_TIMEOUT_S = 0.040
REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_BUNDLE_PREFIX = "in.hackathoni."
TRAINING_BUNDLE = f"{FIXTURE_BUNDLE_PREFIX}crop-loss-training"
PRACTICE_TITLE = "HackaThoni · Business Form Practice"
SAFARI = "com.apple.Safari"
BRAVE = "com.brave.Browser"
PRACTICE_TITLES = {SAFARI: PRACTICE_TITLE, BRAVE: f"{PRACTICE_TITLE} - Brave"}
UNSUPPORTED_BROWSERS = {"com.apple.SafariTechnologyPreview", "com.google.Chrome", "com.google.Chrome.canary",
                        "org.chromium.Chromium", "com.microsoft.edgemac", "org.mozilla.firefox"}
WEB_TEXT_NOTES = {"status", "document-note"}
WEB_VALUE_ROLES = INPUT_ROLES | {"AXSearchField", "AXTimeField", "AXRadioButton"}
WEB_INPUT_ROLES = WEB_VALUE_ROLES | {"AXDateTimeArea"}
SECURE_ROLE = "AXSecureTextField"
WEB_LEAVES = WEB_INPUT_ROLES | {SECURE_ROLE, "AXWebArea"}
HTTP_URL = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


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


def _label(el, role: str, get=_attr, exclude="") -> str:
    for name in ("AXTitle", "AXDescription", "AXLabel"):
        v = get(el, name)
        if isinstance(v, str) and v.strip() and v.strip() != exclude:
            return v.strip()
    if role == "AXStaticText":
        v = get(el, "AXValue")
        if isinstance(v, str):
            return v.strip()
    v = get(el, "AXPlaceholderValue")
    return v.strip() if isinstance(v, str) and v.strip() != exclude else ""


def is_placeholder_choice(value: str) -> bool:
    """'Select', '---Select My Service---', 'Choose...' and blanks mean nothing is chosen yet."""
    v = value.strip().strip("-").strip(" .…").lower()
    return v == "" or v.startswith("select") or v.startswith("choose")


def _filled(value, role: str) -> bool:
    if role in {"AXCheckBox", "AXRadioButton"}:
        return bool(value)
    if role == "AXPopUpButton":
        return isinstance(value, str) and not is_placeholder_choice(value)
    if role == "AXDateField":
        return value is not None
    return isinstance(value, str) and value.strip() != ""


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
            raise ReaderError("Browser Accessibility read exceeded its time budget.")
        AX.AXUIElementSetMessagingTimeout(el, WEB_AX_TIMEOUT_S)
        err, value = AX.AXUIElementCopyAttributeValue(el, name, None)
        if err == AX.kAXErrorCannotComplete:
            raise ReaderError("Browser Accessibility did not respond in time. Try again once the page is ready.")
        return value if err == 0 else None
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
        raise ReaderError("Brave requires --pid for the isolated browser instance; see docs/web-support.md.")
    if pid is not None:
        raise ReaderError("Explicit pid is only supported for the isolated Brave instance.")
    app = find_app(bundle_id)
    if app is None:
        raise ReaderError(f"{bundle_id} is not running.")
    return int(app.processIdentifier())


def _host(url: str) -> str:
    try:
        return urlsplit(url).hostname or ""
    except ValueError:
        return ""


def _url_matches(url: str, prefix: str) -> bool:
    try:
        actual, expected = urlsplit(url), urlsplit(prefix)
        return bool(expected.hostname and actual.netloc == expected.netloc and url.startswith(prefix))
    except ValueError:
        return False


def _selected_web_page(root, get, page_title=None, page_url_prefix=None):
    window = get(root, "AXFocusedWindow") or get(root, "AXMainWindow")
    if window is None or get(window, "AXMinimized"):
        raise ReaderError("The browser has no readable front window.")
    if page_title is not None and get(window, "AXTitle") != page_title:
        raise ReaderError("The front browser window doesn't match this task. Open the task page in the front window.")
    window_frame = _frame(window, get)
    for el, role in _walk(window, get, MAX_WEB_ELEMENTS, WEB_LEAVES | {"AXToolbar"}):
        if role != "AXWebArea":
            continue
        frame = _frame(el, get)
        viewport = _intersection(window_frame, frame) if window_frame and frame else None
        parent = get(el, "AXParent")
        if viewport and parent is not None and get(parent, "AXRole") == "AXScrollArea":
            scroll_frame = _frame(parent, get)
            if scroll_frame:
                viewport = _intersection(viewport, scroll_frame)
        if viewport:
            url = str(get(el, "AXURL") or "")
            if page_url_prefix is not None and not _url_matches(url, page_url_prefix):
                raise ReaderError("The selected page doesn't match this task. Select the task page in the front window.")
            return el, window_frame, viewport, url
    raise ReaderError("No visible page in the front browser window. Wait for the selected tab to load.")


def _web_note(el, get) -> str:
    children = get(el, "AXChildren") or []
    if len(children) == 1 and get(children[0], "AXRole") == "AXStaticText":
        return _label(children[0], "AXStaticText", get)
    return ""


def _web_label(el, role, get, value) -> str:
    exclude = value.strip() if isinstance(value, str) else ""
    label = _label(el, role, get, exclude=exclude)
    if not label and role in WEB_INPUT_ROLES:
        relation = get(el, "AXTitleUIElement")
        if relation is not None and get(relation, "AXRole") == "AXStaticText":
            label = _label(relation, "AXStaticText", get)
            if label == exclude:
                return ""
    return label


def _safe_web_text(text: str) -> str:
    return HTTP_URL.sub(lambda match: _host(match.group()) or "[link]", text)[:MAX_WEB_LABEL_LENGTH]


def _collect(start, get, limit, viewport=None, *, practice=False) -> tuple[Control, ...]:
    controls = []
    web = viewport is not None
    roles = (KEEP_ROLES | WEB_INPUT_ROLES | {"AXHeading", "AXGroup"}) - {"AXStaticText"} if web else KEEP_ROLES
    if web and practice:
        roles |= {"AXStaticText"}
    leaves = WEB_LEAVES | {"AXScrollArea"} if web else INPUT_ROLES | {SECURE_ROLE}
    value_roles = WEB_VALUE_ROLES if web else INPUT_ROLES
    headings = 0
    for el, role in _walk(start, get, limit, leaves):
        if role not in roles:
            continue
        fieldset = role == "AXGroup" and not practice and get(el, "AXSubrole") == "AXFieldset"
        context = role == "AXHeading" or fieldset
        if (context and headings >= MAX_WEB_HEADINGS) or (role == "AXGroup" and not (practice or fieldset)):
            continue
        if role in {"AXTextField", "AXTextArea", "AXSearchField"} and get(el, "AXSubrole") == SECURE_ROLE:
            continue
        frame = _frame(el, get)
        if viewport and frame:
            frame = _intersection(frame, viewport)
        if not frame or frame[2] <= 0 or frame[3] <= 0:
            continue
        ident = _identifier(el, get)
        value = get(el, "AXValue") if role in value_roles else None
        if role == "AXGroup" and practice:
            if ident not in WEB_TEXT_NOTES:
                continue
            label = _web_note(el, get)
            if not label:
                continue
            role = "AXStaticText"
        else:
            label = _web_label(el, role, get, value) if web else _label(el, role, get)
        if fieldset and not label:
            continue
        if web:
            label = _safe_web_text(label)
            if ident and (len(ident) > MAX_WEB_LABEL_LENGTH or HTTP_URL.search(ident)):
                ident = None
        enabled = get(el, "AXEnabled")
        filled = _filled(value, role) if role in value_roles else None
        controls.append(Control(
            id=f"c{len(controls):02d}", role=role, label=label, frame=frame,
            enabled=not fieldset and (enabled is None or bool(enabled)), identifier=ident, filled=filled,
        ))
        headings += context
        if web and len(controls) >= MAX_WEB_CONTROLS:
            break
    return tuple(controls)


def find_app(bundle_id: str) -> NSRunningApplication | None:
    """Prefer this worktree's app; never fall back to a sibling HackaThoni fixture."""
    apps = NSRunningApplication.runningApplicationsWithBundleIdentifier_(bundle_id)
    for app in apps:
        url = app.bundleURL()
        path = url.path() if url is not None else None
        if path and Path(path).resolve().is_relative_to(REPO_ROOT):
            return app
    return apps[0] if apps and not bundle_id.startswith(FIXTURE_BUNDLE_PREFIX) else None


def frontmost_bundle_id() -> str | None:
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    return app.bundleIdentifier() if app else None


def snapshot(bundle_id: str, *, pid: int | None = None, page_title: str | None = None,
             page_url_prefix: str | None = None) -> Snapshot:
    started = time.monotonic()
    if not is_trusted():
        raise ReaderError("This process is not allowed to read other apps (Accessibility permission missing).")
    if bundle_id in PRACTICE_TITLES:
        browser_pid = _browser_pid(bundle_id, pid)
        get = _web_getter(started)
        root = AX.AXUIElementCreateApplication(browser_pid)
        page, window_frame, viewport, url = _selected_web_page(root, get, page_title, page_url_prefix)
        practice = url == _practice_url()
        controls = _collect(page, get, MAX_WEB_ELEMENTS, viewport, practice=practice)
        if str(get(page, "AXURL") or "") != url:
            raise ReaderError("The selected page changed while it was being read. Try again.")
        title = PRACTICE_TITLES[bundle_id] if practice else _host(url) or "Browser page"
        return Snapshot(uuid.uuid4().hex[:12], time.time(), bundle_id, browser_pid, title, window_frame, controls, viewport)
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
    parser.add_argument("bundle_id", nargs="?")
    parser.add_argument("--pid", type=int, help="PID of the isolated Brave instance")
    parser.add_argument("--page-title", help="require the exact title of the front browser window")
    parser.add_argument("--page-url-prefix", help="require the selected page to match this URL prefix")
    args = parser.parse_args()
    t0 = time.perf_counter()
    try:
        snap = snapshot(args.bundle_id or TRAINING_BUNDLE, pid=args.pid,
                        page_title=args.page_title, page_url_prefix=args.page_url_prefix)
    except ReaderError as exc:
        parser.exit(1, f"{exc}\n")
    ms = (time.perf_counter() - t0) * 1000
    print(json.dumps({"snapshot_id": snap.snapshot_id, "window": snap.window_title, "viewport": snap.viewport, "ms": round(ms, 1),
                      "controls": [c.__dict__ for c in snap.controls]}, indent=1, default=list))
