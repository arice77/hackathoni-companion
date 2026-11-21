"""Local Malayalam-first guidance for Gmail's gated Accessibility chrome."""

from __future__ import annotations

import re
from dataclasses import replace
from threading import Lock

from ..contracts import Decision, Snapshot
from . import PrivacyProfile, SiteGoal, SitePack, SiteStep, _phrase

HOST = "mail.google.com"

COMPOSE = SiteStep("AXButton", "Compose", "പുതിയ ഇമെയിൽ എഴുതാൻ ‘Compose’ അമർത്തൂ.",
                   "Click ‘Compose’ to write a new email.", action=True)
TO = SiteStep("AXComboBox", "To", "ആർക്കാണ് അയയ്ക്കേണ്ടത്? ‘To’ എന്നിടത്ത് അവരുടെ ഇമെയിൽ വിലാസം ടൈപ്പ് ചെയ്യൂ. "
              "ഉദാഹരണത്തിന്, നിങ്ങളുടെ മകന്റെ ഇമെയിൽ വിലാസം. എന്നിട്ട് Enter അമർത്തൂ.",
              "In ‘To’, type the recipient’s email address, for example your son’s email. Then press Enter.")
SUBJECT = SiteStep("AXTextField", "Subject", "ഇമെയിൽ എന്തിനെക്കുറിച്ചാണെന്ന് ‘Subject’ എന്നിടത്ത് ചുരുക്കി എഴുതൂ.",
                   "In ‘Subject’, write a short title for the email.")
BODY = SiteStep("AXTextArea", "Message Body", "പറയാനുള്ളത് ‘Message Body’ എന്ന വലിയ ബോക്സിൽ എഴുതൂ.",
                "Write what you want to say in the large ‘Message Body’ box.")
ATTACH = SiteStep("AXPopUpButton", "Attach files", "ഫോട്ടോ ചേർക്കാൻ ‘Attach files’ അമർത്തൂ. "
                  "തുറക്കുന്ന വിൻഡോയിൽ ഫോട്ടോ തിരഞ്ഞെടുത്ത് ‘Open’ അമർത്തൂ.",
                  "Click ‘Attach files’. In the window that opens, choose the photo and click ‘Open’.", action=True)
SEND = SiteStep("AXButton", "Send", "ഇമെയിൽ വിലാസവും എഴുതിയതും ഒന്ന് നോക്കൂ. "
                "അയയ്ക്കാൻ തയ്യാറാണെങ്കിൽ ‘Send’ നിങ്ങൾ തന്നെ അമർത്തൂ.",
                "Check the email address and what you wrote. Click ‘Send’ only when you’re ready.", action=True)
REPLY = SiteStep("AXButton", "Reply", "ഈ ഇമെയിലിന് മറുപടി എഴുതാൻ ‘Reply’ അമർത്തൂ.",
                 "Click ‘Reply’ to write back to this email.", action=True)
SEARCH_ROLES = ("AXTextField", "AXComboBox", "AXSearchField")
SEARCH = SiteStep(SEARCH_ROLES[0], "Search mail", "‘Search mail’ എന്നിടത്ത് ഓർമ്മയുള്ള പേരോ വാക്കോ ടൈപ്പ് ചെയ്യൂ. "
                  "എന്നിട്ട് Enter അമർത്തൂ.",
                  "Type a name or a word you remember into ‘Search mail’, then press Enter.")

PRIVATE_QUESTION = re.compile(
    r"[\w.!#$%&'*+/=?^_`{|}~-]+@[\w-]+(?:\.[\w-]+)+"
    r"|(?<!\d)\+?(?:\(\d+\)[ .-]*)?\d+(?:[ .()/:\u00a0\u2010-\u2015-]+\d+)*(?!\d)",
)
_STEPS = (TO, SUBJECT, BODY, ATTACH, SEND)
_CHROME = {
    (role, _phrase(label)): label for role, label in (
        *((step.role, step.label) for step in (COMPOSE, REPLY, *_STEPS)),
        *((role, "Search mail") for role in SEARCH_ROLES),
        *(("AXLink", name) for name in ("Inbox", "Sent", "Drafts", "Starred", "Snoozed")),
        *(("AXStaticText", name) for name in ("Open email", "Message sent", "Sending…", "Undo")),
        *((role, "Undo") for role in ("AXButton", "AXLink", "AXMenuButton", "AXPopUpButton")),
        ("AXButton", "Back"),
    )
}


