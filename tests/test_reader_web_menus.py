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

    def speed_panel(self, value, *, host="www.youtube.com", open_panel=True):
        viewport = (0, 0, 500, 400)
        url = f"https://{host}/watch?v=test-video"
        nodes = {
            "page": {"AXRole": "AXWebArea", "AXURL": url, "AXChildren": ["seek", "volume", "other", "panel"]},
            "seek": {"AXRole": "AXSlider", "AXTitle": "Seek slider", "AXValue": 30},
            "volume": {"AXRole": "AXSlider", "AXTitle": "Volume", "AXValue": 0.5},
            "other": {"AXRole": "AXSlider", "AXValue": 1},
            "panel": {"AXRole": "AXGroup", "AXChildren": ["speed", "decrease", "increase"]},
            "speed": {"AXRole": "AXSlider", "AXValue": value, "AXDOMIdentifier": "speed-test"},
            "decrease": {"AXRole": "AXButton", "AXTitle": "Decrease playback speed 0.05"},
            "increase": {"AXRole": "AXButton", "AXTitle": "Increase playback speed 0.05"},
        }
        frames = {
            "seek": (90, 250, 150, 16),
            "volume": (30, 175, 80, 20),
            "other": (120, 60, 100, 16),
            "speed": (120, 170, 100, 16),
            "decrease": (92, 168, 25, 20),
            "increase": (225, 168 if open_panel else 450, 25, 20),
        }
        reads = []

        def get(element, name):
            if name == "AXValue":
                reads.append(element)
            return nodes[element].get(name)

        view = reader._WebView("page", viewport, viewport, url, ())
        with patch.object(reader, "_frame", side_effect=lambda element, _: frames.get(element, viewport)):
            snap = reader._read_web_snapshot(view, reader.SAFARI, 123, get)
        return snap, reads

    def test_youtube_only_reads_unlabelled_slider_between_visible_speed_steppers(self):
        snap, reads = self.speed_panel("0.75")
        self.assertEqual(reads, ["speed"])
        self.assertEqual([control.label for control in snap.controls if control.role == "AXSlider"],
                         ["Seek slider", "Volume", "", "Playback speed slider 0.75"])

        cases = ({"host": "example.org"}, {"host": "youtube.com.example.org"}, {"open_panel": False})
        for options in cases:
            with self.subTest(options=options):
                snap, reads = self.speed_panel(0.75, **options)
                self.assertEqual(reads, [])
                self.assertEqual(next(c.label for c in snap.controls if c.identifier == "speed-test"), "")

    def test_speed_value_is_formatted_and_invalid_speed_slider_is_dropped(self):
        for value, expected in ((0.05, "0.05"), (0.756, "0.76"), (1.0, "1"), (" 4.00 ", "4")):
            with self.subTest(value=value):
                snap, reads = self.speed_panel(value, host="m.youtube.com")
                self.assertEqual(reads, ["speed"])
                slider = next(c for c in snap.controls if c.label.startswith("Playback speed slider"))
                self.assertEqual(slider.label, f"Playback speed slider {expected}")
                self.assertIsNone(slider.identifier)  # a value change must change the app's screen signature

        for value in ("0.75×", "1 secret", 0.049, 4.01, True, float("nan"), None):
            with self.subTest(value=value):
                snap, reads = self.speed_panel(value)
                self.assertEqual(reads, ["speed"])
                self.assertFalse(any(c.identifier == "speed-test" or c.label.startswith("Playback speed slider")
                                     for c in snap.controls))
