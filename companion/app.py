"""HackaThoni Companion: question -> live snapshot -> next step -> validated pointer -> human click -> re-check.

Run from a process that has Accessibility permission (on the build Mac, a Conductor terminal):

    .venv/bin/python -m companion.app [--planner scripted|sarvam]

The person always clicks themselves. The companion never sends clicks or keystrokes.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import uuid
from pathlib import Path

import objc
from AppKit import (
    NSApp, NSApplication, NSApplicationActivationPolicyRegular, NSBackingStoreBuffered, NSButton, NSColor,
    NSFloatingWindowLevel, NSFont, NSLineBreakByWordWrapping, NSScreen, NSStackView, NSTextField, NSWindow,
    NSWindowStyleMaskClosable, NSWindowStyleMaskTitled, NSUserInterfaceLayoutOrientationVertical,
)
from Foundation import NSMakeRect, NSObject, NSTimer

from . import reader
from .contracts import Decision
from .planner import ScriptedPlanner
from .validator import validate

TARGET_BUNDLE = "in.hackathoni.crop-loss-training"
ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
TICK_S = 0.5


def make_overlay():
    try:
        from .overlay import SketchOverlay  # delivered by the overlay agent
        return SketchOverlay(), "sketch"
    except Exception:  # noqa: BLE001 - any import/setup failure falls back to the plain pointer
        from .overlay_basic import BasicOverlay
        return BasicOverlay(), "basic"


def make_planner(name: str):
    if name == "sarvam":
        from .planner_sarvam import SarvamPlanner  # requires SARVAM_API_KEY
        return SarvamPlanner()
    return ScriptedPlanner()


def label(text: str, size: float, bold: bool = False, wrap: bool = False) -> NSTextField:
    f = NSTextField.wrappingLabelWithString_(text) if wrap else NSTextField.labelWithString_(text)
    f.setFont_(NSFont.boldSystemFontOfSize_(size) if bold else NSFont.systemFontOfSize_(size))
    if wrap:
        f.setPreferredMaxLayoutWidth_(360)
        f.cell().setLineBreakMode_(NSLineBreakByWordWrapping)
    return f


class Companion(NSObject):
    def initWithPlanner_(self, planner_name):
        self = objc.super(Companion, self).init()
        self.planner = make_planner(planner_name)
        self.overlay, self.overlay_kind = make_overlay()
        self.active = False
        self.question = ""
        self.last_key = None
        self.started = 0.0
        RUNS.mkdir(exist_ok=True)
        self.log_path = RUNS / f"session-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}.jsonl"
        self.build_window()
        self.timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            TICK_S, self, "tick:", None, True)
        self.log("start", planner=self.planner.name, overlay=self.overlay_kind, trusted=reader.is_trusted())
        return self

    # ---------- UI ----------
    @objc.python_method
    def build_window(self):
        screen = NSScreen.mainScreen().visibleFrame()
        w, h = 400, 320
        rect = NSMakeRect(screen.origin.x + screen.size.width - w - 24, screen.origin.y + screen.size.height - h - 24, w, h)
        win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            rect, NSWindowStyleMaskTitled | NSWindowStyleMaskClosable, NSBackingStoreBuffered, False)
        win.setTitle_("Companion")
        win.setLevel_(NSFloatingWindowLevel)
        win.setReleasedWhenClosed_(False)

        self.field = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, 360, 26))
        self.field.setPlaceholderString_("Ask in Malayalam or English (Utter works here)")
        self.field.setTarget_(self)
        self.field.setAction_("ask:")
        ask = NSButton.buttonWithTitle_target_action_("Ask", self, "ask:")
        ask.setKeyEquivalent_("\r")
        stop = NSButton.buttonWithTitle_target_action_("Stop", self, "stop:")
        self.heard = label("", 11)
        self.heard.setTextColor_(NSColor.secondaryLabelColor())
        self.instruction = label("Ask a question to start.", 18, bold=True, wrap=True)
        self.subtitle = label("", 13, wrap=True)
        self.status = label(f"planner: {self.planner.name} · pointer: {self.overlay_kind}", 11, wrap=True)
        self.status.setTextColor_(NSColor.secondaryLabelColor())

        buttons = NSStackView.stackViewWithViews_([ask, stop])
        stack = NSStackView.stackViewWithViews_(
            [self.field, buttons, self.heard, self.instruction, self.subtitle, self.status])
        stack.setOrientation_(NSUserInterfaceLayoutOrientationVertical)
        stack.setAlignment_(1)  # leading
        stack.setSpacing_(10)
        stack.setEdgeInsets_((16, 16, 16, 16))
        win.setContentView_(stack)
        win.makeKeyAndOrderFront_(None)
        self.window = win

    @objc.python_method
    def say(self, decision: Decision | None, ml: str = "", en: str = ""):
        self.instruction.setStringValue_(decision.instruction if decision else ml)
        self.subtitle.setStringValue_(decision.instruction_en if decision else en)

    # ---------- actions ----------
    def ask_(self, sender):
        self.question = str(self.field.stringValue())
        self.heard.setStringValue_(f"Heard: “{self.question}”" if self.question.strip() else "Heard nothing — try again.")
        self.active, self.last_key, self.started = True, None, time.time()
        self.log("question", text=self.question, chars=len(self.question))
        self.tick_(None)

    def stop_(self, sender):
        self.active = False
        self.overlay.hide()
        self.say(None, "നിർത്തി.", "Stopped.")
        self.log("stop")

    # ---------- loop ----------
    def tick_(self, timer):
        if not self.active:
            return
        t0 = time.perf_counter()
        try:
            snap = reader.snapshot(TARGET_BUNDLE)
        except reader.ReaderError as e:
            self.overlay.hide()
            self.say(None, "പരിശീലന ഫോം തുറക്കൂ.", str(e))
            self.status.setStringValue_(f"paused: {e}")
            if self.last_key != "reader-error":
                self.log("reader_error", error=str(e))
                self.last_key = "reader-error"
            return
        t1 = time.perf_counter()
        decision = self.planner.decide(self.question, snap)
        t2 = time.perf_counter()
        ok, why = validate(decision, snap)
        target = snap.control(decision.control_id) if decision.control_id else None
        key = (decision.kind, target.identifier if target else None, target.frame if target else None, ok)
        changed = key != self.last_key

        if decision.kind == "point" and ok:
            if changed:
                self.overlay.show(target.frame, decision.instruction, decision.instruction_en)
        else:
            self.overlay.hide()
        t3 = time.perf_counter()

        if changed:
            self.say(decision)
            self.status.setStringValue_(
                f"planner: {decision.source} · pointer: {self.overlay_kind} · "
                f"observe {1000*(t1-t0):.0f} ms · plan {1000*(t2-t1):.0f} ms · draw {1000*(t3-t2):.0f} ms"
                + ("" if ok else f" · rejected: {why}"))
            self.log("decision", kind=decision.kind, source=decision.source, snapshot=snap.snapshot_id,
                     target=target.identifier if target else None, frame=target.frame if target else None,
                     valid=ok, reason=why, instruction_en=decision.instruction_en,
                     observe_ms=round(1000 * (t1 - t0), 1), plan_ms=round(1000 * (t2 - t1), 1),
                     display_ms=round(1000 * (t3 - t2), 1))
            self.last_key = key

        if decision.kind == "complete":
            receipt = RUNS / "draft-saved.json"
            fresh = receipt.exists() and receipt.stat().st_mtime >= self.started - 1
            self.log("complete", status_text_seen=True, receipt_file_fresh=fresh)
            self.status.setStringValue_(
                "Verified: status text seen" + (" + fresh draft-saved.json receipt" if fresh else " (no receipt file)"))
            self.active = False
        elif decision.kind in ("clarify", "unsupported"):
            self.active = False

    @objc.python_method
    def log(self, event: str, **fields):
        fields.update(event=event, t=round(time.time(), 3))
        with self.log_path.open("a") as fh:
            fh.write(json.dumps(fields, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--planner", default=os.environ.get("COMPANION_PLANNER", "scripted"), choices=["scripted", "sarvam"])
    ap.add_argument("--question", help="pre-fill and ask (rehearsal/testing); normally typed or dictated")
    args = ap.parse_args()
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
    companion = Companion.alloc().initWithPlanner_(args.planner)
    app.activateIgnoringOtherApps_(True)
    if args.question is not None:
        companion.field.setStringValue_(args.question)
        companion.ask_(None)
    print(f"log: {companion.log_path}")
    app.run()


if __name__ == "__main__":
    main()
