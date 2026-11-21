import unittest
from unittest.mock import patch

from companion import reader
from companion.contracts import Snapshot
from companion.planner_sarvam import _screen_signature


VIEWPORT = (0, 0, 160, 160)


def collect(nodes, viewport=None, frames=None):
    with patch.object(reader, "_frame", side_effect=lambda el, get: (frames or {}).get(el, (5, 5, 60, 25))):
        return {control.label: control for control in reader._collect(
            "root", lambda el, name: nodes[el].get(name), 100, viewport,
        ).controls}


def signature(controls):
    return _screen_signature(Snapshot("test", 0, "app", 1, "Form", VIEWPORT, tuple(controls.values())))


class ChoiceSetTests(unittest.TestCase):
    def test_native_radio_group_records_selection_and_changes_signature(self):
        nodes = {
            "root": {"AXRole": "AXWindow", "AXChildren": ["size"]},
            "size": {"AXRole": "AXRadioGroup", "AXTitle": "Pizza Size", "AXChildren": ["wrapper", "medium"]},
            "wrapper": {"AXRole": "AXGroup", "AXChildren": ["small"]},
            "small": {"AXRole": "AXRadioButton", "AXTitle": "Small", "AXValue": 0},
            "medium": {"AXRole": "AXRadioButton", "AXTitle": "Medium", "AXValue": 0},
        }
        empty = collect(nodes)
        nodes["medium"]["AXValue"] = 1
        chosen = collect(nodes)

        self.assertEqual(empty["Pizza Size"].role, "AXRadioGroup")
        self.assertEqual(empty["Pizza Size"].frame, (5, 5, 60, 25))
        self.assertIs(empty["Pizza Size"].filled, False)
        self.assertIs(chosen["Pizza Size"].filled, True)
        self.assertIs(chosen["Small"].filled, False)
        self.assertIs(chosen["Medium"].filled, True)
        for option in ("Small", "Medium"):
            self.assertEqual(chosen[option].group, "Pizza Size")
            self.assertEqual(empty[option].id, chosen[option].id)

        self.assertNotEqual(signature(empty), signature(chosen))

    def test_safari_fieldset_reports_group_for_radio_options(self):
        nodes = {
            "root": {"AXRole": "AXWebArea", "AXChildren": ["size", "other"]},
            "size": {"AXRole": "AXGroup", "AXSubrole": "AXFieldset", "AXTitle": "Pizza Size",
                     "AXChildren": ["large"]},
            "large": {"AXRole": "AXRadioButton", "AXTitle": "Large", "AXValue": 1},
            "other": {"AXRole": "AXRadioButton", "AXTitle": "Standalone", "AXValue": 0},
        }
        controls = collect(nodes, VIEWPORT)
        self.assertEqual(controls["Pizza Size"].role, "AXGroup")
        self.assertIs(controls["Pizza Size"].filled, True)
        self.assertEqual(controls["Large"].group, "Pizza Size")
        self.assertIs(controls["Large"].filled, True)
        self.assertIsNone(controls["Standalone"].group)

    def test_checkbox_fieldset_aggregates_ticks_including_a_scrolled_option(self):
        nodes = {
            "root": {"AXRole": "AXWebArea", "AXChildren": ["toppings"]},
            "toppings": {"AXRole": "AXGroup", "AXRoleDescription": "field set", "AXTitle": "Pizza Toppings",
                         "AXChildren": ["onion", "cheese"]},
            "onion": {"AXRole": "AXCheckBox", "AXTitle": "Onion", "AXValue": 0},
            "cheese": {"AXRole": "AXCheckBox", "AXTitle": "Extra Cheese", "AXValue": 0},
        }
        frames = {"cheese": (5, 180, 40, 20)}
        empty = collect(nodes, VIEWPORT, frames)
        nodes["cheese"]["AXValue"] = 1
        checked = collect(nodes, VIEWPORT, frames)

        self.assertIs(empty["Pizza Toppings"].filled, False)
        self.assertIs(checked["Pizza Toppings"].filled, True)
        self.assertEqual(checked["Onion"].group, "Pizza Toppings")
        self.assertIs(checked["Onion"].filled, False)
        self.assertNotIn("Extra Cheese", checked)
        self.assertNotEqual(signature(empty), signature(checked))
