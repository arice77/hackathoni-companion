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
from AppKit import NSApplication, NSApplicationActivationPolicyRegular
from Foundation import NSObject, NSTimer

from .panel import LANGUAGES, WORDS, PaperPanel
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
    "hi": {"nothing": "कुछ सुनाई नहीं दिया। फिर से बोलें।", "start": "शुरू करने के लिए सवाल पूछें।",
           "mic": "बोलें", "listening": "सुन रहा हूँ… रोकने के लिए दबाएँ",
           "placeholder": "हिन्दी में अपना सवाल लिखें"},
    "kn": {"nothing": "ಏನೂ ಕೇಳಿಸಲಿಲ್ಲ. ಮತ್ತೊಮ್ಮೆ ಹೇಳಿ.", "start": "ಪ್ರಾರಂಭಿಸಲು ಒಂದು ಪ್ರಶ್ನೆ ಕೇಳಿ.",
           "mic": "ಮಾತನಾಡಿ", "listening": "ಕೇಳುತ್ತಿದ್ದೇನೆ… ನಿಲ್ಲಿಸಲು ಒತ್ತಿ",
           "placeholder": "ಕನ್ನಡದಲ್ಲಿ ನಿಮ್ಮ ಪ್ರಶ್ನೆಯನ್ನು ಬರೆಯಿರಿ"},
}
for _lang in ("hi", "kn"):
    UI[_lang].update({key: WORDS[_lang][key] for key in ("ask", "skip", "stop", "heard")})
    UI[_lang]["thinking"] = WORDS[_lang]["think"]
TICK_S = 0.5


def screen_signature(snap) -> tuple:
    """What the planner's answer depends on: which controls exist and which are filled."""
    return (tuple(sorted((c.identifier or c.label, c.role, bool(c.filled)) for c in snap.controls)),
            getattr(snap, "below_fold_count", 0))  # scrolling alone must refresh "scroll down" guidance


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


