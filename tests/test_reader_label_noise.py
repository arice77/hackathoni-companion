import unittest
from unittest.mock import patch

from companion import reader


def page_controls(*buttons):
    nodes = {label: {"AXRole": "AXButton", "AXTitle": label} for label in buttons}
    nodes["page"] = {"AXRole": "AXWebArea", "AXChildren": list(buttons)}
    with patch.object(reader, "_frame", return_value=(10, 10, 20, 20)):
        return reader._collect("page", lambda el, name: nodes[el].get(name), 20, (0, 0, 100, 100)).controls


class LabelNoiseTests(unittest.TestCase):
    def test_private_use_glyphs_drop_only_icon_labels(self):
        self.assertEqual([control.label for control in page_controls(
            "\ue61a", "\uf8ff \ue000\ufe0f", "\ue61a Quick Pay", "മലയാളം", "♫",
        )], ["\ue61a Quick Pay", "മലയാളം", "♫"])

    def test_carousel_dots_are_omitted_among_other_controls(self):
        controls = page_controls("1 of 5", "Slide 2 of 5", "Go to slide 3 of 5", "Quick Pay", "1–50 of 70")
        self.assertEqual([(control.id, control.label) for control in controls],
                         [("c00", "Quick Pay"), ("c01", "1–50 of 70")])

    def test_carousel_only_page_retains_one_dot(self):
        controls = page_controls("1 of 5", "2 of 5", "\ue61a")
        self.assertEqual([(control.id, control.label) for control in controls], [("c00", "1 of 5")])
