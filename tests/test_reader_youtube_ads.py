import unittest
from unittest.mock import patch

from companion import reader


VIEWPORT = (0, 0, 500, 300)


class YouTubeAdMarkerTests(unittest.TestCase):
    def collect(self, host):
        page_url = f"https://{host}/watch?v=synthetic"
        static = {
            "plain-ad": {"AXValue": "Ad"},
            "position": {"AXDescription": "Ad 1 of 2"},
            "timer": {"AXValue": "Ad · 0:15"},
            "sponsor": {"AXTitle": "Sponsored"},
            "advertiser": {"AXValue": "Sponsored by a company"},
            "prose": {"AXValue": "An ordinary video caption"},
            "invalid": {"AXValue": "Ad 7 of 2"},
            "hidden": {"AXValue": "Ad"},
        }
        nodes = {
            "page": {"AXRole": "AXWebArea", "AXURL": page_url, "AXChildren": [*static, "skip"]},
            **{name: {"AXRole": "AXStaticText", "AXDOMIdentifier": "private-name", **attributes}
               for name, attributes in static.items()},
            "skip": {"AXRole": "AXButton", "AXTitle": "Skip ad"},
        }

        def get(element, attribute):
            if element in static:
                self.assertNotIn(attribute, {"AXIdentifier", "AXDOMIdentifier"})
            if element == "hidden":
                self.assertNotIn(attribute, {"AXValue", "AXTitle", "AXDescription", "AXLabel"})
            return nodes[element].get(attribute)

        def frame(element, _get):
            if element == "hidden":
                return (10, 350, 110, 18)
            return VIEWPORT if element == "page" else (10, 20, 110, 18)

        view = reader._WebView("page", VIEWPORT, VIEWPORT, page_url, ())
        with patch.object(reader, "_frame", side_effect=frame):
            return reader._read_web_snapshot(view, reader.SAFARI, 123, get)

    def test_youtube_keeps_only_visible_canonical_ad_text_and_existing_actions(self):
        snap = self.collect("www.youtube.com")
        self.assertEqual([(c.role, c.label, c.enabled) for c in snap.controls], [
            ("AXStaticText", "Ad", False), ("AXStaticText", "Ad 1 of 2", False),
            ("AXStaticText", "Ad", False), ("AXStaticText", "Sponsored", False),
            ("AXButton", "Skip ad", True),
        ])
        self.assertTrue(all(c.identifier is None and c.frame[2:] == (110, 18) for c in snap.controls))
        self.assertEqual(snap.below_fold_count, 0)

    def test_other_hosts_keep_dropping_static_text(self):
        snap = self.collect("example.org")
        self.assertEqual([control.label for control in snap.controls], ["Skip ad"])
