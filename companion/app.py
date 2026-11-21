"""HackaThoni Companion: question -> live snapshot -> next step -> validated pointer -> human click -> re-check.

Run from a process that has Accessibility permission (on the build Mac, a Conductor terminal):

    .venv/bin/python -m companion.app [--planner scripted|sarvam]

The person always clicks themselves. The companion never sends clicks or keystrokes.
"""

from __future__ import annotations

import argparse
import threading
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
from .guidance import with_choice_group_bounds
from .planner import ScriptedPlanner
from .tasks import load as load_task
from .validator import validate

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
UI = {
    "ml": {"heard": "കേട്ടത്", "nothing": "ഒന്നും കേട്ടില്ല — വീണ്ടും പറയൂ.", "start": "ചോദ്യം ചോദിച്ച് തുടങ്ങൂ.",
           "ask": "ചോദിക്കൂ", "stop": "നിർത്തൂ", "skip": "ഒഴിവാക്കൂ", "mic": "സംസാരിക്കൂ", "listening": "കേൾക്കുന്നു… നിർത്താൻ അമർത്തൂ",
           "thinking": "മനസ്സിലാക്കുന്നു…",
           "placeholder": "മലയാളത്തിൽ ചോദിക്കൂ (Utter ഇവിടെ പ്രവർത്തിക്കും)"},
    "en": {"heard": "Heard", "nothing": "Heard nothing — try again.", "start": "Ask a question to start.",
           "ask": "Ask", "stop": "Stop", "skip": "Skip", "mic": "Speak", "listening": "Listening… click to stop",
           "thinking": "Understanding…",
           "placeholder": "Ask in English (Utter works here)"},
}
TICK_S = 0.5


def screen_signature(snap) -> tuple:
    """What the planner's answer depends on: which controls exist and which are filled."""
    return tuple(sorted((c.identifier or c.label, c.role, bool(c.filled)) for c in snap.controls))


