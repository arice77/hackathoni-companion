import unittest
from unittest.mock import patch

from companion import reader
from companion.reader import is_placeholder_choice


class PlaceholderTests(unittest.TestCase):
    def test_placeholders(self):
        for v in ["Select", "---Select Classification---", "---Select My Service---", "", "  ", "Choose...", "--select--"]:
            self.assertTrue(is_placeholder_choice(v), v)

    def test_real_choices(self):
        for v in ["Flood", "Insurance & Calamity Relief Services", "Crop Insurance Compensation", "12-08-2026 (TEST FIR)"]:
            self.assertFalse(is_placeholder_choice(v), v)


class WebReaderTests(unittest.TestCase):
    def test_identifier_prefers_native_and_falls_back_to_dom(self):
        for native, expected in (("native", "native"), ("", "html-id"), (None, "html-id")):
            self.assertEqual(reader._identifier({"AXIdentifier": native, "AXDOMIdentifier": "html-id"}, dict.get),
                             expected)

    def test_intersection_clips_partial_control_and_rejects_outside(self):
        viewport = (0, 80, 100, 100)
        self.assertEqual(reader._intersection((90, 70, 20, 20), viewport), (90, 80, 10, 10))
        self.assertIsNone(reader._intersection((0, 180, 20, 20), viewport))

    def test_title_and_url_scope_the_selected_page(self):
        window_frame = (0, 0, 100, 120)
        viewport = (0, 35, 100, 85)
        url = "http://127.0.0.1:8765/"
        nodes = {
            "app": {"AXWindows": ["other", "minimized", "practice"], "AXFocusedWindow": "other"},
            "other": {"AXTitle": "Unrelated title"},
            "minimized": {"AXTitle": reader.PRACTICE_TITLE, "AXMinimized": True},
            "practice": {"AXRole": "AXWindow", "AXTitle": reader.PRACTICE_TITLE,
                         "AXChildren": ["toolbar", "different-page", "page"]},
            "toolbar": {"AXRole": "AXToolbar"},
            "different-page": {"AXRole": "AXWebArea", "AXURL": "https://example.invalid/"},
            "page": {"AXRole": "AXWebArea", "AXURL": url, "AXParent": "scroll"},
            "scroll": {"AXRole": "AXScrollArea"},
        }

        def get(el, name):
            if el in {"other", "minimized", "toolbar", "different-page"} and name == "AXChildren":
                self.fail(f"Traversed an unrelated subtree: {el}")
            return nodes[el].get(name)

        with patch.object(reader, "_frame", side_effect={"practice": window_frame, "page": (0, 20, 100, 150),
                                                       "scroll": viewport}.get):
            self.assertEqual(reader._practice_page("app", reader.PRACTICE_TITLE, url, get),
                             ("page", window_frame, viewport))
            with self.assertRaises(reader.ReaderError):
                reader._practice_page("app", reader.PRACTICE_TITLE, "http://127.0.0.1:1234/", get)

    def test_collection_clips_controls_and_keeps_only_filled_bit(self):
        nodes = {
            "page": {"AXRole": "AXWebArea", "AXChildren": ["input", "offscreen", "nested"]},
            "input": {"AXRole": "AXTextField", "AXTitle": "Business Name", "AXValue": "TEST name",
                      "AXDOMIdentifier": "business-name", "AXChildren": ["must not read"]},
            "offscreen": {"AXRole": "AXButton", "AXTitle": "Not visible"},
            "nested": {"AXRole": "AXWebArea", "AXChildren": ["must not read"]},
        }
        frames = {"input": (-5, 70, 25, 20), "offscreen": (0, 0, 20, 20)}
        with patch.object(reader, "_frame", side_effect=lambda el, get: frames.get(el)):
            controls = reader._collect("page", lambda el, name: nodes[el].get(name), 10, (0, 80, 100, 100))
        self.assertEqual(len(controls), 1)
        self.assertEqual((controls[0].identifier, controls[0].label, controls[0].frame, controls[0].filled),
                         ("business-name", "Business Name", (0, 80, 20, 10), True))

    def test_launch_guard_rejects_default_profile_and_helpers(self):
        flags = " --user-data-dir=/tmp/hackathoni-brave.ABC123 --force-renderer-accessibility=complete"
        self.assertTrue(reader._launch_isolated_brave("Brave Browser" + flags))
        for command in ("Brave Browser", "Brave Browser --user-data-dir=/tmp/other --force-renderer-accessibility=complete",
                        "Brave Browser" + flags + " --type=renderer", "Brave Browser" + flags + " --user-data-dir=other"):
            self.assertFalse(reader._launch_isolated_brave(command))


if __name__ == "__main__":
    unittest.main()
