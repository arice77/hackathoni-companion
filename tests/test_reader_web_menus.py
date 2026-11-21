import unittest
from unittest.mock import patch

from companion import reader


class WebMenuTests(unittest.TestCase):
    def test_visible_player_menu_entries_are_retained_without_reading_values(self):
        nodes = {
            "page": {"AXRole": "AXWebArea", "AXChildren": ["settings", "menu"]},
            "settings": {"AXRole": "AXPopUpButton", "AXTitle": "Settings", "AXValue": ""},
            "menu": {"AXRole": "AXMenu", "AXChildren": ["speed", "submenu", "hidden"]},
            "speed": {"AXRole": "AXMenuItem", "AXDescription": "Playback speed Normal"},
            "submenu": {"AXRole": "AXMenu", "AXChildren": ["quality", "captions"]},
            "quality": {"AXRole": "AXMenuItemRadio", "AXTitle": "720p"},
            "captions": {"AXRole": "AXMenuItemCheckbox", "AXTitle": "English"},
            "hidden": {"AXRole": "AXMenuItem", "AXTitle": "Hidden choice"},
        }

        def get(el, name):
            if name == "AXValue":
                self.assertEqual(el, "settings")
            return nodes[el].get(name)

        def frame(el, get):
            return (10, 200, 100, 20) if el == "hidden" else (10, 10, 100, 20)

        with patch.object(reader, "_frame", side_effect=frame):
            result = reader._collect("page", get, 20, (0, 0, 200, 150))
        self.assertEqual([(control.role, control.label) for control in result.controls], [
            ("AXPopUpButton", "Settings"), ("AXMenuItem", "Playback speed Normal"),
            ("AXMenuItemRadio", "720p"), ("AXMenuItemCheckbox", "English"),
        ])