def rebind(decision: Decision, old_snap, new_snap) -> Decision | None:
    """Carry a decision made on an older snapshot over to a fresh one with the same screen."""
    target = None
    if decision.control_id:
        old = old_snap.control(decision.control_id)
        if old is None:
            return None
        key = old.identifier or (old.role, old.label)
        target = next((c for c in new_snap.controls
                       if (c.identifier or (c.role, c.label)) == key), None)
        if target is None:
            return None
    return Decision(decision.kind, new_snap.snapshot_id, decision.instruction, decision.instruction_en,
                    target.id if target else None, decision.source)
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
        self.mute = False  # set from --mute; QA runs stay silent so they don't spend credits
        self.recording = False
        self.last_snapshot = None
        self.last_spoken = None
        self.plan_lock = threading.Lock()
        self.plan_thread = None
        self.plan_result = None  # (decision, snapshot, signature, plan_ms) from the background planner
        self.question_version = 0
        self.task = load_task(task_name)
        self.planner = make_planner(planner_name, task_name)
        self.background = getattr(self.planner, "name", "") == "sarvam"  # network planners must not block the UI
        self.overlay, self.overlay_kind = make_overlay()
        self.active = False
        self.progressed, self.unsure = False, 0
        self.question = ""
        self.last_key = None  # logical step: (kind, stable target, instruction, valid); logged and spoken once
        self.shown_frame = None  # where the pointer is drawn now; redrawn on any shift without re-narrating
        self.panel_thinking = False
        self.reader_error_logged = False
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
        self.skip_button = skip = NSButton.buttonWithTitle_target_action_(t["skip"], self, "skip:")
        skip.setToolTip_("Skip this optional step")
        skip.setAccessibilityIdentifier_("companion-skip")
        self.mic_button = mic = NSButton.buttonWithTitle_target_action_("🎤 " + t["mic"], self, "mic:")
        mic.setEnabled_(self.voice is not None)
        mic.setToolTip_(None if self.voice else "Sarvam voice not connected yet (needs the voice module and SARVAM_API_KEY)")
        self.heard = label("", 11)
        self.heard.setTextColor_(NSColor.secondaryLabelColor())
        self.instruction = label(t["start"], 18, bold=True, wrap=True)
        self.subtitle = label("", 13, wrap=True)
        self.status = label(f"planner: {self.planner.name} · pointer: {self.overlay_kind}", 11, wrap=True)
        self.status.setTextColor_(NSColor.secondaryLabelColor())

        buttons = NSStackView.stackViewWithViews_([ask, mic, skip, stop])
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
        self.skip_button.setTitle_(t["skip"])
        self.mic_button.setTitle_("🎤 " + t["mic"])
        self.reset_mic()
        if self.last_decision is not None:
            self.say(self.last_decision)
            self.last_spoken = None
            self.speak(self.last_decision)
        self.last_key = None  # redraw the pointer in the new language on the next tick
        self.shown_frame = None
        self.log("language", lang=self.lang)

    # ---------- voice (Sarvam) ----------
    @objc.python_method
    def pref(self) -> str:
        return "ml-IN" if self.lang == "ml" else "en-IN"

    @objc.python_method
    def keyterms(self) -> list[str]:
        """English labels on the current screen help Saaras hear 'Next', 'Save Draft' and the like."""
        snap, seen = self.last_snapshot, []
        for c in (snap.controls if snap else ()):
            if c.label and len(c.label) <= 40 and c.role != "AXStaticText" and c.label not in seen:
                seen.append(c.label)
        return seen[:50]

    def mic_(self, sender):
        if self.voice is None:
            return
        t = UI[self.lang]
        if not self.recording:
            self.recording = True
            self.voice.stop_speaking()
            self.mic_button.setTitle_("🔴 " + t["listening"])
            threading.Thread(target=self.record_worker, daemon=True).start()
        else:
            self.recording = False
            self.mic_button.setEnabled_(False)
            self.mic_button.setTitle_("… " + t["thinking"])
            threading.Thread(target=self.transcribe_worker, args=(self.pref(), self.keyterms()), daemon=True).start()

    @objc.python_method
    def record_worker(self):
        try:
            self.voice.record_push_to_talk()
            self.log("mic_start")
        except Exception as e:  # noqa: BLE001 - permission or helper failure is shown, not raised
            self.recording = False
            self.on_main("voiceFailed:", f"Microphone: {e}")

    @objc.python_method
    def transcribe_worker(self, pref, keyterms):
        t0 = time.perf_counter()
        try:
            wav = self.voice.stop_recording()
            heard = self.voice.ask(wav, pref, keyterms=keyterms)
        except Exception as e:  # noqa: BLE001
            self.on_main("voiceFailed:", f"Voice: {e}")
            return
        self.log("voice_heard", provider=heard.provider, model=heard.model, text=heard.text,
                 english=heard.english_translation.text if heard.english_translation else None,
                 ms=round(1000 * (time.perf_counter() - t0)), sarvam_calls=2 if pref == "ml-IN" else 1)
        self.on_main("voiceHeard:", {"text": heard.text, "planner": heard.planner_text})

    @objc.python_method
    def on_main(self, selector, payload):
        self.performSelectorOnMainThread_withObject_waitUntilDone_(selector, payload, False)

    def voiceHeard_(self, payload):
        self.reset_mic()
        native, english = payload["text"], payload["planner"]
        self.field.setStringValue_(native)
        # The planner sees both: the native words and Sarvam's English translation of them.
        self.start_question(native if english == native else f"{native} / {english}", shown=native)

    def voiceFailed_(self, message):
        self.reset_mic()
        self.status.setStringValue_(str(message))
        self.log("voice_error", error=str(message))

    @objc.python_method
    def reset_mic(self):
        self.recording = False
        self.mic_button.setEnabled_(self.voice is not None)
        self.mic_button.setTitle_("🎤 " + UI[self.lang]["mic"])

    @objc.python_method
    def speak(self, decision: Decision):
        """Read each new instruction aloud once, in the user's language."""
        text = self.text_for(decision)
        if self.voice is None or self.mute or not text or text == self.last_spoken:
            return
        self.last_spoken = text
        pref = self.pref()

        def run():
            try:
                self.voice.speak(text, pref)
                self.log("spoke", chars=len(text), lang=pref, sarvam_calls=1)
            except Exception as e:  # noqa: BLE001 - readable text stays on screen if speech fails
                self.on_main("voiceFailed:", f"Speech: {e}")
        threading.Thread(target=run, daemon=True).start()

    # ---------- actions ----------
    def ask_(self, sender):
        text = str(self.field.stringValue())
        self.start_question(text, shown=text)

    @objc.python_method
    def start_question(self, question: str, shown: str):
        with self.plan_lock:
            self.question = question
            self.question_version += 1
            self.plan_result = None
            reset_question = getattr(self.planner, "reset_question", None)
            if reset_question is not None:
                reset_question()
        self.last_spoken = None
        t = UI[self.lang]
        self.heard.setStringValue_(f"{t['heard']}: “{shown}”" if shown.strip() else t["nothing"])
        self.active, self.last_key, self.started = True, None, time.time()
        self.shown_frame, self.panel_thinking = None, False
        self.progressed, self.unsure = False, 0
        self.log("question", text=self.question, chars=len(self.question))
        self.tick_(None)

    def skip_(self, sender):
        """Skip the step currently pointed at (optional fields, toppings...). The planner decides what's next."""
        skip = getattr(self.planner, "skip_current", None)
        if skip is None or not self.active:
            return
        skip()
        with self.plan_lock:
            self.plan_result = None
        self.last_key = None
        self.shown_frame = None
        self.log("skip")
        self.tick_(None)

    def stop_(self, sender):
        self.active = False
        self.overlay.hide()
        if self.voice is not None:
            self.voice.stop_speaking()
        self.say(None, "നിർത്തി.", "Stopped.")
        self.log("stop")

    # ---------- loop ----------
    def tick_(self, timer):
        if not self.active:
            return
        t0 = time.perf_counter()
        try:
            snap = reader.snapshot(self.task.bundle_id, page_title=self.task.page_title,
                                   page_url_prefix=self.task.page_url_prefix)
            snap = with_choice_group_bounds(snap)
            self.last_snapshot = snap
        except reader.ReaderError as e:
            self.overlay.hide()
            self.shown_frame = None
            self.say(None, "പരിശീലന ഫോം തുറക്കൂ.", str(e))
            self.status.setStringValue_(f"paused: {e}")
            if not self.reader_error_logged:
                self.log("reader_error", error=str(e))
                self.reader_error_logged = True
            return
        self.reader_error_logged = False
        t1 = time.perf_counter()
        if self.background:
            decision, plan_ms = self.background_decision(snap)
            if decision is None:  # the planner is still thinking about this screen
                return
        else:
            decision = self.planner.decide(self.question, snap)
            plan_ms = None
        t2 = time.perf_counter()
        if decision.kind == "unsupported" and self.progressed:
            self.unsure += 1
            if self.unsure < SETTLE_TICKS:  # likely a half-drawn screen; look again before giving up
                return
        else:
            self.unsure = 0
        ok, why = validate(decision, snap)
        target = snap.control(decision.control_id) if decision.control_id else None
        stable_target = (target.identifier or (target.role, target.label)) if target else None
        key = (decision.kind, stable_target, decision.instruction, ok)
        changed = key != self.last_key

        if decision.kind == "point" and ok:
            self.progressed = True
            if changed or target.frame != self.shown_frame:  # a 1-pt layout shift repaints, nothing more
                self.overlay.show(target.frame, self.text_for(decision), "")
                self.shown_frame = target.frame
        elif self.shown_frame is not None:
            self.overlay.hide()
            self.shown_frame = None
        t3 = time.perf_counter()
        if not changed and self.panel_thinking:  # same step after a re-plan: restore the text quietly
            self.say(decision)
        self.panel_thinking = False

        if changed:
            if plan_ms is not None:
                self.status.setStringValue_(str(self.status.stringValue()).replace(
                    f"plan {1000*(t2-t1):.0f} ms", f"plan {plan_ms:.0f} ms"))
            self.say(decision)
            self.speak(decision)
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
        elif decision.kind == "unsupported" or (decision.kind == "clarify" and not self.progressed):
            self.active = False  # mid-task "clarify" (e.g. "scroll down to continue") keeps watching the screen

    @objc.python_method
    def background_decision(self, snap):
        """Return (decision for this exact screen, plan ms) or (None, None) while still planning."""
        sig = screen_signature(snap)
        with self.plan_lock:
            result, running = self.plan_result, self.plan_thread is not None and self.plan_thread.is_alive()
        if not running and (result is None or result[2] != sig):
            question = self.question
            question_version = self.question_version

            def work():
                t0 = time.perf_counter()
                try:
                    d = self.planner.decide(question, snap)
                except Exception as e:  # noqa: BLE001 - a failed call becomes an honest unsupported
                    d = Decision("unsupported", snap.snapshot_id, "സഹായി ഇപ്പോൾ ലഭ്യമല്ല.",
                                 f"Planner error: {e}", source="sarvam")
                with self.plan_lock:
                    if question_version == self.question_version:  # drop late answers to an earlier submission
                        self.plan_result = (d, snap, sig, 1000 * (time.perf_counter() - t0))
            self.plan_thread = threading.Thread(target=work, daemon=True)
            self.plan_thread.start()
        if result is None or result[2] != sig:
            if not self.panel_thinking:
                self.overlay.hide()
                self.shown_frame = None
                self.instruction.setStringValue_(UI[self.lang]["thinking"])
                self.panel_thinking = True
            return None, None
        decision = rebind(result[0], result[1], snap)
        if decision is None:
            with self.plan_lock:
                self.plan_result = None
            return None, None
        return decision, result[3]

    @objc.python_method
    def log(self, event: str, **fields):
        fields.update(event=event, t=round(time.time(), 3))
        with self.log_path.open("a") as fh:
            fh.write(json.dumps(fields, ensure_ascii=False) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--planner", default=os.environ.get("COMPANION_PLANNER"), choices=["scripted", "sarvam"],
                    help="default: sarvam for web_any (no step script), scripted otherwise")
    ap.add_argument("--task", default=os.environ.get("COMPANION_TASK", "aims"), help="companion/tasks/<name>.py")
    ap.add_argument("--mute", action="store_true", help="no spoken replies (QA, or to save Sarvam credits)")
    ap.add_argument("--lang", default=os.environ.get("COMPANION_LANG", "ml"), choices=["ml", "en"])
    ap.add_argument("--question", help="pre-fill and ask (rehearsal/testing); normally typed or dictated")
    args = ap.parse_args()
    args.planner = args.planner or ("sarvam" if args.task in ("web_any", "web_site") else "scripted")
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
    companion = Companion.alloc().initWithPlanner_task_lang_(args.planner, args.task, args.lang)
    companion.mute = args.mute
    app.activateIgnoringOtherApps_(True)
    if args.question is not None:
        companion.field.setStringValue_(args.question)
        companion.ask_(None)
    print(f"log: {companion.log_path}")
    app.run()


if __name__ == "__main__":
    main()
