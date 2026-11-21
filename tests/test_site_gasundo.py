import json
import unittest
from dataclasses import asdict
from unittest.mock import patch

from companion import reader
from companion.planner_sarvam import SarvamPlanner
from companion.sites.gasundo import PACK
from companion.validator import validate
from companion.voice import sarvam


FRAME = (0, 0, 1000, 750)
URL = "https://gasundo.live/?district=ernakulam"
QUESTION = "Is Bektash Kakkanad open?"


def snapshot(*entries, district="Ernakulam", search="", url=URL):
    nodes = {
        "page": {"AXRole": "AXWebArea", "AXURL": url},
        "district": {"AXRole": "AXPopUpButton", "AXValue": district, "AXDOMIdentifier": "district-select-hero",
                     "frame": (35, 65, 220, 40)},
        "search": {"AXRole": "AXTextField", "AXValue": search, "AXDOMIdentifier": "restaurant-search-panel",
                   "AXPlaceholderValue": "Search restaurants", "frame": (35, 250, 300, 40)},
    }
    nodes.update({key: {"AXRole": role, ("AXValue" if role == "AXStaticText" else "AXTitle"): label,
                        "frame": frame} for key, role, label, frame in entries})
    nodes["page"]["AXChildren"] = [key for key in nodes if key != "page"]
    view = reader._WebView("page", FRAME, FRAME, url, ())
    with patch.object(reader, "_frame", side_effect=lambda key, _: nodes[key].get("frame", FRAME)):
        return reader._read_web_snapshot(view, reader.SAFARI, 123, lambda key, attr: nodes[key].get(attr))


def card(*labels):
    return (("card", "AXButton", "Copy Bektash Kakkanad link", (280, 370, 30, 30)),
            *((f"status-{i}", "AXStaticText", label, (55, 440 + i * 22, 150, 18))
              for i, label in enumerate(labels)))


