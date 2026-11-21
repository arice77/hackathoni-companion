"""Paper Note companion panel. The owner supplies voice, planner and action handlers."""

from dataclasses import dataclass
from math import ceil

import AppKit as A
import objc
from Foundation import NSObject

from .views import (
    INK, MUTED, LanguagePills, PanelActivityIndicator, PaperButton,
    PaperPanelWindow, PaperSurface, hand, text_height, text_style,
)


@dataclass(frozen=True)
class PanelState:
    name: str
    ml: str = ""
    en: str = ""
    target: str = ""


WORDS = {
    "ml": {
        "language": "മലയാളം", "stopped": "നിർത്തി.", "speech_failed": "ശബ്ദം ലഭ്യമല്ല. നിർദേശം വായിക്കാം.",
        "question_error": "ചോദ്യം വിവർത്തനം ചെയ്യാനായില്ല. വീണ്ടും ശ്രമിക്കൂ.",
        "prompt": "എന്താണ് സഹായം വേണ്ടത്?", "intro": "പറഞ്ഞാൽ മതി, സ്ക്രീനിൽ ഞാൻ കാണിച്ചുതരാം.",
        "speak": "സംസാരിക്കാൻ അമർത്തൂ", "listen": "കേൾക്കുന്നു…", "finish": "പറഞ്ഞു കഴിഞ്ഞാൽ വീണ്ടും അമർത്തൂ.",
        "think": "മനസ്സിലാക്കുന്നു…", "type": "ചോദ്യം ടൈപ്പ് ചെയ്യൂ", "screen": "സ്ക്രീനിൽ",
        "new": "പുതിയ ചോദ്യം", "replay": "വീണ്ടും കേൾക്കൂ", "details": "സാങ്കേതിക വിവരങ്ങൾ",
        "heard": "കേട്ടത്", "again": "വീണ്ടും ശ്രമിക്കാം", "voice_error": "ശബ്ദം ഉപയോഗിക്കാൻ കഴിഞ്ഞില്ല. ടൈപ്പ് ചെയ്യുകയോ വീണ്ടും ശ്രമിക്കുകയോ ചെയ്യൂ.",
        "page_error": "സഹായം വേണ്ട പേജ് തുറക്കൂ.", "stop": "നിർത്തൂ", "skip": "ഒഴിവാക്കൂ", "ask": "ചോദിക്കൂ",
    },
    "en": {
        "language": "English", "stopped": "Stopped.", "speech_failed": "Voice is unavailable. You can read the step above.",
        "question_error": "I couldn’t translate your question. Please try again.",
        "prompt": "What can I help you do?", "intro": "Tell me, and I’ll point it out on screen.",
        "speak": "Tap to speak", "listen": "Listening…", "finish": "Tap again when you’ve finished.",
        "think": "Understanding…", "type": "Type your question", "screen": "On screen",
        "new": "New question", "replay": "Hear this step again", "details": "Technical details",
        "heard": "Heard", "again": "Let’s try again", "voice_error": "Voice is unavailable. Type your question or try speaking again.",
        "page_error": "Open the page you’d like help with.", "stop": "Stop", "skip": "Skip", "ask": "Ask",
    },
    "hi": {
        "language": "हिन्दी", "prompt": "आपको किस काम में मदद चाहिए?", "intro": "मुझे बताइए, मैं स्क्रीन पर दिखाऊँगा।",
        "question_error": "सवाल का अनुवाद नहीं हो पाया। फिर से कोशिश करें।",
        "speak": "बोलने के लिए दबाएँ", "listen": "सुन रहा हूँ…", "finish": "बात पूरी हो जाए तो फिर से दबाएँ।",
        "think": "समझ रहा हूँ…", "type": "अपना सवाल लिखें", "screen": "स्क्रीन पर",
        "new": "नया सवाल", "replay": "यह कदम फिर से सुनें", "details": "तकनीकी जानकारी",
        "heard": "आपने कहा", "again": "फिर से कोशिश करें", "voice_error": "आवाज़ उपलब्ध नहीं है। अपना सवाल लिखें या फिर से बोलें।",
        "page_error": "जिस पेज पर मदद चाहिए, उसे खोलें।", "stop": "रोकें", "skip": "छोड़ें", "ask": "पूछें",
        "stopped": "रुक गया।", "speech_failed": "आवाज़ उपलब्ध नहीं है। ऊपर दिया निर्देश पढ़ें।",
    },
    "kn": {
        "language": "ಕನ್ನಡ", "prompt": "ನಿಮಗೆ ಯಾವ ಕೆಲಸದಲ್ಲಿ ಸಹಾಯ ಬೇಕು?", "intro": "ಹೇಳಿ, ಪರದೆಯ ಮೇಲೆ ತೋರಿಸುತ್ತೇನೆ.",
        "question_error": "ಪ್ರಶ್ನೆಯನ್ನು ಅನುವಾದಿಸಲು ಆಗಲಿಲ್ಲ. ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.",
        "speak": "ಮಾತನಾಡಲು ಒತ್ತಿ", "listen": "ಕೇಳುತ್ತಿದ್ದೇನೆ…", "finish": "ಮಾತು ಮುಗಿದ ಮೇಲೆ ಮತ್ತೊಮ್ಮೆ ಒತ್ತಿ.",
        "think": "ಅರ್ಥಮಾಡಿಕೊಳ್ಳುತ್ತಿದ್ದೇನೆ…", "type": "ನಿಮ್ಮ ಪ್ರಶ್ನೆಯನ್ನು ಬರೆಯಿರಿ", "screen": "ಪರದೆಯ ಮೇಲೆ",
        "new": "ಹೊಸ ಪ್ರಶ್ನೆ", "replay": "ಈ ಸೂಚನೆಯನ್ನು ಮತ್ತೆ ಕೇಳಿ", "details": "ತಾಂತ್ರಿಕ ವಿವರಗಳು",
        "heard": "ನೀವು ಹೇಳಿದ್ದು", "again": "ಮತ್ತೆ ಪ್ರಯತ್ನಿಸೋಣ", "voice_error": "ಧ್ವನಿ ಲಭ್ಯವಿಲ್ಲ. ನಿಮ್ಮ ಪ್ರಶ್ನೆಯನ್ನು ಬರೆಯಿರಿ ಅಥವಾ ಮತ್ತೆ ಮಾತನಾಡಿ.",
        "page_error": "ನಿಮಗೆ ಸಹಾಯ ಬೇಕಿರುವ ಪುಟವನ್ನು ತೆರೆಯಿರಿ.", "stop": "ನಿಲ್ಲಿಸಿ", "skip": "ಬಿಟ್ಟುಬಿಡಿ", "ask": "ಕೇಳಿ",
        "stopped": "ನಿಲ್ಲಿಸಲಾಗಿದೆ.", "speech_failed": "ಧ್ವನಿ ಲಭ್ಯವಿಲ್ಲ. ಮೇಲಿನ ಸೂಚನೆಯನ್ನು ಓದಿ.",
    },
}
LANGUAGES = tuple(WORDS)


