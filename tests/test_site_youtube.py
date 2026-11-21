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
                    "www.youtube.com", bounds, controls, viewport=bounds,
                    below_fold_count=REPLAY["below_fold_counts"].get(name, 0))


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
        home = replace(snapshot("home"), below_fold_count=160)
        self.assertEqual(guide.decide(home).control_id, "search")
        typed = snapshot("typed")
        self.assertEqual(guide.decide(typed).control_id, "go")
        warm = replace(typed, snapshot_id="warm", controls=tuple(replace(c, id=f"fresh-{c.id}") for c in typed.controls))
        self.assertEqual(guide.decide(warm).control_id, "fresh-go")
        self.assertEqual(guide.decide(snapshot("results")).control_id, "best")

    def test_submitted_search_with_no_visible_video_links_can_ask_for_scroll(self):
        guide = PACK.start_guidance("Find and play Darshana Hridayam")
        self.assertEqual(guide.decide(snapshot("home")).control_id, "search")
        self.assertEqual(guide.decide(snapshot("typed")).control_id, "go")
        step = guide.decide(snapshot("no_links_yet"))
        self.assertEqual((step.kind, step.control_id, step.instruction_en),
                         ("clarify", None, "Scroll down to see more results."))
        self.assertIn("താഴേക്ക്", step.instruction)
        self.assertEqual(guide.decide(snapshot("results")).control_id, "best")

    def test_disregards_a_channel_even_when_its_heading_and_link_match(self):
        guide = PACK.start_guidance("Find and play Darshana Rajendran")
        self.assertEqual(guide.decide(snapshot("home")).control_id, "search")
        self.assertEqual(guide.decide(snapshot("typed")).control_id, "go")
        decision = guide.decide(snapshot("results"))
        self.assertEqual((decision.kind, decision.control_id), ("clarify", None))

    def test_prefers_the_regular_video_even_if_a_collection_has_more_title_cues(self):
        results = snapshot("song_results")
        for collection in ("mix", "playlist", "short"):
            with self.subTest(collection=collection):
                guide = PACK.start_guidance("Play the Darshana song")
                controls = tuple(results.control(c) for c in ("filters", collection, "plain"))
                decision = guide.decide(replace(results, controls=controls))
                self.assertEqual(decision.control_id, "plain")

    def test_uses_the_title_anchor_for_a_verified_video(self):
        snap = snapshot("results")
        best = snap.control("best")
        title = replace(best, identifier="youtube-watch:official:title")
        thumbnail = replace(best, id="thumbnail", label="Image or duration", frame=(20, 2, 160, 25),
                            identifier="youtube-watch:official:thumbnail")
        snap = replace(snap, controls=(
            thumbnail, *(title if c.id == title.id else c for c in snap.controls),
        ))
        guide = PACK.start_guidance("Find and play a video")
        guide.decide(snapshot("home"))
        guide.decide(snapshot("typed"))
        self.assertEqual(guide.decide(snap).control_id, "best")

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
        paused = snapshot("watch_paused")
        self.assertEqual(PACK.privacy.filter_snapshot(paused).control("play"), paused.control("play"))
        self.assertIsNone(PACK.start_guidance("Edit my profile photo"))

    def test_braces_in_spoken_title_are_literal(self):
        guide = PACK.start_guidance("Find and play {my title}")
        self.assertIn("{my title}", guide.decide(snapshot("home")).instruction_en)

    def test_polite_intent_and_video_title_with_a_number(self):
        faster = PACK.start_guidance("Could you please play at 1.25x?")
        self.assertEqual(faster.decide(snapshot("speed_menu")).control_id, "fast")
        search = PACK.start_guidance("Find and play Money 2x")
        self.assertIn("money 2x", search.decide(snapshot("home")).instruction_en)
        song = PACK.start_guidance("Please play the song called Darshana.")
        self.assertIn("Type ‘darshana’", song.decide(snapshot("home")).instruction_en)

    def test_language_button_outside_subtitles_is_not_pointed_at(self):
        snap = snapshot("watch")
        snap = replace(
            snap, controls=(*snap.controls, Control("other", "AXMenuItem", "Malayalam", (20, 290, 125, 20)))
        )
        guide = PACK.start_guidance("How do I turn on Malayalam subtitles?")
        self.assertEqual(guide.decide(snap).control_id, "gear")
        self.assertEqual(guide.decide(snapshot("menu")).control_id, "subs")
        self.assertEqual(guide.decide(snapshot("menu", 2)).control_id, "subs")

    def test_web_site_planner_keeps_a_guide_until_the_next_question(self):
        planner = SarvamPlanner("web_site", log_calls=False)
        with patch.object(sarvam, "_post") as post:
            question = "Find and play Darshana Hridayam"
            expected = (("home", "search"), ("typed", "go"), ("results", "best"), ("watch", None))
            for screen, control_id in expected:
                decision = planner.decide(question, snapshot(screen))
                self.assertEqual(decision.control_id, control_id)
            self.assertEqual(decision.kind, "complete")
            waiting = planner.decide("Play it slower", snapshot("generic_player_loading"))
            self.assertEqual((waiting.kind, waiting.control_id), ("clarify", None))
            self.assertEqual(planner.decide("Play it slower", snapshot("watch_paused")).control_id, "gear")
            partial = planner.decide("Play it slower", snapshot("settings_partial"))
            self.assertEqual((partial.kind, partial.control_id), ("clarify", None))
            self.assertEqual(planner.decide("Play it slower", snapshot("settings_values")).control_id, "speed")
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

    def test_provider_sees_fixed_menu_names_and_pointer_binds_to_live_row(self):
        planner = SarvamPlanner("web_site", log_calls=False)
        reply = {"kind": "point", "control_id": "speed",
                 "instruction_ml": "വേഗം മാറ്റാൻ അമർത്തൂ.", "instruction_en": "Open the playback settings."}
        response = {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(reply)}}]}
        screen = snapshot("settings_values")
        new_controls = tuple(replace(c, id=f"fresh-{c.id}") for c in screen.controls if c.id != "timer")
        refreshed = replace(screen, snapshot_id="refreshed", controls=new_controls)
        with (
            patch.object(sarvam, "_load_api_key", return_value="test-key"),
            patch.object(sarvam, "_post", return_value=(response, 1.0)) as post,
        ):
            question = "Where are the advanced options?"
            for snap, target in ((screen, "speed"), (refreshed, "fresh-speed")):
                decision = planner.decide(question, snap)
                self.assertEqual((decision.kind, decision.control_id), ("point", target))
                self.assertEqual(validate(decision, snap), (True, "ok"))
                self.assertIn("‘Playback speed Normal’", decision.instruction_en)
        post.assert_called_once()
        view = json.loads(json.loads(post.call_args.args[2])["messages"][1]["content"])
        for label in ("Playback speed", "Subtitles/CC", "Quality"):
            self.assertIn(f'"{label}"', view["controls"])
        for suffix in ("Normal", "English", "720p", "Sleep timer"):
            self.assertNotIn(suffix, view["controls"])
