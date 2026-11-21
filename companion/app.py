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
    NSSegmentedControl,
)
from Foundation import NSMakeRect, NSObject, NSTimer

from . import reader
from .contracts import Decision
from .planner import ScriptedPlanner
from .tasks import load as load_task
from .validator import validate

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
UI = {
    "ml": {"heard": "കേട്ടത്", "nothing": "ഒന്നും കേട്ടില്ല — വീണ്ടും പറയൂ.", "start": "ചോദ്യം ചോദിച്ച് തുടങ്ങൂ.",
           "ask": "ചോദിക്കൂ", "stop": "നിർത്തൂ", "mic": "പിടിച്ച് സംസാരിക്കൂ",
           "placeholder": "മലയാളത്തിൽ ചോദിക്കൂ (Utter ഇവിടെ പ്രവർത്തിക്കും)"},
    "en": {"heard": "Heard", "nothing": "Heard nothing — try again.", "start": "Ask a question to start.",
           "ask": "Ask", "stop": "Stop", "mic": "Hold to speak",
           "placeholder": "Ask in English (Utter works here)"},
}
TICK_S = 0.5
SETTLE_TICKS = 3  # mid-task "unsupported" must persist this many ticks (screens redraw in pieces)


def make_overlay():
    try:
        from .overlay import SketchOverlay  # delivered by the overlay agent
        return SketchOverlay(), "sketch"
    except Exception:  # noqa: BLE001 - any import/setup failure falls back to the plain pointer
        from .overlay_basic import BasicOverlay
        return BasicOverlay(), "basic"


def load_voice():
    """Sarvam voice module when merged and usable; None keeps the mic button disabled."""
    try:
        from . import voice  # delivered by the voice builder
        return voice if hasattr(voice, "ask") else None
    except Exception:  # noqa: BLE001
        return None


def make_planner(name: str, task: str):
    if name == "sarvam":
        from .planner_sarvam import SarvamPlanner  # requires SARVAM_API_KEY
        return SarvamPlanner(task)
    return ScriptedPlanner(task)


def label(text: str, size: float, bold: bool = False, wrap: bool = False) -> NSTextField:
    f = NSTextField.wrappingLabelWithString_(text) if wrap else NSTextField.labelWithString_(text)
    f.setFont_(NSFont.boldSystemFontOfSize_(size) if bold else NSFont.systemFontOfSize_(size))
    if wrap:
        f.setPreferredMaxLayoutWidth_(360)
        f.cell().setLineBreakMode_(NSLineBreakByWordWrapping)
    return f


