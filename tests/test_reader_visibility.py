import unittest
from unittest.mock import patch

from companion import reader


class ReaderVisibilityTests(unittest.TestCase):
    def test_nested_scroll_ancestors_clip_through_wrappers(self):
        nodes = {
            "page": {"AXRole": "AXWebArea", "AXChildren": ["outer"]},
            "outer": {"AXRole": "AXScrollArea", "AXChildren": ["inner", "disjoint"]},
            "inner": {"AXRole": "AXScrollArea", "AXChildren": ["group"]},
            "group": {"AXRole": "AXGroup", "AXChildren": ["partial", "outside-inner"]},
            "partial": {"AXRole": "AXButton", "AXTitle": "Partly visible"},
            "outside-inner": {"AXRole": "AXButton", "AXTitle": "Inside only the outer pane"},
            "disjoint": {"AXRole": "AXScrollArea", "AXChildren": ["outside-both"]},
            "outside-both": {"AXRole": "AXButton", "AXTitle": "Inside a disjoint pane"},
        }
        frames = {"outer": (10, 20, 80, 80), "inner": (15, 5, 70, 45), "partial": (5, 15, 35, 50),
                  "outside-inner": (20, 50, 20, 10), "disjoint": (10, 120, 80, 80),
                  "outside-both": (20, 125, 20, 10)}
        with patch.object(reader, "_frame", side_effect=lambda el, get: frames[el]):
            result = reader._collect("page", lambda el, name: nodes[el].get(name), 20, (0, 0, 100, 100))
        self.assertEqual([(control.label, control.frame) for control in result.controls],
                         [("Partly visible", (15, 20, 25, 30))])
        self.assertEqual(result.below_fold_count, 0)

    def test_below_fold_counts_without_reading_labels_or_input_values(self):
        nodes = {
            "page": {"AXRole": "AXWebArea", "AXChildren": ["partial", "above", "sides", "below", "disabled",
                                                          "password", "heading", "lower-pane"]},
            "partial": {"AXRole": "AXButton", "AXTitle": "Visible edge"},
            "above": {"AXRole": "AXButton"},
            "sides": {"AXRole": "AXButton"},
            "below": {"AXRole": "AXTextField", "AXValue": "not read"},
            "disabled": {"AXRole": "AXButton", "AXEnabled": False},
            "password": {"AXRole": "AXTextField", "AXSubrole": "AXSecureTextField"},
            "heading": {"AXRole": "AXHeading", "AXTitle": "Not a control"},
            "lower-pane": {"AXRole": "AXScrollArea", "AXChildren": ["nested-below"]},
            "nested-below": {"AXRole": "AXButton"},
        }
        frames = {"partial": (80, 90, 35, 30), "above": (20, -40, 20, 10), "sides": (100, 105, 20, 10),
                  "below": (20, 100, 20, 10), "disabled": (20, 140, 20, 10), "heading": (20, 120, 20, 10),
                  "lower-pane": (20, 120, 60, 60), "nested-below": (20, 130, 20, 10)}

        def get(el, name):
            if el not in {"page", "partial", "lower-pane"}:
                self.assertIn(name, {"AXRole", "AXSubrole", "AXEnabled", "AXChildren"})
            return nodes[el].get(name)

        with patch.object(reader, "_frame", side_effect=lambda el, get: frames[el]):
            result = reader._collect("page", get, 20, (0, 0, 100, 100))
        self.assertEqual([(control.label, control.frame) for control in result.controls],
                         [("Visible edge", (80, 90, 20, 10))])
        self.assertEqual(result.below_fold_count, 2)

    def test_native_controls_clip_to_the_scroll_area_and_window(self):
        nodes = {
            "window": {"AXRole": "AXWindow", "AXChildren": ["scroll"]},
            "scroll": {"AXRole": "AXScrollArea", "AXChildren": ["button", "offscreen"]},
            "button": {"AXRole": "AXButton", "AXTitle": "Clipped"},
            "offscreen": {"AXRole": "AXButton"},
        }
        frames = {"scroll": (0, 30, 100, 100), "button": (10, 10, 20, 100), "offscreen": (10, 110, 20, 10)}
        with patch.object(reader, "_frame", side_effect=lambda el, get: frames[el]):
            result = reader._collect("window", lambda el, name: nodes[el].get(name), 10,
                                     window_frame=(0, 0, 100, 80))
        self.assertEqual([control.frame for control in result.controls], [(10, 30, 20, 50)])
        self.assertEqual(result.below_fold_count, 0)