class GmailPrivacy(PrivacyProfile):
    def filter_snapshot(self, snap: Snapshot) -> Snapshot:
        filtered = super().filter_snapshot(snap)
        return replace(filtered, window_title=HOST, controls=tuple(
            replace(control, label=_CHROME[(control.role, _phrase(control.label))], identifier=None, group=None)
            for control in filtered.controls
        ))


_MAIL_WORDS = re.compile(r"\b(?:e-?mail|mail|gmail|message|letter)\b|ഇമെയിൽ|ഈമെയിൽ|ഇ-മെയിൽ|മെയിൽ|മെയില്|കത്ത്|സന്ദേശം")
_COMPOSE_WORDS = re.compile(r"\b(?:send|write|compose|new|draft|ayakk\w*|ayakkanam|ezhuth\w*)\b|അയ|എഴുത")
_REPLY_WORDS = re.compile(r"\brepl(?:y|ies|ying)\b|\banswer\b|മറുപടി")
_SEARCH_WORDS = re.compile(r"\b(?:find|search|look for|where is|kandupidi\w*)\b|കണ്ടെത്ത|കണ്ടുപിടി|തിരയ")
_ATTACH_WORDS = re.compile(r"\b(?:attach\w*|photo|picture|image|cherkk\w*)\b|ഫോട്ടോ|ചിത്രം|ചേർക്ക")


class GmailPack(SitePack):
    provider_goal = "Guide the visible Gmail controls. Never infer or reveal message content."

    def is_practice(self, snap: Snapshot) -> bool:
        return False

    def goal_for(self, question: str) -> SiteGoal | None:
        goal = super().goal_for(question)
        if goal is not None:
            return goal
        # Live test 22 Nov 04:05: real speech ("I need to send an email to my son.", "എനിക്കൊരു ഇമെയിൽ അയക്കണം",
        # "I want to write a mail") missed the exact phrase list. Fall back to keywords on both halves.
        text = " ".join(_phrase(part) for part in question.split(" / ", 1))
        mail = bool(_MAIL_WORDS.search(text))
        name = None
        if _REPLY_WORDS.search(text):
            name = "reply"
        elif mail and _SEARCH_WORDS.search(text):
            name = "search"
        elif mail and _COMPOSE_WORDS.search(text):
            name = "compose"
        elif _ATTACH_WORDS.search(text):
            name = "attach"
        return next((g for g in self.goals if g.name == name), None)

    def start_guidance(self, question: str) -> GmailGuide:
        goal = self.goal_for(self.privacy.filter_question(question))
        return GmailGuide(goal.name if goal else None)


PACK = GmailPack(
    name="Gmail", hosts=frozenset({HOST}), practice_heading="", practice_result="",
    entry=COMPOSE, steps=_STEPS, privacy=GmailPrivacy(frozenset(_CHROME), PRIVATE_QUESTION),
    goals=(
        SiteGoal("compose", (
            "How do I write a new email", "Help me write an email", "I want to send an email", "Write an email",
            "പുതിയ ഇമെയിൽ എങ്ങനെ എഴുതാം", "എനിക്ക് ഒരു ഇമെയിൽ അയയ്ക്കണം", "പുതിയ മെയിൽ എഴുതണം",
            "എന്റെ മകന് ഒരു ഇമെയിൽ അയയ്ക്കണം",
            "Puthiya email engane ezhutham", "Oru mail ayakkanam", "Mail engane ayakkam",
        )),
        SiteGoal("reply", (
            "How do I reply to this email", "Reply to this email", "I want to reply to this email",
            "ഈ ഇമെയിലിന് എങ്ങനെ മറുപടി അയയ്ക്കാം", "ഈ മെയിലിന് മറുപടി എഴുതണം", "മറുപടി എങ്ങനെ എഴുതാം",
            "Ee mailinu engane reply cheyyam", "Reply engane cheyyam",
        )),
        SiteGoal("search", (
            "How do I find an email", "Find an email", "How do I search my email", "Search my mail",
            "ഇമെയിൽ എങ്ങനെ കണ്ടെത്താം", "ഒരു മെയിൽ കണ്ടെത്തണം", "മെയിൽ എങ്ങനെ തിരയാം",
            "Oru mail engane kandupidikkam", "Mail engane search cheyyam",
        ), SEARCH),
        SiteGoal("attach", (
            "How do I attach a photo", "Attach a photo", "I want to attach a photo",
            "ഫോട്ടോ എങ്ങനെ ചേർക്കാം", "ഒരു ഫോട്ടോ ചേർക്കണം", "ഫോട്ടോ എങ്ങനെ അയയ്ക്കാം",
            "Photo engane attach cheyyam", "Oru photo cherkkam",
        ), ATTACH),
    ),
)