class Companion(NSObject):
    def initWithPlanner_task_lang_(self, planner_name, task_name, lang):
        self = objc.super(Companion, self).init()
        self.lang = lang  # "ml" or "en": language of the panel, the overlay and (later) the voice
        self.last_decision = None
        self.voice = load_voice()
        self.task = load_task(task_name)
        self.planner = make_planner(planner_name, task_name)
        self.overlay, self.overlay_kind = make_overlay()
        self.active = False
        self.progressed, self.unsure = False, 0
        self.question = ""
        self.last_key = None
        self.started = 0.0
        RUNS.mkdir(exist_ok=True)
        self.log_path = RUNS / f"session-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}.jsonl"
        self.build_window()
        self.timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            TICK_S, self, "tick:", None, True)
        self.log("start", lang=self.lang, voice=self.voice is not None, task=self.task.name, planner=self.planner.name, overlay=self.overlay_kind, trusted=reader.is_trusted())
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

        t = UI[self.lang]
        self.lang_switch = NSSegmentedControl.segmentedControlWithLabels_trackingMode_target_action_(
            ["മലയാളം", "English"], 0, self, "langChanged:")
        self.lang_switch.setSelectedSegment_(0 if self.lang == "ml" else 1)
        self.field = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, 360, 26))
        self.field.setPlaceholderString_(t["placeholder"])
        self.field.setTarget_(self)
        self.field.setAction_("ask:")
        self.ask_button = ask = NSButton.buttonWithTitle_target_action_(t["ask"], self, "ask:")
        ask.setKeyEquivalent_("\r")
        self.stop_button = stop = NSButton.buttonWithTitle_target_action_(t["stop"], self, "stop:")
        self.mic_button = mic = NSButton.buttonWithTitle_target_action_("🎤 " + t["mic"], self, "mic:")
        mic.setEnabled_(self.voice is not None)
        mic.setToolTip_(None if self.voice else "Sarvam voice not connected yet (needs the voice module and SARVAM_API_KEY)")
        self.heard = label("", 11)
        self.heard.setTextColor_(NSColor.secondaryLabelColor())
        self.instruction = label(t["start"], 18, bold=True, wrap=True)
        self.subtitle = label("", 13, wrap=True)
        self.status = label(f"planner: {self.planner.name} · pointer: {self.overlay_kind}", 11, wrap=True)
        self.status.setTextColor_(NSColor.secondaryLabelColor())

        buttons = NSStackView.stackViewWithViews_([ask, mic, stop])
        stack = NSStackView.stackViewWithViews_(
            [self.lang_switch, self.field, buttons, self.heard, self.instruction, self.subtitle, self.status])
        stack.setOrientation_(NSUserInterfaceLayoutOrientationVertical)
        stack.setAlignment_(1)  # leading
        stack.setSpacing_(10)
        stack.setEdgeInsets_((16, 16, 16, 16))
        win.setContentView_(stack)
        win.makeKeyAndOrderFront_(None)
        self.window = win

    @objc.python_method
    def say(self, decision: Decision | None, ml: str = "", en: str = ""):
        """Show one language only: the user's preference. Subtitle is reserved for system detail."""
        if decision is not None:
            self.last_decision = decision
            ml, en = decision.instruction, decision.instruction_en
        self.instruction.setStringValue_(ml if self.lang == "ml" else (en or ml))
        self.subtitle.setStringValue_("" if decision is not None else (en if self.lang == "ml" else ""))

    @objc.python_method
    def text_for(self, decision: Decision) -> str:
        return decision.instruction if self.lang == "ml" else (decision.instruction_en or decision.instruction)

    def langChanged_(self, sender):
        self.lang = "ml" if sender.selectedSegment() == 0 else "en"
        t = UI[self.lang]
        self.field.setPlaceholderString_(t["placeholder"])
        self.ask_button.setTitle_(t["ask"])
        self.stop_button.setTitle_(t["stop"])
        self.mic_button.setTitle_("🎤 " + t["mic"])
        if self.last_decision is not None:
            self.say(self.last_decision)
        self.last_key = None  # redraw the pointer in the new language on the next tick
        self.log("language", lang=self.lang)

    def mic_(self, sender):
        pass  # wired when the voice module lands (push-to-talk -> ask -> planner -> speak)

    # ---------- actions ----------
    def ask_(self, sender):
        self.question = str(self.field.stringValue())
        t = UI[self.lang]
        self.heard.setStringValue_(f"{t['heard']}: “{self.question}”" if self.question.strip() else t["nothing"])
        self.active, self.last_key, self.started = True, None, time.time()
        self.progressed, self.unsure = False, 0
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
            snap = reader.snapshot(self.task.bundle_id)
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
        if decision.kind == "unsupported" and self.progressed:
            self.unsure += 1
            if self.unsure < SETTLE_TICKS:  # likely a half-drawn screen; look again before giving up
                return
        else:
            self.unsure = 0
        ok, why = validate(decision, snap)
        target = snap.control(decision.control_id) if decision.control_id else None
        key = (decision.kind, target.identifier if target else None, target.frame if target else None, ok)
        changed = key != self.last_key

        if decision.kind == "point" and ok:
            self.progressed = True
            if changed:
                self.overlay.show(target.frame, self.text_for(decision), "")
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
            receipt = RUNS / self.task.receipt_file
            fresh = receipt.exists() and receipt.stat().st_mtime >= self.started - 1
            self.log("complete", status_text_seen=True, receipt_file_fresh=fresh)
            self.status.setStringValue_(
                "Verified: status text seen" + (" + fresh training receipt file" if fresh else " (no receipt file)"))
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
    ap.add_argument("--task", default=os.environ.get("COMPANION_TASK", "aims"), help="companion/tasks/<name>.py")
    ap.add_argument("--lang", default=os.environ.get("COMPANION_LANG", "ml"), choices=["ml", "en"])
    ap.add_argument("--question", help="pre-fill and ask (rehearsal/testing); normally typed or dictated")
    args = ap.parse_args()
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
    companion = Companion.alloc().initWithPlanner_task_lang_(args.planner, args.task, args.lang)
    app.activateIgnoringOtherApps_(True)
    if args.question is not None:
        companion.field.setStringValue_(args.question)
        companion.ask_(None)
    print(f"log: {companion.log_path}")
    app.run()


if __name__ == "__main__":
    main()
