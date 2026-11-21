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
    @patch.object(sarvam, "_load_api_key", side_effect=AssertionError("Replay must stay in the local site pack"))
    def test_multilingual_eval(self, load_key):
        self.assertEqual({case["language"] for case in REPLAY["cases"]}, {"english", "malayalam", "manglish"})
        for case in REPLAY["cases"]:
            with self.subTest(case=case["id"]):
                planner = SarvamPlanner("web_site", log_calls=False)
                for tick, (screen, kind, control_id, *text) in enumerate(case["walk"]):
                    snap = snapshot(screen, tick)
                    decision = planner.decide(case["question"], snap)
                    self.assertEqual((decision.kind, decision.control_id), (kind, control_id))
                    self.assertEqual(validate(decision, snap), (True, "ok"))
                    if text:
                        self.assertIn(text[0], decision.instruction_en)
                    if control_id:
                        label = snap.control(control_id).label
                        self.assertIn(f"‘{label}’", decision.instruction)
                        self.assertIn(f"‘{label}’", decision.instruction_en)
        load_key.assert_not_called()

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

    @patch.object(sarvam, "_load_api_key", side_effect=AssertionError("Speed must stay local"))
    def test_custom_speed_counts_down_then_completes_without_a_preset(self, load_key):
        planner = SarvamPlanner("web_site", log_calls=False)
        question = "Play it slower"
        self.assertEqual(planner.decide(question, snapshot("watch")).control_id, "gear")
        self.assertEqual(planner.decide(question, snapshot("settings_values")).control_id, "speed")
        for tick, (value, kind, target, text, ml_text) in enumerate((
            ("1.0", "point", "decrease", "Press − to slow down (5 more times)", "ഇനി 5 തവണ"),
            ("0.8", "point", "decrease", "Press − to slow down (1 more time)", "ഇനി 1 തവണ"),
            ("0.75", "complete", None, "The video is set to 0.75×.", "0.75"),
            ("0.7509", "complete", None, "The video is set to 0.75×.", "0.75"),
        )):
            with self.subTest(value=value):
                snap = snapshot("speed_stepper", tick)
                snap = replace(snap, controls=tuple(replace(c, label=f"Playback speed slider {value}")
                               if c.role == "AXSlider" else c for c in snap.controls))
                decision = planner.decide(question, snap)
                self.assertEqual((decision.kind, decision.control_id, decision.instruction_en), (kind, target, text))
                self.assertIn(ml_text, decision.instruction)
                self.assertEqual(validate(decision, snap), (True, "ok"))
        load_key.assert_not_called()

    def test_custom_speed_without_slider_uses_visible_menu_value_or_no_count(self):
        guide = PACK.start_guidance("Play it slower")
        snap = snapshot("speed_stepper")
        controls = tuple(c for c in snap.controls if c.role != "AXSlider")
        decision = guide.decide(replace(snap, controls=controls))
        self.assertEqual((decision.control_id, decision.instruction_en), ("decrease", "Press − until it shows 0.75×."))
        speed = replace(snapshot("settings_values").control("speed"), label="Playback speed 0.70")
        decision = guide.decide(replace(snap, controls=(*controls, speed)))
        self.assertEqual((decision.control_id, decision.instruction_en),
                         ("increase", "Press + to speed up (1 more time)"))

    def test_speed_prefers_a_preset_and_does_not_overshoot_an_unreachable_value(self):
        snap = snapshot("speed_stepper")
        self.assertEqual(PACK.start_guidance("Faster").decide(snap).control_id, "fast")
        decision = PACK.start_guidance("Set playback speed to 0.76").decide(snap)
        self.assertEqual((decision.kind, decision.control_id), ("clarify", None))
        self.assertIn("0.05× at a time", decision.instruction_en)

    def test_waits_for_ad_markers_and_keeps_advertiser_copy_out_of_sarvam(self):
        playing = snapshot("watch")
        for label, marker in (
            ("Ad · Some advertiser", "Ad"), ("Sponsored by Some advertiser", "Sponsored"),
            ("Ad 1 of 2", "Ad break"), ("My Ad Centre", "My Ad Centre"),
            ("Visit advertiser — Some advertiser", "Visit advertiser"),
        ):
            with self.subTest(label=label):
                ad = Control("ad", "AXButton", label, (20, 275, 150, 20))
                snap = replace(playing, controls=(*playing.controls, ad))
                guide = PACK.start_guidance("Resume the video")
                decision = guide.decide(snap)
                self.assertEqual((decision.kind, decision.control_id), ("clarify", None))
                self.assertEqual(decision.instruction_en, "The ad will finish in a few seconds.")
                safe = PACK.privacy.filter_snapshot(snap).control("ad")
                self.assertEqual((safe.role, safe.label), ("AXStaticText", marker))
                self.assertEqual(guide.decide(playing).kind, "complete")

    def test_sponsored_search_card_does_not_block_the_results(self):
        results = snapshot("results")
        sponsor = Control("sponsor", "AXStaticText", "Sponsored", (20, 275, 150, 20))
        guide = PACK.start_guidance("Find Darshana Hridayam")
        decision = guide.decide(replace(results, controls=(*results.controls, sponsor)))
        self.assertEqual(decision.control_id, "best")

    def test_sponsored_recommendation_beside_the_player_does_not_block_playback(self):
        playing = snapshot("watch")
        ads = tuple(Control(f"outside-{i}", "AXButton", label, (300, 20 + 25 * i, 150, 20))
                    for i, label in enumerate(("Sponsored", "My Ad Centre", "Visit advertiser", "Skip")))
        snap = replace(playing, controls=(*playing.controls, *ads))
        guide = PACK.start_guidance("Resume the video")
        self.assertEqual(guide.decide(snap).kind, "complete")
        self.assertTrue(all(PACK.privacy.filter_snapshot(snap).control(ad.id) is None for ad in ads))

    def test_partial_settings_reopens_once_then_advances_when_the_row_appears(self):
        planner = SarvamPlanner("web_site", log_calls=False)
        question = "Play it slower"
        partial = snapshot("settings_partial")
        with (
            patch("companion.sites.youtube.monotonic", return_value=10.0) as clock,
            patch.object(sarvam, "_post") as post,
        ):
            self.assertEqual(planner.decide(question, snapshot("watch_paused")).control_id, "gear")
            self.assertEqual(planner.decide(question, partial).kind, "clarify")
            self.assertEqual(planner.retry_at, 13.0)
            clock.return_value = 12.9
            self.assertEqual(planner.decide(question, partial).kind, "clarify")
            self.assertEqual(planner.retry_at, 13.0)
            clock.return_value = 13.0
            decision = planner.decide(question, partial)
            self.assertEqual((decision.kind, decision.control_id), ("point", "gear"))
            self.assertEqual(decision.instruction_en, "Close ‘Settings’, then open it again.")
            self.assertIsNone(planner.retry_at)
            closed = planner.decide(question, snapshot("watch_paused"))
            self.assertEqual((closed.control_id, closed.instruction_en), ("gear", decision.instruction_en))
            clock.return_value = 18.0
            decision = planner.decide(question, partial)
            self.assertEqual((decision.kind, decision.control_id), ("clarify", None))
            self.assertIn("still isn’t visible", decision.instruction_en)
            self.assertIsNone(planner.retry_at)
            self.assertEqual(planner.decide(question, snapshot("settings_values")).control_id, "speed")
            self.assertEqual(planner.decide(question, snapshot("speed_menu")).control_id, "slow")
            post.assert_not_called()

    def test_ad_cancels_the_settings_timer_until_normal_playback_returns(self):
        guide = PACK.start_guidance("Play it slower")
        partial = snapshot("settings_partial")
        with patch("companion.sites.youtube.monotonic", return_value=10.0) as clock:
            self.assertEqual(guide.decide(partial).kind, "clarify")
            self.assertEqual(guide.retry_at, 13.0)
            clock.return_value = 18.0
            self.assertIn("The ad", guide.decide(snapshot("settings_partial_ad")).instruction_en)
            self.assertIsNone(guide.retry_at)
            clock.return_value = 20.0
            self.assertEqual(guide.decide(partial).kind, "clarify")
            self.assertEqual(guide.retry_at, 23.0)
            self.assertEqual(guide.decide(snapshot("settings_values")).control_id, "speed")
            self.assertIsNone(guide.retry_at)

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
