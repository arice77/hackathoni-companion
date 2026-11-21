"""Gmail's local goal replays and privacy contract; no external calls."""

import json
import time
import unittest
from dataclasses import asdict, replace
from unittest.mock import patch

from companion.contracts import Control, Snapshot
from companion.planner_sarvam import SarvamPlanner
from companion.sites import pack_for
from companion.sites.gmail import ATTACH, BODY, COMPOSE, HOST, PACK, REPLY, SEARCH, SEND, SUBJECT, TO
from companion.validator import validate
from companion.voice import sarvam

FRAME = (0, 0, 800, 600)
OPEN_EMAIL = Control("open-email", "AXStaticText", "Open email", FRAME, enabled=False)
MESSAGE_SENT = Control("message-sent", "AXStaticText", "Message sent", FRAME, enabled=False)
SENDING = Control("sending", "AXStaticText", "Sending…", FRAME, enabled=False)
COMPOSE_QUESTION = "എനിക്ക് ഒരു ഇമെയിൽ അയയ്ക്കണം"


def make_screen(*steps, filled=(), empty=(), extra=()):
    controls = tuple(Control(step.label, step.role, step.label, (10, 30 + index * 30, 180, 20),
                             filled=True if step.label in filled else False if step.label in empty else None)
                     for index, step in enumerate(steps))
    return Snapshot("screen", time.time(), "com.apple.Safari", 101, HOST, FRAME, (*controls, *extra), FRAME)


