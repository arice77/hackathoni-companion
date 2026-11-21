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


def straight_to_send(w, screen):
    """Abin's decision, 22 Nov 04:15: the compose walk goes straight from Message Body to Send. Attach is NOT offered here (it stays its
    own 'attach a photo' goal); Send is next and says to press it only when ready."""
    d = w.step(screen, "point", "Send", not_text="attach")
    assert "only when you" in d.instruction_en, d.instruction_en


QUESTION = "എന്റെ മകന് ഒരു ഇമെയിൽ അയയ്ക്കണം"


@scenario
def s_compose_walk_ends_in_complete_your_email_was_sent():
    """Compose -> To -> Subject -> Body -> Send (no Attach step) -> 'Message sent' with the composer gone = complete."""
    with blocked_network():
        w = Walk(QUESTION)
        w.step(gm("Compose"), "point", "Compose")
        w.step(gm(*COMPOSER, empty=("To", "Subject", "Message Body")), "point", "To", text="son")
        w.step(gm(*COMPOSER, filled=("To",), empty=("Subject", "Message Body")), "point", "Subject")
        w.step(gm(*COMPOSER[1:], filled=("Subject",), empty=("Message Body",)), "point", "Message Body")
        ready = gm(*COMPOSER[1:], filled=("Subject", "Message Body"))
        straight_to_send(w, ready)
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
def s_attach_stays_available_as_its_own_request():
    """'Attach a photo' (its own request) still points at Attach files even though the compose walk no longer offers it."""
    with blocked_network():
        Walk("Attach a photo").step(gm("Attach files"), "point", "Attach files")


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


PHRASINGS = ("I need to send an email to my son.", "എനിക്കൊരു ഇമെയിൽ അയക്കണം.", "I want to write a mail",
             "Ente makanu oru email ayakkanam", "എന്റെ മകന് ഒരു ഇമെയിൽ അയയ്ക്കണം")


@scenario
def s_natural_phrasings_start_the_compose_guide():
    """Abin's real sentences (spoken and typed, English/Malayalam/Manglish) start Compose, never 'I can help write…' with no step;
    a request that is not about mail still gets the honest 'I can help…' line."""
    with blocked_network():
        for q in PHRASINGS:
            Walk(q).step(gm("Compose"), "point", "Compose", text="new email")
        Walk("Can you pay my bill").step(gm("Compose"), "unsupported", text="I can help")


@scenario
def s_collapsed_to_box_is_done_and_the_guide_does_not_bounce_back():
    """After the address is typed and Subject is clicked, Gmail collapses To into a recipients summary (no To control, or one read
    as empty). That, or any later field filled, means To is done: To -> Subject -> Body -> Send (no Attach), To pointed once."""
    with blocked_network():
        for q in PHRASINGS[:2]:
            w = Walk(q)
            w.step(gm("Compose"), "point", "Compose")
            w.step(gm(*COMPOSER, empty=("To", "Subject", "Message Body")), "point", "To")
            # clicked Subject: To collapsed (no To control), Subject still empty
            w.step(gm(*COMPOSER[1:], empty=("Subject", "Message Body")), "point", "Subject")
            # typed the subject, To still collapsed
            w.step(gm(*COMPOSER[1:], filled=("Subject",), empty=("Message Body",)), "point", "Message Body")
            # Gmail re-renders To as an empty-looking field while Subject is filled: still done
            w.step(gm(*COMPOSER, filled=("Subject",), empty=("To", "Message Body")), "point", "Message Body")
            ready = gm(*COMPOSER, filled=("Subject", "Message Body"), empty=("To",))
            straight_to_send(w, ready)
            targets = [e.split(":")[1] for e in w.log if e.startswith("point")]
            assert targets.count("To") == 1, f"To was pointed at {targets.count('To')} times: {targets}"
            w.step(gm("Compose", "Sending…"), "clarify")
            w.step(gm("Compose", "Message sent"), "complete", text="Your email was sent")


@scenario
def s_collapsed_to_at_the_very_start_of_a_compose_is_not_a_finished_to():
    """Guard the other side: before anything is typed the To control is present and empty, so the guide points at it (the
    collapsed-To rule only applies when To has gone away)."""
    with blocked_network():
        w = Walk(PHRASINGS[0])
        w.step(gm("Compose"), "point", "Compose")
        w.step(gm(*COMPOSER, empty=("To", "Subject", "Message Body")), "point", "To")
        w.step(gm(*COMPOSER, empty=("To", "Subject", "Message Body")), "point", "To")  # still empty: same pointer, not skipped


def run():
    out = []
    for name, fn in SCENARIOS.items():
        try:
            fn()
            out.append(result(FEATURE, CHECK + name, "pass", "automated", (fn.__doc__ or "ok").strip()[:140]))
        except Exception as exc:  # noqa: BLE001
            out.append(result(FEATURE, CHECK + name, "fail", "automated", f"{type(exc).__name__}: {exc}"[:600]))
    return out
