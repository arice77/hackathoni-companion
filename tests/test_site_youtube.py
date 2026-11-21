"""Replay YouTube Accessibility states without accessing a browser or Sarvam."""

from dataclasses import replace
import json
from pathlib import Path
import time
import unittest
from unittest.mock import patch

from companion.contracts import Control, Snapshot
from companion.planner_sarvam import SarvamPlanner
from companion.sites import pack_for
from companion.sites.youtube import PACK
from companion.validator import validate
from companion.voice import sarvam

FIXTURE = Path(__file__).parent / "fixtures" / "planner" / "youtube.json"
REPLAY = json.loads(FIXTURE.read_text())


def snapshot(name: str, tick: int = 0) -> Snapshot:
    controls = tuple(
        Control(**row, frame=(20, 8 + 23 * i, 170, 20))
        for i, row in enumerate(REPLAY["screens"][name])
    )
    bounds = (0, 0, 500, 500)
    return Snapshot(f"{name}-{tick}", time.time(), "com.apple.Safari", 123,
                    "www.youtube.com", bounds, controls, viewport=bounds)


class YouTubeTests(unittest.TestCase):
    def test_multilingual_eval(self):
        self.assertEqual({case["language"] for case in REPLAY["cases"]}, {"english", "malayalam", "manglish"})
        for case in REPLAY["cases"]:
            with self.subTest(case=case["id"]):
                guide = PACK.start_guidance(case["question"])
                self.assertIsNotNone(guide)
                for tick, (screen, kind, control_id, *text) in enumerate(case["walk"]):
                    snap = snapshot(screen, tick)
                    decision = guide.decide(snap)
                    self.assertEqual((decision.kind, decision.control_id), (kind, control_id))
                    self.assertEqual(validate(decision, snap), (True, "ok"))
                    if text:
                        self.assertIn(text[0], decision.instruction_en)
                    if control_id:
                        label = snap.control(control_id).label
                        self.assertIn(f"‘{label}’", decision.instruction)
                        self.assertIn(f"‘{label}’", decision.instruction_en)

    def test_search_rebinds_the_same_action_to_fresh_ids_without_advance(self):
        guide = PACK.start_guidance("Find and play Darshana Hridayam")
        home = snapshot("home")
        self.assertEqual(guide.decide(home).control_id, "search")
        typed = snapshot("typed")
        self.assertEqual(guide.decide(typed).control_id, "go")
        warm = replace(typed, snapshot_id="warm", controls=tuple(replace(c, id=f"fresh-{c.id}") for c in typed.controls))
        self.assertEqual(guide.decide(warm).control_id, "fresh-go")
        self.assertEqual(guide.decide(snapshot("results")).control_id, "best")

    def test_existing_search_text_can_be_replaced_without_reading_it(self):
        guide = PACK.start_guidance("Find and play Darshana Hridayam")
        existing = snapshot("typed")
        instruction = guide.decide(existing)
        self.assertEqual(instruction.control_id, "search")
        self.assertIn("press Return", instruction.instruction_en)
        self.assertEqual(guide.decide(snapshot("results")).control_id, "best")

    def test_open_menu_state_does_not_repoint_settings(self):
        guide = PACK.start_guidance("Play it slower")
        self.assertEqual(guide.decide(snapshot("watch")).control_id, "gear")
        self.assertEqual(guide.decide(snapshot("menu")).control_id, "speed")
        self.assertEqual(guide.decide(snapshot("speed_menu")).control_id, "slow")
        closed = guide.decide(snapshot("watch"))
        self.assertEqual((closed.kind, closed.control_id), ("clarify", None))
        self.assertIn("Check that", closed.instruction_en)

    def test_only_supported_host_and_safe_provider_controls(self):
        self.assertIs(pack_for(snapshot("watch")), PACK)
        self.assertIsNone(pack_for(replace(snapshot("watch"), window_title="www.youtube.com.example.net")))
        safe = PACK.privacy.filter_snapshot(snapshot("results"))
        self.assertEqual({c.id for c in safe.controls}, {"search", "go"})
        self.assertIsNone(PACK.start_guidance("Edit my profile photo"))

    def test_braces_in_spoken_title_are_literal(self):
        guide = PACK.start_guidance("Find and play {my title}")
        self.assertIn("{my title}", guide.decide(snapshot("home")).instruction_en)

    def test_web_site_planner_keeps_a_guide_until_the_next_question(self):
        planner = SarvamPlanner("web_site", log_calls=False)
        with patch.object(sarvam, "_post") as post:
            question = "Find and play Darshana Hridayam"
            expected = (("home", "search"), ("typed", "go"), ("results", "best"), ("watch", None))
            for screen, control_id in expected:
                decision = planner.decide(question, snapshot(screen))
                self.assertEqual(decision.control_id, control_id)
            self.assertEqual(decision.kind, "complete")
            self.assertEqual(planner.decide("Play it slower", snapshot("watch")).control_id, "gear")
            self.assertEqual(planner.decide("Play it slower", snapshot("menu")).control_id, "speed")
            self.assertEqual(planner.decide("Play it slower", snapshot("speed_menu")).control_id, "slow")
            post.assert_not_called()

    def test_unknown_youtube_intent_uses_safe_provider_context_once(self):
        planner = SarvamPlanner("web_site", log_calls=False)
        reply = {
            "kind": "unsupported", "control_id": None,
            "instruction_ml": "സഹായിക്കാൻ കഴിയില്ല.", "instruction_en": "I can’t help with that.",
        }
        response = {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(reply)}}]}
        with (
            patch.object(sarvam, "_load_api_key", return_value="test-key"),
            patch.object(sarvam, "_post", return_value=(response, 1.0)) as post,
        ):
            question = "What is my username?"
            self.assertEqual(planner.decide(question, snapshot("results")).kind, "unsupported")
            self.assertEqual(planner.decide(question, snapshot("watch")).kind, "unsupported")
        post.assert_called_once()
        view = json.loads(json.loads(post.call_args.args[2])["messages"][1]["content"])
        self.assertIn("Guide YouTube search", view["task_goal"])
        self.assertNotIn("Account private display name", view["controls"])
        self.assertNotIn("Darshana", view["controls"])
