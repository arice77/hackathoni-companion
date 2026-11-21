"""Local checks a decision must pass before anything is drawn on screen."""

from __future__ import annotations

import time

from .contracts import Decision, Snapshot

MAX_SNAPSHOT_AGE_S = 2.0


def validate(decision: Decision, snap: Snapshot, now: float | None = None) -> tuple[bool, str]:
    now = time.time() if now is None else now
    if decision.snapshot_id != snap.snapshot_id:
        return False, "decision refers to a different snapshot"
    if now - snap.taken_at > MAX_SNAPSHOT_AGE_S:
        return False, "snapshot is stale"
    if decision.kind != "point":
        return (decision.control_id is None, "ok" if decision.control_id is None else "non-point decision has a control")
    if not decision.control_id:
        return False, "point decision without a control id"
    control = snap.control(decision.control_id)
    if control is None:
        return False, f"unknown control id {decision.control_id}"
    group_outline = control.role in {"AXGroup", "AXRadioGroup"} and bool(control.label) and any(
        option.group == control.label and option.role in {"AXRadioButton", "AXCheckBox"} and option.enabled
        for option in snap.controls
    )
    if not control.enabled and not group_outline:
        return False, "target control is disabled"
    x, y, w, h = control.frame
    wx, wy, ww, wh = snap.viewport if snap.viewport is not None else snap.window_frame
    if w <= 0 or h <= 0:
        return False, "target has no visible size"
    cx, cy = x + w / 2, y + h / 2
    if not (wx <= cx <= wx + ww and wy <= cy <= wy + wh):
        return False, "target centre is outside the page viewport" if snap.viewport is not None else "target centre is outside the app window"
    return True, "ok"
