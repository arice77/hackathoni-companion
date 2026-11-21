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
COMPOSE_QUESTION = "എനിക്ക് ഒരു ഇമെയിൽ അയയ്ക്കണം"


def make_screen(*steps, filled=(), empty=(), extra=()):
    controls = tuple(Control(step.label, step.role, step.label, (10, 30 + index * 30, 180, 20),
                             filled=True if step.label in filled else False if step.label in empty else None)
                     for index, step in enumerate(steps))
    return Snapshot("screen", time.time(), "com.apple.Safari", 101, HOST, FRAME, (*controls, *extra), FRAME)


class GmailSiteTests(unittest.TestCase):
    def setUp(self):
        self.guide = PACK.new_guide()
        self.post = self.enterContext(patch.object(sarvam, "_post", side_effect=AssertionError("Unexpected provider call")))

    def point(self, question, snap, step, revision=0):
        decision = self.guide.decide(question, snap, revision=revision)
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
                    self.guide = PACK.new_guide()
                    self.point(question, snap, step)
        self.post.assert_not_called()

    def test_compose_walk_without_reading_values(self):
        self.point(COMPOSE_QUESTION, make_screen(COMPOSE), COMPOSE)
        editor = make_screen(TO, SUBJECT, BODY, ATTACH, SEND)
        decision = self.point(COMPOSE_QUESTION, editor, TO)
        self.assertIn("son’s email", decision.instruction_en)
        self.assertIn("say ‘Next’", decision.instruction_en)
        self.point("skip", editor, TO, revision=1)
        self.point("അടുത്തത്", editor, SUBJECT, revision=2)
        self.point("അടുത്തത്", editor, SUBJECT, revision=2)
        self.point("next", editor, BODY, revision=3)
        decision = self.point("next", editor, ATTACH, revision=4)
        self.assertIn("Open", decision.instruction_en)
        self.assertIn("skip", decision.instruction_en)
        decision = self.point("skip", editor, SEND, revision=5)
        self.assertIn("only when you’re ready", decision.instruction_en)
        closed = self.guide.decide("skip", make_screen(COMPOSE), revision=5)
        self.assertEqual((closed.kind, closed.control_id), ("clarify", None))
        self.assertIn("can’t confirm", closed.instruction_en)

    def test_visible_empty_field_blocks_send_and_acknowledgement(self):
        editor = make_screen(TO, SUBJECT, BODY, ATTACH, SEND, filled=("To", "Subject"), empty=("Message Body",))
        self.point(COMPOSE_QUESTION, editor, BODY)
        self.point("done", editor, BODY, revision=1)
        ready = make_screen(TO, SUBJECT, BODY, ATTACH, SEND, filled=("To", "Subject", "Message Body"))
        self.point("done", ready, ATTACH, revision=1)
        self.assertTrue(self.guide.skip_optional())
        self.point("done", ready, SEND, revision=1)

    def test_confirmed_to_field_can_collapse_after_focus_moves_to_subject(self):
        self.point(COMPOSE_QUESTION, make_screen(TO, SUBJECT, BODY, SEND), TO)
        collapsed = make_screen(SUBJECT, BODY, SEND)
        self.point("next", collapsed, SUBJECT, revision=1)
        self.point("next", collapsed, BODY, revision=2)
        self.point("next", collapsed, SEND, revision=3)
        self.point("next", make_screen(TO, SUBJECT, BODY, SEND, empty=("To",)), TO, revision=3)

    def test_reply_never_opens_a_row_or_uses_a_new_draft(self):
        question = "How do I reply to this email?"
        self.assertEqual(self.guide.decide(question, make_screen(COMPOSE)).kind, "clarify")
        self.point(question, make_screen(REPLY, extra=(OPEN_EMAIL,)), REPLY)
        editor = make_screen(BODY, SEND, extra=(OPEN_EMAIL,))
        self.point(question, editor, BODY)
        self.point("done", editor, SEND, revision=1)
        new_draft = make_screen(TO, SUBJECT, BODY, SEND, extra=(OPEN_EMAIL,))
        self.assertEqual(self.guide.decide("done", new_draft, revision=1).kind, "clarify")

    def test_search_resolves_editable_combo_not_search_button(self):
        field = replace(SEARCH, role="AXComboBox")
        button = Control("Search", "AXButton", "Search mail", (10, 70, 80, 20))
        decision = self.point("Mail engane search cheyyam", make_screen(field, extra=(button,)), SEARCH)
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
        self.assertEqual(self.guide.decide(question, make_screen(COMPOSE)).kind, "unsupported")
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