class GmailSiteTests(unittest.TestCase):
    def setUp(self):
        self.guide = PACK.start_guidance(COMPOSE_QUESTION)
        self.post = self.enterContext(patch.object(sarvam, "_post", side_effect=AssertionError("Unexpected provider call")))

    def point(self, snap, step):
        decision = self.guide.decide(snap)
        self.assertEqual(decision.kind, "point")
        self.assertEqual(snap.control(decision.control_id).label, step.label)
        self.assertEqual(validate(decision, snap), (True, "ok"))
        return decision

    def test_registry_and_exact_host_match(self):
        snap = make_screen(COMPOSE)
        self.assertIs(pack_for(snap), PACK)
        self.assertIsNone(pack_for(replace(snap, window_title="mail.google.com.example.test")))
        self.assertIsNone(pack_for(replace(snap, window_title="127.0.0.1")))

    def test_local_eval_phrases_in_malayalam_english_and_manglish(self):
        cases = (
            (("How do I write a new email?", COMPOSE_QUESTION, "എന്റെ മകന് ഒരു ഇമെയിൽ അയയ്ക്കണം",
              "Oru mail ayakkanam"), COMPOSE, make_screen(COMPOSE)),
            (("How do I reply to this email?", "ഈ മെയിലിന് മറുപടി എഴുതണം", "Reply engane cheyyam"), REPLY,
             make_screen(REPLY, extra=(OPEN_EMAIL,))),
            (("Find an email", "മെയിൽ എങ്ങനെ തിരയാം?", "Mail engane search cheyyam"), SEARCH, make_screen(SEARCH)),
            (("Attach a photo", "ഒരു ഫോട്ടോ ചേർക്കണം", "Photo engane attach cheyyam"), ATTACH, make_screen(ATTACH)),
        )
        for utterances, step, snap in cases:
            for question in utterances:
                with self.subTest(question=question):
                    self.guide = PACK.start_guidance(question)
                    self.point(snap, step)
        self.post.assert_not_called()

    def test_compose_walk_uses_filled_flags_and_skips_optional_attachment(self):
        self.point(make_screen(COMPOSE), COMPOSE)
        steps = (TO, SUBJECT, BODY, ATTACH, SEND)
        decision = self.point(make_screen(*steps, empty=("To", "Subject", "Message Body")), TO)
        self.assertIn("son’s email", decision.instruction_en)
        self.assertNotIn("say ‘Next’", decision.instruction_en)
        self.point(make_screen(*steps, filled=("To",), empty=("Subject", "Message Body")), SUBJECT)
        # Gmail can collapse the To input after the user focuses the subject or body.
        self.point(make_screen(*steps[1:], filled=("Subject",), empty=("Message Body",)), BODY)
        ready = make_screen(*steps[1:], filled=("Subject", "Message Body"))
        decision = self.point(ready, ATTACH)
        self.assertIn("Open", decision.instruction_en)
        self.assertIn("skip", decision.instruction_en)
        self.assertTrue(self.guide.skip_current())
        decision = self.point(ready, SEND)
        self.assertIn("only when you’re ready", decision.instruction_en)
        closed = self.guide.decide(make_screen(COMPOSE))
        self.assertEqual((closed.kind, closed.control_id), ("clarify", None))
        self.assertIn("can’t confirm", closed.instruction_en)

    def test_compose_completes_when_the_new_sent_notice_appears(self):
        self.point(make_screen(COMPOSE, extra=(MESSAGE_SENT,)), COMPOSE)
        ready = make_screen(TO, SUBJECT, BODY, SEND, filled=("To", "Subject", "Message Body"))
        self.point(ready, SEND)
        waiting = self.guide.decide(make_screen(COMPOSE, extra=(SENDING,)))
        self.assertEqual(waiting.kind, "clarify")
        self.assertIn("Gmail is sending", waiting.instruction_en)
        confirmed = make_screen(COMPOSE, extra=(MESSAGE_SENT,))
        for _ in range(2):
            complete = self.guide.decide(confirmed)
            self.assertEqual((complete.kind, complete.instruction_en, complete.instruction),
                             ("complete", "Your email was sent", "ഇമെയിൽ അയച്ചു"))
            self.assertEqual(validate(complete, confirmed), (True, "ok"))

    def test_a_notice_present_before_compose_does_not_confirm_this_draft(self):
        self.point(make_screen(COMPOSE, extra=(MESSAGE_SENT,)), COMPOSE)
        self.point(make_screen(TO, SUBJECT, BODY, SEND, filled=("To", "Subject", "Message Body"),
                               extra=(MESSAGE_SENT,)), SEND)
        unchanged = self.guide.decide(make_screen(COMPOSE, extra=(MESSAGE_SENT,)))
        self.assertEqual(unchanged.kind, "clarify")
        self.assertIn("can’t confirm", unchanged.instruction_en)

    def test_reply_completes_if_gmail_returns_to_the_inbox_with_a_sent_notice(self):
        self.guide = PACK.start_guidance("How do I reply to this email?")
        self.point(make_screen(BODY, SEND, filled=("Message Body",), extra=(OPEN_EMAIL,)), SEND)
        self.assertEqual(self.guide.decide(make_screen(COMPOSE, extra=(MESSAGE_SENT,))).kind, "complete")

    def test_next_acknowledges_only_one_unknown_field_per_call(self):
        editor = make_screen(TO, SUBJECT, BODY, ATTACH, SEND)
        decision = self.point(editor, TO)
        self.assertIn("say ‘Next’", decision.instruction_en)
        self.assertFalse(self.guide.skip_current("skip"))
        self.assertTrue(self.guide.skip_current("അടുത്തത് / Next"))
        self.point(editor, SUBJECT)
        self.point(editor, SUBJECT)
        self.assertTrue(self.guide.skip_current("Next"))
        self.point(editor, BODY)
        self.assertTrue(self.guide.skip_current("Next"))
        self.point(editor, ATTACH)
        self.assertTrue(self.guide.skip_current("Next"))
        self.point(editor, SEND)

    def test_visible_empty_field_blocks_send_and_acknowledgement(self):
        editor = make_screen(TO, SUBJECT, BODY, ATTACH, SEND, filled=("To", "Subject"))
        self.point(editor, BODY)
        self.assertTrue(self.guide.skip_current("Next"))
        empty_body = make_screen(TO, SUBJECT, BODY, ATTACH, SEND, filled=("To", "Subject"), empty=("Message Body",))
        self.point(empty_body, BODY)
        self.assertFalse(self.guide.skip_current("Next"))
        self.point(empty_body, BODY)

    def test_confirmed_to_field_can_collapse_after_focus_moves_to_subject(self):
        self.point(make_screen(TO, SUBJECT, BODY, SEND), TO)
        collapsed = make_screen(SUBJECT, BODY, SEND)
        for step in (SUBJECT, BODY, SEND):
            self.assertTrue(self.guide.skip_current("Next"))
            self.point(collapsed, step)
        self.point(make_screen(TO, SUBJECT, BODY, SEND, empty=("To",)), TO)

    def test_reply_never_opens_a_row_or_uses_a_new_draft(self):
        self.guide = PACK.start_guidance("How do I reply to this email?")
        self.assertEqual(self.guide.decide(make_screen(COMPOSE)).kind, "clarify")
        self.point(make_screen(REPLY, extra=(OPEN_EMAIL,)), REPLY)
        editor = make_screen(BODY, SEND, extra=(OPEN_EMAIL,))
        self.point(editor, BODY)
        self.assertTrue(self.guide.skip_current("done"))
        self.point(editor, SEND)
        new_draft = make_screen(TO, SUBJECT, BODY, SEND, extra=(OPEN_EMAIL,))
        self.assertEqual(self.guide.decide(new_draft).kind, "clarify")

    def test_search_resolves_editable_combo_not_search_button(self):
        self.guide = PACK.start_guidance("Mail engane search cheyyam")
        field = replace(SEARCH, role="AXComboBox")
        button = Control("Search", "AXButton", "Search mail", (10, 70, 80, 20))
        decision = self.point(make_screen(field, extra=(button,)), SEARCH)
        self.assertIn("press Enter", decision.instruction_en)

    def test_only_canonical_chrome_and_masked_question(self):
        private_label = "Asha's private health report"
        private_text = Control("secret", "AXHeading", private_label, FRAME)
        compose = replace(make_screen(COMPOSE).controls[0], label=" Compose! ", identifier="private-id", group=private_label)
        projection = PACK.privacy.filter_snapshot(replace(make_screen(COMPOSE), controls=(compose, private_text)))
        serialized = json.dumps(asdict(projection))
        self.assertNotIn(private_label, serialized)
        self.assertNotIn("private-id", serialized)
        self.assertEqual(projection.controls[0].label, "Compose")
        question = "Find parent+test@example.invalid, +91 (484) 012-3456, 12/11/2026 and ൧൨൩"
        sanitized = PACK.privacy.filter_question(question)
        self.assertEqual(sanitized.count("[redacted]"), 4)
        for token in ("example.invalid", "012-3456", "2026", "൧൨൩"):
            self.assertNotIn(token, sanitized)
        self.assertEqual(PACK.start_guidance(question).decide(make_screen(COMPOSE)).kind, "unsupported")
        self.post.assert_not_called()

    def test_registered_planner_dispatches_gmail_without_provider_fallback(self):
        planner = SarvamPlanner("web_site", log_calls=False)
        first = planner.decide(COMPOSE_QUESTION, make_screen(COMPOSE))
        self.assertEqual((first.kind, first.control_id), ("point", "Compose"))
        editor = make_screen(TO, SUBJECT, BODY, SEND, filled=("To",), empty=("Subject", "Message Body"))
        step = planner.decide(COMPOSE_QUESTION, editor)
        self.assertEqual((step.kind, step.control_id), ("point", "Subject"))
        result = planner.decide("Read my private mail from a@example.invalid", make_screen(COMPOSE))
        self.assertEqual((result.kind, result.control_id), ("unsupported", None))
        self.post.assert_not_called()
