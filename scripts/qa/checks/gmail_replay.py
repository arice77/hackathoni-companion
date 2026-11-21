"""Gmail regression replays (offline): compose -> Send -> complete, reply on a Sent conversation, search. No Safari, no Sarvam.

Synthetic gated Gmail states (fixed chrome names only, `filled` flags, the "Message sent" notice) go through the real
SarvamPlanner with the network blocked. Live coverage is gmail_follow_pointer_e2e.py (one real send to the allowlisted address).
The privacy contract is asserted here too: the decision text never contains the typed question's address or number.
"""
from _common import result
from _replay import Walk, blocked_network, snap, C

FEATURE = "web-support"
CHECK = "gmail replay: "
HOST = "mail.google.com"
STEP = {"Compose": "AXButton", "Reply": "AXButton", "To": "AXComboBox", "Subject": "AXTextField", "Message Body": "AXTextArea",
        "Attach files": "AXPopUpButton", "Send": "AXButton", "Search mail": "AXTextField"}
NOTICE = {"Open email", "Message sent", "Sending…"}


def gm(*labels, filled=(), empty=()):
    """A gated Gmail screen: buttons/fields by name (filled flag when the field state is known), notices as static text."""
    out = []
    for i, label in enumerate(labels):
        if label in NOTICE:
            out.append(C(label, "AXStaticText", label, (10, 30 + 30 * i, 180, 20), enabled=False))
        else:
            out.append(C(label, STEP[label], label, (10, 30 + 30 * i, 180, 20),
                         filled=True if label in filled else False if label in empty else None))
    return snap(out, host=HOST)


COMPOSER = ("To", "Subject", "Message Body", "Attach files", "Send")
SCENARIOS = {}


def scenario(fn):
    SCENARIOS[fn.__name__.removeprefix("s_").replace("_", " ")] = fn
    return fn


QUESTION = "എന്റെ മകന് ഒരു ഇമെയിൽ അയയ്ക്കണം"


@scenario
def s_compose_walk_ends_in_complete_your_email_was_sent():
    """Compose -> To -> Subject -> Body -> (optional Attach, skipped) -> Send -> 'Message sent' with the composer gone = complete."""
    with blocked_network():
        w = Walk(QUESTION)
        w.step(gm("Compose"), "point", "Compose")
        w.step(gm(*COMPOSER, empty=("To", "Subject", "Message Body")), "point", "To", text="son")
        w.step(gm(*COMPOSER, filled=("To",), empty=("Subject", "Message Body")), "point", "Subject")
        w.step(gm(*COMPOSER[1:], filled=("Subject",), empty=("Message Body",)), "point", "Message Body")
        ready = gm(*COMPOSER[1:], filled=("Subject", "Message Body"))
        w.step(ready, "point", "Attach files", text="skip")
        assert w.pl.skip_current(), "the panel's Skip did not reach the Gmail guide"
        w.step(ready, "point", "Send", text="only when you")
        w.step(gm("Compose", "Sending…"), "clarify")  # sent, not yet confirmed
        d = w.step(gm("Compose", "Message sent"), "complete", text="Your email was sent")
        assert d.instruction, "no Malayalam completion line"


@scenario
def s_vanished_composer_without_the_notice_is_not_a_claimed_send():
    """The draft disappearing (discarded, closed) is NOT proof of sending: no 'Your email was sent' without the notice."""
    with blocked_network():
        w = Walk(QUESTION)
        w.step(gm("Compose"), "point", "Compose")
        w.step(gm(*COMPOSER, empty=("To", "Subject", "Message Body")), "point", "To")
        d = w.step(gm("Compose"), "clarify", text="can’t confirm")
        assert "was sent" not in d.instruction_en.replace("whether it was sent", "")


@scenario
def s_message_sent_notice_alone_does_not_end_a_new_draft():
    """A stale 'Message sent' toast while a new composer is open must not complete the walk."""
    with blocked_network():
        w = Walk(QUESTION)
        w.step(gm("Compose", "Message sent"), "point", "Compose")
        w.step(gm(*COMPOSER, "Message sent", empty=("To", "Subject", "Message Body")), "point", "To")


@scenario
def s_reply_on_a_sent_conversation():
    """Reply: Open email + Reply -> point Reply; the reply composer asks for the body only, then Send, then complete."""
    with blocked_network():
        w = Walk("Reply to this email")
        w.step(gm("Open email", "Reply"), "point", "Reply")
        reply = ("Message Body", "Send")
        w.step(gm("Open email", *reply, empty=("Message Body",)), "point", "Message Body")
        w.step(gm("Open email", *reply, filled=("Message Body",)), "point", "Send", text="only when you")
        w.step(gm("Open email", "Reply", "Message sent"), "complete", text="Your email was sent")
        # no open conversation: ask the person to open one (the companion never opens mail itself)
        d = Walk("Reply to this email").step(gm("Compose"), "clarify", text="Open the email")
        # a NEW draft is not a reply
        Walk("Reply to this email").step(gm("Open email", *COMPOSER, "Reply"), "clarify", text="new email draft")


@scenario
def s_search_points_at_search_mail():
    with blocked_network():
        Walk("Find an email").step(gm("Compose", "Search mail"), "point", "Search mail", text="Enter")
        Walk("മെയിൽ എങ്ങനെ തിരയാം").step(gm("Search mail"), "point", "Search mail")


@scenario
def s_private_question_text_never_reaches_a_decision():
    """An address or number in the question is redacted before the guide: it never appears in any decision text."""
    with blocked_network():
        w = Walk("I want to send an email")  # the goal phrase; privacy filter must keep it recognisable
        w.step(gm("Compose"), "point", "Compose")
        from companion.sites.gmail import PACK
        red = PACK.privacy.filter_question("Send it to my.son@example.invalid or call 9847012345")
        assert "my.son@example.invalid" not in red and "9847012345" not in red, red


def run():
    out = []
    for name, fn in SCENARIOS.items():
        try:
            fn()
            out.append(result(FEATURE, CHECK + name, "pass", "automated", (fn.__doc__ or "ok").strip()[:140]))
        except Exception as exc:  # noqa: BLE001
            out.append(result(FEATURE, CHECK + name, "fail", "automated", f"{type(exc).__name__}: {exc}"[:600]))
    return out