class GasUndoTests(unittest.TestCase):
    def test_named_workflow_and_private_projection(self):
        planner = SarvamPlanner("web_site", log_calls=False)
        steps = [
            (snapshot(district="Alappuzha"), "Select district: Alappuzha"),
            (snapshot(), "Search restaurants"),
            (snapshot(("result", "AXButton", "Bektash Kakkanad select", (35, 294, 300, 42)),
                      ("another", "AXButton", "Bektash Edappally select", (35, 342, 300, 42)),
                      ("signin", "AXButton", "Sign in with Google", (35, 392, 300, 42)),
                      search="private query"), "Bektash Kakkanad"),
        ]
        with patch.object(sarvam, "_post", side_effect=AssertionError("Unexpected chat call")):
            for snap, label in steps:
                answer = planner.decide(QUESTION, snap)
                self.assertEqual(answer.kind, "point")
                self.assertEqual(snap.control(answer.control_id).label, label)
                self.assertEqual(validate(answer, snap), (True, "ok"))
            report = snapshot(*card("Limited menu", "Stale", "252d ago", "ordinary comment"))
            answer = planner.decide(QUESTION, report)
            self.assertEqual(answer.kind, "complete")
            self.assertIn("limited menu", answer.instruction_en)
            self.assertIn("252 days ago", answer.instruction_en)
            self.assertIn("current status is unknown", answer.instruction_en)
            self.assertFalse(planner.calls)
        serialized = json.dumps(asdict(steps[2][0]))
        self.assertNotIn("private query", serialized)
        self.assertNotIn("?district", serialized)
        self.assertNotIn("ordinary comment", json.dumps(asdict(report)))
        suggestions = [c for c in steps[2][0].controls if (c.identifier or "").startswith("gasundo-suggestion:")]
        self.assertEqual(len({c.identifier for c in suggestions}), 2)

    def test_malayalam_and_manglish_requests(self):
        self.enterContext(patch.object(sarvam, "transliterate_text", side_effect=sarvam.SarvamMissingKeyError()))
        for question in ("ബെക്താഷ് കാക്കനാടിന്റെ നില എങ്ങനെ നോക്കാം?", "Bektash Kakkanad open aano?",
                         "Bektash Kakkanad thurannittundo?", "Bektash Kakkanad open aano ennu ariyanam"):
            with self.subTest(question=question):
                snap = snapshot()
                decision = PACK.start_guidance(question).decide(snap)
                self.assertEqual(snap.control(decision.control_id).label, "Search restaurants")
                self.assertIn("Bektash Kakkanad", decision.instruction_en)
        snap = snapshot(("open", "AXButton", "Open 35", (35, 335, 260, 40)))
        answer = PACK.start_guidance("എറണാകുളത്ത് ഇപ്പോൾ തുറന്നിരിക്കുന്ന ഹോട്ടലുകൾ ഏതൊക്കെ?").decide(snap)
        self.assertEqual(snap.control(answer.control_id).label, "Open 35")
        self.assertIn("filters the map", answer.instruction_en)

    def test_english_transcript_supplies_latin_name_without_a_provider_call(self):
        with patch.object(sarvam, "transliterate_text") as transliterate:
            guide = PACK.start_guidance("റഹ്മാനിയ ഹോട്ടൽ തുറന്നിട്ടുണ്ടോ എന്ന് അറിയണം / Is Rahmaniya Hotel open?")
            answer = guide.decide(snapshot())
        self.assertEqual(answer.kind, "point")
        self.assertIn("rahmaniya hotel", answer.instruction_en)
        transliterate.assert_not_called()

    def test_malayalam_name_transliterates_once_for_the_whole_replay(self):
        planner = SarvamPlanner("web_site", log_calls=False)
        question = "റഹ്മാനിയ ഹോട്ടൽ തുറന്നിട്ടുണ്ടോ എന്ന് അറിയണം"
        with patch.object(sarvam, "transliterate_text", return_value="Rahmaniya Hotel") as transliterate:
            answer = planner.decide(question, snapshot())
            self.assertIn("Rahmaniya Hotel", answer.instruction_en)
            results = snapshot(("result", "AXButton", "Rahmaniya Hotel select", (35, 294, 300, 42)),
                               search="Rahmaniya")
            result = planner.decide(question, results)
            self.assertEqual(results.control(result.control_id).label, "Rahmaniya Hotel")
            transliterate.assert_called_once_with("റഹ്മാനിയ ഹോട്ടൽ", "ml-IN", "en-IN")
        self.assertFalse(planner.calls)

    def test_unavailable_transliteration_asks_for_catalog_spelling(self):
        for response in ("", "റഹ്മാനിയ", "https://example.test", "it"):
            with self.subTest(response=response), patch.object(sarvam, "transliterate_text", return_value=response):
                answer = PACK.start_guidance("റഹ്മാനിയ തുറന്നിട്ടുണ്ടോ എന്നറിയണം").decide(snapshot())
                self.assertEqual(answer.kind, "clarify")
                self.assertIn("English letters", answer.instruction_en)

    def test_missing_report_and_catalog_error_are_explicit(self):
        guide = PACK.start_guidance("When was this restaurant's status updated?")
        unknown = guide.decide(snapshot(*card("Needs a fresh update", "No recent report")))
        self.assertEqual(unknown.kind, "complete")
        self.assertIn("no recent report", unknown.instruction_en)
        error = snapshot(("error", "AXStaticText", "Could not load the restaurant catalog right now.",
                          (35, 200, 250, 24)), district="Alappuzha")
        decision = PACK.start_guidance("Is Cafe Point open in Alappuzha?").decide(error)
        self.assertEqual(decision.kind, "clarify")
        self.assertIn("couldn’t load", decision.instruction_en)

    def test_no_action_for_reporting_and_no_site_projection_on_other_hosts(self):
        stray = ("note", "AXStaticText", "Stale", (35, 400, 150, 18))
        self.assertEqual(PACK.start_guidance("Report a new status").decide(snapshot(stray)).kind, "unsupported")
        other = snapshot(stray, url="https://example.org/")
        self.assertFalse(PACK.matches(other))
        self.assertFalse(any(c.label == "Stale" for c in other.controls))
