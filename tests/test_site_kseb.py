"""KSEB pack contracts, replay and privacy checks without network or a browser."""

from dataclasses import replace
import json
import unittest
from unittest.mock import patch

from companion.contracts import Control
from companion.guidance import FormPlan
from companion.planner_sarvam import DEFAULT_MODEL, SarvamPlanner
from companion.sites import pack_for
from companion.sites.kseb import CONSUMER, MOBILE, PACK, SEE_BILL, VERIFICATION
from companion.tasks import load
from companion.validator import validate
from companion.voice import sarvam
from scripts import eval_planner


class KsebTests(unittest.TestCase):
    def setUp(self):
        self.screens = json.loads((eval_planner.FIXTURES / "screens.json").read_text())
        self.snap = eval_planner._snapshot("kseb", self.screens["kseb-form"], False)
        self.post = self.enterContext(patch.object(sarvam, "_post"))
        self.planner = SarvamPlanner(load("web_site"), log_calls=False)

    def test_pack_matches_exact_host_and_practice_signature(self):
        self.assertIs(pack_for(self.snap), PACK)
        self.assertIs(pack_for(replace(self.snap, window_title="127.0.0.1")), PACK)
        self.assertIsNone(pack_for(replace(self.snap, window_title="wss.kseb.in.example.com")))
        unrelated = replace(self.snap, window_title="127.0.0.1", controls=self.snap.controls[:1])
        self.assertIsNone(pack_for(unrelated))
        self.assertEqual(load("web_site").bundle_id, "com.apple.Safari")

    def test_kseb_eval_phrasings_resolve_without_sarvam(self):
        cases = json.loads((eval_planner.FIXTURES / "cases.json").read_text())
        targets = [case for case in cases if case["task"] == "web_site"]
        self.assertEqual(len(targets), 9)
        for case in targets:
            with self.subTest(id=case["id"]):
                row = eval_planner._case(DEFAULT_MODEL, case, self.screens[case["screen"]])
                self.assertTrue(row["correct"])
                self.assertTrue(row["cache_ok"])
                self.assertEqual(row["calls"], [])
        self.post.assert_not_called()

    def test_pack_order_wins_and_captcha_is_read_by_user(self):
        question = "എന്റെ കറന്റ് ബിൽ എങ്ങനെ അടയ്ക്കാം?"
        snap = replace(
            self.snap, window_title="127.0.0.1",
            controls=tuple(replace(c, frame=(20, 240 - i * 22, 130, 16))
                           for i, c in enumerate(self.snap.controls)),
        )
        self.assertEqual([unit.site_step for unit in FormPlan.from_snapshot(snap, PACK.steps).units], list(PACK.steps))
        for index, step in enumerate((CONSUMER, MOBILE, VERIFICATION, SEE_BILL)):
            decision = self.planner.decide(question, snap)
            control = snap.control(decision.control_id)
            self.assertEqual(control.label, step.label)
            self.assertEqual(decision.instruction, f"അടുത്തത്, {step.ml}" if index else step.ml)
            self.assertEqual(decision.instruction_en, f"Next, {step.en[:1].lower()}{step.en[1:]}" if index else step.en)
            self.assertEqual(validate(decision, snap), (True, "ok"))
            snap = replace(
                snap, snapshot_id=f"after-{control.id}",
                controls=tuple(replace(c, filled=True) if c.id == control.id else c for c in snap.controls),
            )
        completed = replace(snap, controls=(
            Control("receipt", "AXHeading", PACK.practice_result, (20, 20, 160, 20)),
        ))
        decision = self.planner.decide(question, completed)
        self.assertEqual((decision.kind, decision.control_id), ("complete", None))
        self.assertIn("Read the image yourself", VERIFICATION.en)
        self.assertIn("Refresh", VERIFICATION.en)
        self.post.assert_not_called()

    def test_missing_consumer_field_does_not_advance_to_later_visible_steps(self):
        clipped = replace(
            self.snap, snapshot_id="clipped", below_fold_count=1,
            controls=tuple(c for c in self.snap.controls if c.id != "consumer"),
        )
        decision = self.planner.decide("How do I see my electricity bill?", clipped)
        self.assertEqual((decision.kind, decision.control_id, decision.instruction_en),
                         ("clarify", None, "Scroll down to continue."))
        self.post.assert_not_called()

    def test_provider_sees_allowlisted_controls_and_redacted_numbers(self):
        secret_label = "Private display label and account balance"
        private = Control("private", "AXHeading", secret_label, (10, 1, 150, 20))
        snap = replace(self.snap, controls=(private, *self.snap.controls))
        reply = {
            "kind": "point", "control_id": "submit",
            "instruction_ml": "അമർത്തൂ [CONTROL].", "instruction_en": "Press [CONTROL].",
        }
        self.post.return_value = (
            {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(reply)}}]}, 2.0,
        )
        with patch.object(sarvam, "_load_api_key", return_value="fake-unit-key"):
            decision = self.planner.decide("Do I use 1234567890123 or 01234 56789 to check this?", snap)
        payload = json.loads(self.post.call_args.args[2])
        view = json.loads(payload["messages"][1]["content"])
        self.assertNotIn(secret_label, view["controls"])
        self.assertNotEqual(view["screen_title"], secret_label)
        self.assertNotIn("1234567890123", view["question"])
        self.assertNotIn("01234 56789", view["question"])
        self.assertIn("[redacted]", view["question"])
        self.assertIn("13 digit Consumer number", view["controls"])
        self.assertEqual(decision.control_id, "consumer")
        self.assertEqual(decision.instruction, CONSUMER.ml)

    def test_unconfigured_web_site_never_sends_a_snapshot(self):
        snap = replace(self.snap, window_title="mail.google.com")
        decision = self.planner.decide("Show the latest email.", snap)
        self.assertEqual((decision.kind, decision.control_id), ("unsupported", None))
        self.post.assert_not_called()