_NEXT = {"next", "done", "അടുത്തത്", "കഴിഞ്ഞു", "adutha", "aduthathu"}
_SKIP = {"skip", "no", "ഒഴിവാക്കൂ", "വേണ്ട", "venda"}


class GmailGuide:
    """One local session. Unknown field state advances only on a new, explicit acknowledgement."""

    def __init__(self, goal: str | None) -> None:
        self._goal = goal
        self._lock = Lock()
        self._current: SiteStep | None = None
        self._acknowledgement: SiteStep | None = None
        self._pending: SiteStep | None = None
        self._confirmed: set[SiteStep] = set()
        self._saw_editor = False
        self._sent_notice_after_editor: bool | None = None

    @staticmethod
    def _note(snap: Snapshot, ml: str, en: str, *, unsupported: bool = False) -> Decision:
        return Decision("unsupported" if unsupported else "clarify", snap.snapshot_id, ml, en, source="sarvam")

    def _point(self, snap: Snapshot, step: SiteStep, *, acknowledge: bool = False,
               optional: bool = False) -> Decision:
        target = step.target(snap)
        if target is None:
            return self._note(snap, "ആ ബോക്സ് ഇപ്പോൾ കാണുന്നില്ല. അത് കാണുന്ന പേജ് തുറക്കൂ.",
                              "I can’t see that control. Open the screen where it appears.")
        self._current = step
        self._acknowledgement = step if acknowledge and target.filled is None else None
        decision = step.point(snap, target)
        if optional:
            return replace(decision,
                           instruction=decision.instruction + " ഫോട്ടോ വേണ്ടെങ്കിലോ ചേർത്തുകഴിഞ്ഞെങ്കിലോ ‘അടുത്തത്’ എന്ന് പറയൂ.",
                           instruction_en=decision.instruction_en + " Say ‘Next’ after attaching it, or to skip.")
        if acknowledge and target.filled is None:
            return replace(decision, instruction=decision.instruction + " കഴിഞ്ഞാൽ ‘അടുത്തത്’ എന്ന് പറയൂ.",
                           instruction_en=decision.instruction_en + " When you’re done, say ‘Next’.")
        return decision

    def skip_current(self, question: str = "skip") -> bool:
        """Queue one Next or Skip for the control currently being explained."""
        utterances = {_phrase(part) for part in question.split(" / ", 1)}
        next_requested = bool(utterances & _NEXT)
        with self._lock:
            if self._goal == "compose" and self._current == ATTACH and (next_requested or utterances & _SKIP):
                self._pending = ATTACH
                return True
            if next_requested and self._acknowledgement is not None:
                self._pending = self._acknowledgement
                return True
            return False

    def decide(self, snap: Snapshot) -> Decision:
        with self._lock:
            pending, self._pending = self._pending, None
            self._current = self._acknowledgement = None
            return self._decide(snap, pending)

    def _decide(self, snap: Snapshot, pending: SiteStep | None) -> Decision:
        if not PACK.matches(snap):
            return self._note(snap, "Gmail തുറന്നിട്ട് വീണ്ടും ചോദിക്കൂ.", "Open Gmail and ask again.", unsupported=True)
        snap = PACK.privacy.filter_snapshot(snap)
        if self._goal == "search":
            candidates = [replace(SEARCH, role=role) for role in SEARCH_ROLES if replace(SEARCH, role=role).target(snap)]
            if len(candidates) == 1:
                return self._point(snap, candidates[0])
            return self._note(snap, "‘Search mail’ എന്ന് എഴുതിയ ബോക്സ് കാണുന്ന പേജ് തുറക്കൂ.",
                              "Show the page with the ‘Search mail’ field.")
        if self._goal == "attach":
            return self._point(snap, ATTACH)
        if self._goal not in {"compose", "reply"}:
            return self._note(snap, "പുതിയ ഇമെയിൽ എഴുതാനോ, മറുപടി നൽകാനോ, മെയിൽ തിരയാനോ, ഫോട്ടോ ചേർക്കാനോ സഹായിക്കാം.",
                              "I can help write, reply, search for mail, or attach a photo.", unsupported=True)
        notices = {control.label for control in snap.controls if control.role == "AXStaticText"}
        editor = any(step.target(snap) is not None for step in (TO, SUBJECT, BODY, SEND))
        if "Message sent" not in notices:
            self._sent_notice_after_editor = None
        elif self._sent_notice_after_editor is None:
            self._sent_notice_after_editor = self._saw_editor
        if self._sent_notice_after_editor and not editor:
            return Decision("complete", snap.snapshot_id, "ഇമെയിൽ അയച്ചു", "Your email was sent", source="sarvam")
        if self._saw_editor and "Sending…" in notices:
            return self._note(snap, "ഇമെയിൽ അയയ്ക്കുകയാണ്. ഒന്ന് കാത്തിരിക്കൂ.", "Gmail is sending your email. One moment.")
        if self._goal == "reply" and "Open email" not in notices and (editor or not self._saw_editor):
            return self._note(snap, "മറുപടി അയയ്ക്കേണ്ട ഇമെയിൽ നിങ്ങൾ തന്നെ തുറന്നിട്ട് ചോദിക്കൂ.",
                              "Open the email you want to reply to, then ask again.")
        if not editor:
            self._confirmed.clear()
            if self._saw_editor:
                return self._note(snap, "എഴുതിയ ഇമെയിൽ ഇപ്പോൾ കാണുന്നില്ല. അത് അയച്ചോ എന്ന് എനിക്ക് ഉറപ്പിക്കാൻ കഴിയില്ല.",
                                  "The draft is no longer visible. I can’t confirm whether it was sent.")
            return self._point(snap, REPLY if self._goal == "reply" else COMPOSE)
        if self._goal == "reply" and (TO.target(snap) or SUBJECT.target(snap)):
            return self._note(snap, "ഇത് പുതിയ ഇമെയിൽ എഴുതുന്ന ബോക്സാണ്. മറുപടി നൽകേണ്ട മെയിലിലെ ‘Reply’ തുറക്കൂ.",
                              "This is a new email draft. Open ‘Reply’ on the email you want to answer.")
        self._saw_editor = True
        fields = (TO, SUBJECT, BODY) if self._goal == "compose" else (BODY,)
        for index, step in enumerate(fields):
            target = step.target(snap)
            filled = target.filled if target is not None else None
            # Live test 22 Nov 04:10: after the address is typed and focus moves on, Gmail collapses the To box
            # into a recipients summary (hidden or read as empty), so the guide bounced back to To. A collapsed
            # To, or any later field already filled, means the person has moved past it.
            later_filled = any((t := later.target(snap)) is not None and t.filled is True for later in fields[index + 1:])
            collapsed_to = step == TO and target is None
            if filled is False and not later_filled:
                self._confirmed.discard(step)
            elif filled is True or step == pending or later_filled or collapsed_to:
                self._confirmed.add(step)
        if pending == ATTACH:
            self._confirmed.add(ATTACH)
        for step in fields:
            if step not in self._confirmed:
                return self._point(snap, step, acknowledge=True)
        # Abin, 22 Nov 04:15: don't offer Attach inside "write an email"; go from Message Body straight to Send.
        # Attaching stays available as its own request ("attach a photo").
        return self._point(snap, SEND)