class Companion(NSObject):
    def initWithPlanner_task_lang_(self, planner_name, task_name, lang):
        self = objc.super(Companion, self).init()
        self.lang = lang
        self.translations = {}
        self.pending_translations = set()
        self.failed_translations = set()
        self.translating_question = False
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
        self.panel = PaperPanel.alloc().initWithOwner_(self)
        self.window = self.panel.window
        self.lang_switch = self.panel.lang_switch
        self.field, self.ask_button = self.panel.field, self.panel.ask_button
        self.mic_button, self.stop_button = self.panel.mic_button, self.panel.stop_button
        self.skip_button = self.panel.skip_button
        self.instruction, self.heard, self.status = self.panel.instruction, self.panel.heard, self.panel.status
        self.window.orderFrontRegardless()

    @objc.python_method
    def say(self, decision: Decision | None, ml: str = "", en: str = ""):
        if decision is None:
            self.panel.set_state("page_error" if self.active else "idle", ml=ml, en=en)
        else:
            # tick_ supplies the validated screen label. A language switch
            # reuses that same step and must also preserve stopped/error states.
            self.last_decision = decision
            self.panel.set_state("language")

    @objc.python_method
    def text_for(self, decision: Decision) -> str:
        if self.lang == "ml":
            return decision.instruction
        english = decision.instruction_en
        return self.translations.get((english, self.pref()), english or decision.instruction)

    @objc.python_method
    def request_translation(self, decision):
        english, pref = decision.instruction_en, self.pref()
        key = (english, pref)
        if (self.lang not in ("hi", "kn") or not english or self.voice is None or key in self.translations
                or key in self.pending_translations or key in self.failed_translations):
            return
        self.pending_translations.add(key)

        def work():
            try:
                text = self.voice.translate_instruction(english, pref)
            except self.voice.sarvam.SarvamError:
                text = ""
            self.on_main("instructionTranslated:", (english, pref, text))

        threading.Thread(target=work, daemon=True).start()

    def instructionTranslated_(self, payload):
        english, pref, text = payload
        key = (english, pref)
        self.pending_translations.discard(key)
        if text:
            self.translations[key] = text
        else:
            self.failed_translations.add(key)  # keep the English step, retry on the next question
        decision = self.panel.current_decision
        if decision is None or self.pref() != pref or decision.instruction_en != english:
            return
        self.panel.render()
        if self.active and self.shown_frame is not None and decision.kind == "point":
            self.overlay.show(self.shown_frame, self.text_for(decision), "")
        if not self.panel.voice_phase:
            self.speak(decision)

    def langChanged_(self, sender):
        self.lang = LANGUAGES[sender.selectedSegment()]
        self.reset_mic()
        if self.voice is not None:
            self.voice.stop_speaking()
        self.panel.set_state("language")
        decision = self.panel.current_decision
        if decision is not None:
            self.request_translation(decision)
            if self.active and self.shown_frame is not None and decision.kind == "point":
                self.overlay.show(self.shown_frame, self.text_for(decision), "")
            self.last_spoken = None
            self.speak(decision)
        self.log("language", lang=self.lang)

    # ---------- voice (Sarvam) ----------
    @objc.python_method
    def pref(self) -> str:
        return f"{self.lang}-IN"

    @objc.python_method
    def keyterms(self) -> list[str]:
        """English labels on the current screen help Saaras hear 'Next', 'Save Draft' and the like."""
        snap, seen = self.last_snapshot, []
        for c in (snap.controls if snap else ()):
            # Saaras rejects any keyterm containing a comma or semicolon (HTTP 400), so skip those labels.
            if (c.label and len(c.label) <= 40 and c.role != "AXStaticText" and c.label not in seen
                    and not any(ch in c.label for ch in ",;")):
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
            self.panel.set_state("listening")
            threading.Thread(target=self.record_worker, daemon=True).start()
        else:
            self.recording = False
            self.mic_button.setEnabled_(False)
            self.mic_button.setTitle_("… " + t["thinking"])
            self.panel.set_state("transcribing")
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
                 ms=round(1000 * (time.perf_counter() - t0)), sarvam_calls=1 + int(heard.english_translation is not None))
        self.on_main("voiceHeard:", {"text": heard.text, "planner": heard.planner_text, "preference": pref})

    @objc.python_method
    def on_main(self, selector, payload):
        self.performSelectorOnMainThread_withObject_waitUntilDone_(selector, payload, False)

    def voiceHeard_(self, payload):
        self.reset_mic()
        native, english = payload["text"], payload["planner"]
        self.field.setStringValue_(native)
        question = english
        if native != english and payload["preference"] in ("ml-IN", "en-IN"):
            question = f"{native} / {english}"
        self.start_question(question, shown=native)

    def voiceFailed_(self, message):
        self.reset_mic()
        self.status.setStringValue_(str(message))
        self.panel.set_state("voice_error")
        self.log("voice_error", error=str(message))

    @objc.python_method
    def reset_mic(self):
        self.recording = False
        self.mic_button.setEnabled_(self.voice is not None)
        self.mic_button.setTitle_("🎤 " + UI[self.lang]["mic"])

    @objc.python_method
    def speak(self, decision: Decision):
        """Read each new instruction aloud once, in the user's language."""
        if (decision.instruction_en, self.pref()) in self.pending_translations:
            return
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
        self.start_question(text, shown=text, translate=self.lang in ("hi", "kn") and bool(text.strip()))

    @objc.python_method
    def start_question(self, question: str, shown: str, translate=False):
        with self.plan_lock:
            self.question = question
            self.question_version += 1
            self.plan_result = None
            reset_question = getattr(self.planner, "reset_question", None)
            if reset_question is not None:
                reset_question()
        self.last_spoken = None
        self.failed_translations.clear()
        self.translating_question = translate
        t = UI[self.lang]
        self.heard.setStringValue_(f"{t['heard']}: “{shown}”" if shown.strip() else t["nothing"])
        self.active, self.last_key, self.started = True, None, time.time()
        self.shown_frame, self.panel_thinking = None, False
        self.progressed, self.unsure = False, 0
        self.panel.set_state("question", heard=shown)
        if translate:
            version, pref = self.question_version, self.pref()
            self.overlay.hide()

            def work():
                english = ""
                if self.voice is not None:
                    try:
                        english = self.voice.sarvam.translate_text(question, pref, "en-IN").strip()
                    except self.voice.sarvam.SarvamError:
                        pass
                self.on_main("questionTranslated:", (version, english))

            threading.Thread(target=work, daemon=True).start()
            return
        self.log("question", text=self.question, chars=len(self.question))
        self.tick_(None)

    def questionTranslated_(self, payload):
        version, english = payload
        if self.question_version != version or not self.active:
            return
        self.translating_question = False
        if not english:
            self.active = False
            self.panel.set_state("question_error")
            return
        self.question = english
        self.log("question", text=english, chars=len(english))
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
        if not self.active or self.translating_question:
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
        key = (decision.kind, stable_target, decision.instruction, decision.instruction_en, ok)
        changed = key != self.last_key
        self.request_translation(decision)

        if decision.kind == "point" and ok:
            self.progressed = True
            if changed or target.frame != self.shown_frame:  # a 1-pt layout shift repaints, nothing more
                self.overlay.show(target.frame, self.text_for(decision), "")
                self.shown_frame = target.frame
        elif self.shown_frame is not None:
            self.overlay.hide()
            self.shown_frame = None
        t3 = time.perf_counter()
        self.panel.set_state("decision", decision=decision, target=target.label if ok and target else "")
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
        elif decision.kind == "unsupported":
            self.active = False
        # "clarify" keeps watching: "scroll down", "open a video first" or a menu that hasn't appeared yet
        # can resolve on the next screen without a new question (QA live run, 22 Nov 01:07).

    @objc.python_method
    def background_decision(self, snap):
        """Return (decision for this exact screen, plan ms) or (None, None) while still planning."""
        sig = screen_signature(snap)
        with self.plan_lock:
            result, running = self.plan_result, self.plan_thread is not None and self.plan_thread.is_alive()
        retry_at = getattr(self.planner, "retry_at", None)  # planner-owned timed retry on an unchanged screen
        due = retry_at is not None and time.monotonic() >= retry_at
        if not running and (result is None or result[2] != sig or due):
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
            if result is not None and result[0].kind in {"point", "clarify"}:
                # Live pages (YouTube previews, carousels) change every tick. Keep the current step on screen
                # while re-planning instead of flashing "Understanding…" (Abin's real-mic test, 22 Nov 02:20).
                stale = rebind(result[0], result[1], snap)
                if stale is not None:
                    return stale, result[3]
            if not self.panel_thinking:
                self.overlay.hide()
                self.shown_frame = None
                self.instruction.setStringValue_(UI[self.lang]["thinking"])
                self.panel.set_state("thinking")
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


def parse_args(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--planner", default=os.environ.get("COMPANION_PLANNER"), choices=["scripted", "sarvam"],
                    help="default: sarvam for web_any (no step script), scripted otherwise")
    ap.add_argument("--task", default=os.environ.get("COMPANION_TASK", "aims"), help="companion/tasks/<name>.py")
    ap.add_argument("--mute", action="store_true", help="no spoken replies (QA, or to save Sarvam credits)")
    ap.add_argument("--lang", default=os.environ.get("COMPANION_LANG", "ml"), choices=LANGUAGES)
    ap.add_argument("--question", help="pre-fill and ask (rehearsal/testing); normally typed or dictated")
    args = ap.parse_args(argv)
    if args.lang not in LANGUAGES:
        ap.error(f"Unsupported COMPANION_LANG: {args.lang}")
    args.planner = args.planner or ("sarvam" if args.task in ("web_any", "web_site") else "scripted")
    return args


def main():
    args = parse_args()
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
