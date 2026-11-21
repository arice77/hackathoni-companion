"""Accessibility reader: one fresh snapshot of the target app's front window.

Our own implementation (the H Companion reader was studied, not copied). Privacy rule:
editable inputs report only whether they are filled, never their content. Static text
(screen titles, status lines, file notes) is UI text and is kept as the label.
"""

from __future__ import annotations

import time
import uuid

import ApplicationServices as AX
from AppKit import NSRunningApplication, NSWorkspace

from .contracts import Control, Rect, Snapshot

INPUT_ROLES = {"AXTextField", "AXTextArea", "AXComboBox", "AXPopUpButton", "AXCheckBox", "AXDateField"}
KEEP_ROLES = INPUT_ROLES | {"AXButton", "AXStaticText", "AXLink", "AXRadioButton", "AXMenuButton"}
MAX_ELEMENTS = 400


class ReaderError(RuntimeError):
    pass


def is_trusted() -> bool:
    return bool(AX.AXIsProcessTrusted())


def _attr(el, name):
    err, value = AX.AXUIElementCopyAttributeValue(el, name, None)
    return value if err == 0 else None


def _frame(el) -> Rect | None:
    pos, size = _attr(el, "AXPosition"), _attr(el, "AXSize")
    if pos is None or size is None:
        return None
    ok1, p = AX.AXValueGetValue(pos, AX.kAXValueCGPointType, None)
    ok2, s = AX.AXValueGetValue(size, AX.kAXValueCGSizeType, None)
    if not (ok1 and ok2):
        return None
    return (float(p.x), float(p.y), float(s.width), float(s.height))


def _label(el, role: str) -> str:
    for name in ("AXTitle", "AXDescription", "AXLabel"):
        v = _attr(el, name)
        if isinstance(v, str) and v.strip():
            return v.strip()
    if role == "AXStaticText":
        v = _attr(el, "AXValue")
        if isinstance(v, str):
            return v.strip()
    v = _attr(el, "AXPlaceholderValue")
    return v.strip() if isinstance(v, str) else ""


def is_placeholder_choice(value: str) -> bool:
    """'Select', '---Select My Service---', 'Choose...' and blanks mean nothing is chosen yet."""
    v = value.strip().strip("-").strip(" .…").lower()
    return v == "" or v.startswith("select") or v.startswith("choose")


def _filled(el, role: str) -> bool | None:
    if role not in INPUT_ROLES:
        return None
    v = _attr(el, "AXValue")
    if role == "AXCheckBox":
        return bool(v)
    if role == "AXPopUpButton":
        return isinstance(v, str) and not is_placeholder_choice(v)
    if role == "AXDateField":
        return v is not None
    return isinstance(v, str) and v.strip() != ""


def find_app(bundle_id: str) -> NSRunningApplication | None:
    apps = NSRunningApplication.runningApplicationsWithBundleIdentifier_(bundle_id)
    return apps[0] if apps else None


def frontmost_bundle_id() -> str | None:
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    return app.bundleIdentifier() if app else None


def snapshot(bundle_id: str) -> Snapshot:
    if not is_trusted():
        raise ReaderError("This process is not allowed to read other apps (Accessibility permission missing).")
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

    controls: list[Control] = []
    stack, seen = [window], 0
    while stack and seen < MAX_ELEMENTS:
        el = stack.pop(0)
        seen += 1
        role = _attr(el, "AXRole") or ""
        if role in KEEP_ROLES:
            frame = _frame(el)
            if frame and frame[2] > 0 and frame[3] > 0:
                ident = _attr(el, "AXIdentifier")
                controls.append(Control(
                    id=f"c{len(controls):02d}",
                    role=role,
                    label=_label(el, role),
                    frame=frame,
                    enabled=bool(_attr(el, "AXEnabled") if _attr(el, "AXEnabled") is not None else True),
                    identifier=ident if isinstance(ident, str) and ident else None,
                    filled=_filled(el, role),
                ))
        if role not in INPUT_ROLES:  # don't descend into popups/fields
            stack.extend(_attr(el, "AXChildren") or [])

    return Snapshot(
        snapshot_id=uuid.uuid4().hex[:12],
        taken_at=time.time(),
        app_bundle_id=bundle_id,
        app_pid=int(app.processIdentifier()),
        window_title=str(_attr(window, "AXTitle") or ""),
        window_frame=_frame(window) or (0.0, 0.0, 0.0, 0.0),
        controls=tuple(controls),
    )


if __name__ == "__main__":
    import json
    import sys

    t0 = time.perf_counter()
    snap = snapshot(sys.argv[1] if len(sys.argv) > 1 else "in.hackathoni.crop-loss-training")
    ms = (time.perf_counter() - t0) * 1000
    print(json.dumps({"snapshot_id": snap.snapshot_id, "window": snap.window_title, "ms": round(ms, 1),
                      "controls": [c.__dict__ for c in snap.controls]}, indent=1, default=list))
