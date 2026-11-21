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
        title = replace(best, identifier="youtube-watch:official:a123")
        thumbnail = replace(best, id="thumbnail", frame=(20, 2, 160, 25),
                            identifier="youtube-watch:official:c123")
        snap = replace(snap, controls=(
            thumbnail, *(title if c.id == title.id else c for c in snap.controls),
        ))
        guide = PACK.start_guidance("Find and play a video")
        guide.decide(snapshot("home"))
        guide.decide(snapshot("typed"))
        self.assertEqual(guide.decide(snap).control_id, "best")
        hovered = replace(title, id="fresh-title", label="Play video", identifier="youtube-watch:official:a456")
        changed = replace(snap, controls=tuple(hovered if c == title else c for c in snap.controls))
        self.assertEqual(guide.decide(changed).control_id, "fresh-title")
        only_thumbnail = replace(changed, controls=tuple(c for c in changed.controls if c != hovered))
        self.assertIsNone(guide.decide(only_thumbnail).control_id)
        self.assertEqual(guide.decide(changed).control_id, "fresh-title")

    def test_scroll_keeps_the_selected_result_until_an_equally_good_one_is_visible(self):
        guide = PACK.start_guidance("Play the Darshana song")
        results = snapshot("song_results")
        self.assertEqual(guide.decide(results).control_id, "best")
        best = results.control("best")
        cover = replace(best, id="cover", label="Darshana Official Video Song Hindi Cover",
                        identifier="youtube-watch:cover:a001")
        lower = replace(results, controls=(results.control("filters"), cover), below_fold_count=20)
        step = guide.decide(lower)
        self.assertEqual((step.kind, step.control_id), ("clarify", None))
        self.assertIn("Scroll back up to ‘Darshana", step.instruction_en)
        self.assertIn("മുകളിലേക്ക്", step.instruction)
        self.assertEqual(guide.decide(results).control_id, "best")
        alternate = replace(best, id="alternate", identifier="youtube-watch:alternate:a001")
        self.assertEqual(guide.decide(replace(lower, controls=(*lower.controls, alternate))).control_id, "alternate")

    def test_results_preview_player_does_not_wait_for_ad_or_claim_watch_playback(self):
        for labeled in (True, False):
            with self.subTest(labeled=labeled):
                guide = PACK.start_guidance("Find and play Darshana Hridayam")
                results = snapshot("song_results")
                links = tuple(c for c in results.controls if labeled or c.id != "filters")
                preview = replace(results, controls=(*links, *snapshot("ad_skip_plain").controls))
                self.assertEqual(guide.decide(preview).control_id, "best")
                self.assertEqual(guide.decide(preview).control_id, "best")
                self.assertEqual(guide.decide(snapshot("ad_skip_plain")).control_id, "skip")
                self.assertEqual(guide.decide(snapshot("watch")).kind, "complete")

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

    def test_malformed_manglish_uses_one_intent_call_with_only_the_question(self):
        planner = SarvamPlanner("web_site", log_calls=False)
        reply = {"action": "find", "title": "Darshana"}
        response = {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps(reply)}}]}
        with (
            patch.object(sarvam, "_load_api_key", return_value="test-key"),
            patch.object(sarvam, "_post", return_value=(response, 1.0)) as post,
        ):
            question = "Enikku darshana kaaranam"
            search = planner.decide(question, snapshot("home"))
            self.assertEqual(search.control_id, "search")
            self.assertIn("Darshana", search.instruction_en)
            self.assertEqual(planner.decide(question, snapshot("typed")).control_id, "go")
            self.assertEqual(planner.decide(question, snapshot("results")).control_id, "best")
        post.assert_called_once()
        request = json.loads(post.call_args.args[2])
        self.assertEqual(request["messages"][1]["content"], question)
        self.assertNotIn("Account private display name", str(request))
        schema = request["response_format"]["json_schema"]["schema"]
        self.assertEqual(set(schema["required"]), {"action", "title"})
        self.assertEqual(schema["properties"]["title"]["maxLength"], 60)

    @patch.object(sarvam, "_load_api_key", side_effect=AssertionError("Known phrases must stay local"))
    def test_native_and_romanized_search_suffixes_stay_local(self, load_key):
        questions = [f"Enikku Darshana {suffix}" for suffix in
                     ("kaananam", "kaanam", "kaanan", "kelkkanam", "venam", "vekku", "play cheyyu")]
        questions += [f"എനിക്ക് ദർശന {suffix}" for suffix in ("കാണണം", "കേൾക്കണം", "വേണം", "വെക്കൂ")]
        questions.append("Darshana kaananam")
        for question in questions:
            with self.subTest(question=question):
                decision = SarvamPlanner("web_site", log_calls=False).decide(question, snapshot("home"))
                self.assertEqual(decision.control_id, "search")
                self.assertIn("Type ‘darshana’", decision.instruction_en)
        load_key.assert_not_called()

    @patch.object(sarvam, "_load_api_key", side_effect=AssertionError("Known commands must stay local"))
    def test_natural_bilingual_speed_and_malayalam_request_forms_stay_local(self, load_key):
        slower = (
            "എനിക്ക് വീഡിയോ ഇച്ചിരി സ്ലോ ആക്കണം. / I need to slow down the video a bit.",
            "എനിക്ക് വീഡിയോ ഇച്ചിരി സ്ലോ ആക്കണം.", "സ്ലോ ആക്കണം", "സ്ലോ ആക്കൂ", "ഇച്ചിരി സ്ലോ", "കുറച്ച് സ്ലോ",
            "Slow down the video", "Slow down the video a bit", "I need to slow down", "I want to slow down",
            "പതുക്കെ ആക്കണം", "വേഗം കുറയ്ക്കണം", "സ്പീഡ് കുറയ്ക്കണം",
            "വീഡിയോ കുറിച്ച് പറയൂ / I need to slow down the video a bit.",
        )
        for question in slower:
            with self.subTest(question=question):
                planner = SarvamPlanner("web_site", log_calls=False)
                for screen, target in (("watch", "gear"), ("settings_values", "speed"), ("speed_menu", "slow")):
                    self.assertEqual(planner.decide(question, snapshot(screen)).control_id, target)
        for question, screen, target in (
            ("പ്ലേ ചെയ്യണം", "watch_paused", "play"), ("നിർത്തണം", "watch", "pause"),
            ("വലുതാക്കണം", "watch", "full"), ("ശബ്ദം ഓഫ് ചെയ്യണം", "watch", "mute"),
            ("ശബ്ദം തിരിച്ചു കൊണ്ടുവരണം", "muted", "unmute"), ("അക്ഷരങ്ങൾ കാണിക്കണം", "cc_off", "cc"),
            ("വേഗം കൂട്ടണം", "speed_menu", "fast"), ("ഫുൾ സ്ക്രീനിൽ നിന്ന് പുറത്തു വരണം", "fullscreen", None),
        ):
            with self.subTest(question=question):
                decision = SarvamPlanner("web_site", log_calls=False).decide(question, snapshot(screen))
                self.assertEqual(decision.control_id, target)
                self.assertEqual(decision.kind, "point" if target else "clarify")
        load_key.assert_not_called()

    @patch.object(sarvam, "_load_api_key", side_effect=AssertionError("Known commands must stay local"))
    def test_make_it_faster_points_to_player_settings_locally(self, load_key):
        controls = (
            Control("pause", "AXButton", "Pause (k)", (55, 548, 38, 35)),
            Control("seek", "AXSlider", "Seek slider", (52, 529, 610, 10)),
            Control("settings", "AXPopUpButton", "Settings", (610, 548, 40, 35)),
        )
        snap = Snapshot("player", 0, "com.apple.Safari", 123, "www.youtube.com", (0, 0, 1200, 800), controls,
                        viewport=(0, 60, 1200, 740))
        decision = SarvamPlanner("web_site", log_calls=False).decide("make it faster", snap)
        self.assertEqual((decision.kind, decision.control_id), ("point", "settings"))
        self.assertEqual(validate(decision, snap, now=snap.taken_at), (True, "ok"))
        self.assertEqual(PACK.start_guidance("make it faster").decide(snapshot("speed_menu")).control_id, "fast")
        load_key.assert_not_called()

    def test_unrecognized_model_intents_stay_in_youtube_search(self):
        for reply in ({"action": None, "title": ""}, {"action": "delete", "title": ""},
                      {"action": "find", "title": "x" * 61}):
            with (self.subTest(reply=reply), patch.object(sarvam, "_load_api_key", return_value="test-key"),
                  patch.object(sarvam, "_post") as post,
                  patch("companion.planner_sarvam.FormPlan.from_snapshot", side_effect=AssertionError("generic plan"))):
                planner = SarvamPlanner("web_any", log_calls=False)
                post.return_value = ({"choices": [{"finish_reason": "stop",
                                                   "message": {"content": json.dumps(reply)}}]}, 1.0)
                for screen in ("results", "typed"):
                    step = planner.decide("Something unclear", snapshot(screen))
                    self.assertEqual(step.control_id, "search")
                    self.assertIn("Type the name", step.instruction_en)
                post.assert_called_once()

    def test_privacy_keeps_fixed_menu_names(self):
        safe = PACK.privacy.filter_snapshot(snapshot("settings_values"))
        self.assertEqual({c.label for c in safe.controls}, {"Settings", "Playback speed", "Subtitles/CC", "Quality"})