def position(view, x, y, w, h):
    view.setFrame_(((x, y), (w, h)))


class PaperPanel(NSObject):
    def initWithOwner_(self, owner):
        self = objc.super(PaperPanel, self).init()
        self.owner = owner
        self.lang = owner.lang
        self.state = PanelState("idle")
        self.voice_phase = None
        self.details = False
        self.current_decision = None
        self.heard_text = ""
        self.speech_failed = False
        screen = A.NSScreen.mainScreen().visibleFrame()
        self.width = min(430, screen.size.width - 16)
        rect = ((A.NSMaxX(screen) - self.width - 16, A.NSMaxY(screen) - 420), (self.width, 400))
        flags = A.NSWindowStyleMaskBorderless | A.NSWindowStyleMaskNonactivatingPanel
        self.window = PaperPanelWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            rect, flags, A.NSBackingStoreBuffered, False)
        self.window.setTitle_("Companion")
        self.window.setFloatingPanel_(True)
        self.window.setLevel_(A.NSFloatingWindowLevel)
        self.window.setHidesOnDeactivate_(False)
        self.window.setBecomesKeyOnlyIfNeeded_(True)
        self.window.setMovableByWindowBackground_(True)
        self.window.setOpaque_(False)
        self.window.setBackgroundColor_(A.NSColor.clearColor())
        self.window.setHasShadow_(True)
        self.window.setReleasedWhenClosed_(False)
        self.window.setCollectionBehavior_(A.NSWindowCollectionBehaviorCanJoinAllSpaces |
                                           A.NSWindowCollectionBehaviorFullScreenAuxiliary)
        self.window.setAppearance_(A.NSAppearance.appearanceNamed_(A.NSAppearanceNameAqua))
        self.root = PaperSurface.alloc().initWithFrame_(((0, 0), (self.width, 400)))
        self.root.ticket = self.root.field_box = self.root.badge = self.root.chip_box = None
        self.window.setContentView_(self.root)
        self.make_controls()
        self.render()
        A.NSWorkspace.sharedWorkspace().notificationCenter().addObserver_selector_name_object_(
            self, "motionChanged:", A.NSWorkspaceAccessibilityDisplayOptionsDidChangeNotification, None)
        return self

    @objc.python_method
    def make_controls(self):
        t = WORDS[self.lang]
        # The question is the only editable field and the first AXTextField.
        self.field = A.NSTextField.alloc().initWithFrame_(A.NSZeroRect)
        self.field.setBordered_(False)
        self.field.setDrawsBackground_(False)
        self.field.setFont_(hand(17))
        self.field.setTextColor_(INK)
        self.field.setTarget_(self.owner)
        self.field.setAction_("ask:")
        self.field.setAccessibilityIdentifier_("companion-field")
        self.root.addSubview_(self.field)
        self.lang_switch = LanguagePills.segmentedControlWithLabels_trackingMode_target_action_(
            [WORDS[lang]["language"] for lang in LANGUAGES],
            A.NSSegmentSwitchTrackingSelectOne, self.owner, "langChanged:")
        self.lang_switch.setAccessibilityIdentifier_("companion-lang")
        self.root.addSubview_(self.lang_switch)

        def button(title, action, name, kind, target=None):
            view = PaperButton.alloc().initWithFrame_(A.NSZeroRect)
            view.kind = kind
            view.glyph = None
            view.setBordered_(False)
            view.setButtonType_(A.NSButtonTypeMomentaryPushIn)
            view.setTitle_(title)
            view.setTarget_(target if target is not None else self.owner)
            view.setAction_(action)
            view.setAccessibilityIdentifier_("companion-" + name)
            self.root.addSubview_(view)
            return view

        self.ask_button = button(t["ask"], "ask:", "ask", "flat")
        self.ask_button.setKeyEquivalent_("\r")
        self.mic_button = button(t["speak"], "mic:", "mic", "mic")
        self.mic_button.setEnabled_(self.owner.voice is not None)
        self.stop_button = button(t["stop"], "stop:", "stop", "flat")
        self.skip_button = button(t["skip"], "skip:", "skip", "flat")
        self.more = button(t["details"], "toggleDetails:", "details", "more", self)
        self.more.glyph = "ellipsis"
        self.replay = button(t["replay"], "replayStep:", "replay", "replay", self)
        self.replay.glyph = "speaker.wave.2"
        self.new = button(t["new"], "newQuestion:", "new", "primary", self)

        def label(name):
            view = A.NSTextField.wrappingLabelWithString_("")
            view.setSelectable_(False)
            view.setAccessibilityIdentifier_("companion-" + name)
            self.root.addSubview_(view)
            return view

        self.heard = label("heard")
        self.instruction = label("instruction")
        self.caption = label("caption")
        self.on_screen = label("on-screen")
        self.chip = label("target")
        self.feedback = label("voice-feedback")
        self.status = label("debug")
        self.status.setFont_(A.NSFont.systemFontOfSize_(13))
        self.status.setTextColor_(MUTED)
        self.status.setStringValue_(f"planner: {self.owner.planner.name} · pointer: {self.owner.overlay_kind}")
        self.scroll = A.NSScrollView.alloc().initWithFrame_(A.NSZeroRect)
        self.scroll.setDrawsBackground_(False)
        self.scroll.setAutohidesScrollers_(True)
        self.scroll.setHasVerticalScroller_(True)
        self.scroll.setScrollerStyle_(A.NSScrollerStyleOverlay)
        self.scroll.setDocumentView_(self.instruction)
        self.root.addSubview_(self.scroll)
        self.meter = PanelActivityIndicator.alloc().initWithFrame_(A.NSZeroRect)
        self.meter.setWantsLayer_(True)
        self.meter.setAccessibilityElement_(False)
        self.root.addSubview_positioned_relativeTo_(self.meter, A.NSWindowBelow, self.mic_button)
        self.window.setInitialFirstResponder_(self.field)
        self.window.setAccessibilityIdentifier_("companion-state")

    @objc.python_method
    def set_state(self, event, *, ml="", en="", target="", decision=None, heard=None):
        previous = (self.lang, self.state, self.voice_phase, self.heard_text, self.speech_failed)
        self.lang = self.owner.lang
        if event in ("listening", "transcribing"):
            self.voice_phase = event
        elif event == "decision":
            mode = {"complete": "done", "unsupported": "error"}.get(decision.kind, "guiding")
            new_state = PanelState(mode, decision.instruction, decision.instruction_en, target)
            if self.state != new_state:
                self.speech_failed = False
            self.current_decision = decision
            self.state = new_state
        elif event == "language":
            pass  # The current state carries both translations.
        elif event == "voice_error" and self.state.name in ("guiding", "done"):
            self.voice_phase = None
            self.speech_failed = True
        elif event == "question":
            self.speech_failed = False
            self.heard_text = heard or ""
            if not self.owner.recording:
                self.voice_phase = None
            self.current_decision = None
            self.state = PanelState("thinking")
        else:
            self.speech_failed = False
            if event in ("idle", "voice_error"):
                self.voice_phase = None
            self.current_decision = decision
            self.state = PanelState(event, ml, en, target)
        if event == "thinking" or previous != (self.lang, self.state, self.voice_phase, self.heard_text, self.speech_failed):
            self.render()

    def replayStep_(self, sender):
        if self.current_decision is not None and self.state.name == "guiding":
            self.owner.last_spoken = None
            self.owner.speak(self.current_decision)

    def newQuestion_(self, sender):
        self.owner.last_decision = None
        self.field.setStringValue_("")
        self.set_state("idle")

    def toggleDetails_(self, sender):
        self.details = not self.details
        self.render()

    def motionChanged_(self, notification):
        self.meter.update_motion(A.NSWorkspace.sharedWorkspace().accessibilityDisplayShouldReduceMotion())

    @objc.python_method
    def render(self):
        t = WORDS[self.lang]
        state = self.state
        mode = self.voice_phase or state.name
        message = state.ml if self.lang == "ml" else state.en or state.ml
        if self.current_decision is not None and self.lang in ("hi", "kn"):
            message = self.owner.text_for(self.current_decision)
        elif state.name == "idle" and state.en == WORDS["en"]["stopped"]:
            message = t["stopped"]
        w = self.width
        left, inner = 24, w - 48
        center = w / 2
        frame = self.window.frame()
        screen = (self.window.screen() or A.NSScreen.mainScreen()).visibleFrame()
        max_height = screen.size.height - 16
        self.root.ticket = self.root.badge = self.root.chip_box = None
        for view in (self.skip_button, self.stop_button, self.mic_button, self.heard, self.caption,
                     self.replay, self.new, self.chip, self.meter, self.on_screen, self.feedback):
            view.setHidden_(True)

        def show(view, x, y, width, height):
            position(view, x, y, width, height)
            view.setHidden_(False)

        def caption(text, y, centered=False):
            value = text_style(text, 16, ink=MUTED, system=True, center=centered)
            self.caption.setAttributedStringValue_(value)
            h = text_height(value, inner - 4)
            show(self.caption, left, y, inner, h)
            return y + h

        def instruction(text, x, y, width, cap, *, centered=False, size=27):
            value = text_style(text, size, center=centered, leading=ceil(size * 1.5))
            h = text_height(value, width - 6)
            visible = min(h, max(54, cap))
            self.instruction.setAttributedStringValue_(value)
            self.instruction.setPreferredMaxLayoutWidth_(width)
            position(self.scroll, x, y, width, visible)
            position(self.instruction, 0, 0, width, h)
            self.instruction.scrollRectToVisible_(((0, 0), (1, 1)))
            return y + visible

        def mic(y, diameter):
            show(self.mic_button, center - diameter / 2, y, diameter, diameter)

        self.field.setPlaceholderAttributedString_(text_style(t["type"], 16, ink=MUTED, system=True))
        self.field.setAccessibilityLabel_(t["type"])
        self.ask_button.setTitle_(t["ask"])
        self.ask_button.setAccessibilityTitle_(t["ask"] if self.lang == "ml" else "Ask")
        self.stop_button.setTitle_(t["stop"])
        self.skip_button.setTitle_(t["skip"])
        self.replay.setTitle_(t["replay"])
        self.replay.setToolTip_(t["replay"])
        self.more.setTitle_(t["details"])
        self.more.setToolTip_(t["details"])
        self.new.setTitle_(t["new"])
        self.mic_button.glyph = "stop.fill" if mode == "listening" else "mic.fill"
        self.mic_button.setAccessibilityLabel_(t["finish"] if mode == "listening" else t["speak"])
        switch_width = min(304, w - left - 76)
        for i in range(len(LANGUAGES)):
            self.lang_switch.setWidth_forSegment_((switch_width - 4) / len(LANGUAGES), i)
        position(self.lang_switch, left, 20, switch_width, 34)
        self.lang_switch.setSelectedSegment_(LANGUAGES.index(self.lang))
        self.lang_switch.setEnabled_(not self.voice_phase)
        position(self.more, w - 66, 16, 44, 42)
        public_state = {"voice_error": "error", "page_error": "error", "question_error": "error",
                        "transcribing": "thinking"}.get(mode, mode)
        self.window.setAccessibilityValue_(public_state)
        self.window.setAccessibilityHelp_(mode)
        self.meter.mode = public_state
        stop_width = (inner - 76) / 2
        stop_x = left + inner - stop_width
        y = 86
        if mode == "guiding":
            if self.heard_text:
                self.heard.setAttributedStringValue_(text_style(f'{t["heard"]}: “{self.heard_text}”',
                                                                 14, ink=MUTED, system=True))
                self.heard.cell().setLineBreakMode_(A.NSLineBreakByTruncatingTail)
                show(self.heard, left, y, inner, 21)
                y += 34
            top = y
            self.replay.setEnabled_(self.owner.voice is not None and not self.owner.mute)
            show(self.replay, w - left - 53, y + 10, 44, 44)
            y = instruction(message, left + 15, y + 14, inner - 74,
                            max_height - y - (275 if self.details else 231))
            y = max(y, top + 52)
            if state.target:
                prefix = text_style(t["screen"], 14, ink=MUTED, system=True)
                self.on_screen.setAttributedStringValue_(prefix)
                prefix_w = ceil(prefix.size().width) + 6
                show(self.on_screen, left + 15, y + 12, prefix_w, 21)
                chip = text_style(state.target, 15, ink=INK, system=True)
                self.chip.setAttributedStringValue_(chip)
                self.chip.setDrawsBackground_(False)
                self.chip.cell().setLineBreakMode_(A.NSLineBreakByTruncatingTail)
                self.chip.setToolTip_(state.target)
                chip_x = left + 21 + prefix_w
                chip_w = min(left + inner - chip_x - 16, ceil(chip.size().width) + 19)
                self.root.chip_box = (chip_x, y + 7, chip_w, 27)
                show(self.chip, chip_x + 7, y + 11, chip_w - 12, 23)
                y += 36
            y += 14
            self.root.ticket = (left, top, inner, y - top)
            y += 14
            show(self.mic_button, left, y, 56, 56)
            show(self.skip_button, left + 66, y + 3, stop_width, 50)
            show(self.stop_button, stop_x, y + 3, stop_width, 50)
            y += 70
        elif mode == "listening":
            show(self.meter, center - 70, y, 140, 191)
            mic(y + 18, 96)
            y = instruction(t["listen"], left, y + 201, inner, 100, centered=True)
            y = caption(t["finish"], y, True) + 20
        elif mode in ("thinking", "transcribing"):
            show(self.meter, center - 30, y + 9, 60, 22)
            y = instruction(t["think"], left, y + 40, inner, 125, centered=True)
            if mode == "thinking" and self.owner.active:
                show(self.stop_button, stop_x, y + 12, stop_width, 50)
                y += 62
            y += 14
        elif mode == "done":
            self.root.badge = (center, y + 39)
            y = instruction(message, left, y + 90, inner, max_height - 340, centered=True)
            show(self.new, left, y + 16, inner, 56)
            y += 86
        elif public_state == "error":
            y = instruction(t["again"], left, y, inner, 100)
            body = t.get(mode, message)
            value = text_style(body, 18, ink=MUTED)
            self.caption.setAttributedStringValue_(value)
            h = min(text_height(value, inner - 4), max_height - 310)
            show(self.caption, left, y + 6, inner, h)
            y += h + 24
            mic(y, 64)
            y += 78
        else:
            y = instruction(t["prompt"], left, y, inner, 120)
            y = caption(message or t["intro"], y + 2)
            mic(y + 17, 96)
            value = text_style(t["speak"], 18, center=True)
            # The mic caption doubles as its visible action label.
            self.chip.setDrawsBackground_(False)
            self.chip.setToolTip_(None)
            self.chip.setAttributedStringValue_(value)
            show(self.chip, left, y + 120, inner, 30)
            y += 164

        if self.speech_failed:
            value = text_style(t["speech_failed"], 14, ink=MUTED, system=True)
            self.feedback.setAttributedStringValue_(value)
            h = text_height(value, inner - 4)
            show(self.feedback, left, y, inner, h)
            y += h + 7
        field_w = inner - 110
        self.root.field_box = (left, y, field_w, 44)
        position(self.field, left + 11, y + 10, field_w - 22, 26)
        position(self.ask_button, left + field_w + 8, y, 102, 44)
        y += 44
        self.status.setHidden_(not self.details)
        if self.details:
            position(self.status, left, y + 9, inner, 46)
            y += 55
        height = ceil(y + 23)
        # Anchor the top of the note where the person dragged it.
        origin_y = max(A.NSMinY(screen), min(A.NSMaxY(frame), A.NSMaxY(screen)) - height)
        self.window.setFrame_display_(((frame.origin.x, origin_y), (w, height)), False)
        self.root.setNeedsDisplay_(True)
        self.motionChanged_(None)
