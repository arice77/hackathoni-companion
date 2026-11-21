import unittest
from unittest.mock import patch

from companion import reader


VIEWPORT = (10, 20, 800, 600)
INBOX = "https://mail.google.com/mail/u/0/#inbox"


class GmailPrivacyTests(unittest.TestCase):
    def collect(self, nodes, url=INBOX, *, value_fields=()):
        def get(element, attribute):
            self.assertNotIn(attribute, {"AXIdentifier", "AXDOMIdentifier"})
            if attribute == "AXValue":
                self.assertIn(element, value_fields)
            return nodes[element].get(attribute)

        with patch.object(reader, "_frame", side_effect=lambda el, get: nodes[el].get("frame", VIEWPORT)):
            return reader._gmail_collect("page", get, VIEWPORT, url).controls

    def test_inbox_aggregates_rows_and_never_descends_into_them(self):
        nodes = {
            "page": {"AXRole": "AXWebArea", "AXChildren": ["compose", "inbox", "custom-label", "table"]},
            "compose": {"AXRole": "AXButton", "AXTitle": "Compose"},
            "inbox": {"AXRole": "AXLink", "AXTitle": "Inbox (2,457 unread)"},
            "custom-label": {"AXRole": "AXLink", "AXTitle": "Latha's loan papers"},
            "table": {"AXRole": "AXTable", "AXRows": ["row-one", "row-two"],
                      "AXChildren": ["row-one", "row-two"], "frame": (15, 100, 760, 900)},
            "row-one": {"AXRole": "AXRow", "AXTitle": "Meera Nair: Clinic results", "AXChildren": ["not read"]},
            "row-two": {"AXRole": "AXRow", "AXTitle": "Fwd: Bank statement", "AXChildren": ["not read"]},
        }
        controls = self.collect(nodes)
        self.assertEqual([(control.role, control.label) for control in controls],
                         [("AXButton", "Compose"), ("AXLink", "Inbox"), ("AXTable", "Inbox: 2 messages")])
        self.assertFalse(controls[-1].enabled)
        self.assertEqual(controls[-1].frame, (15, 100, 760, 520))
        self.assertNotIn("Clinic results", repr(controls))
        self.assertNotIn("Meera Nair", repr(controls))

    def test_open_email_keeps_chrome_without_quoting_header_or_body(self):
        nodes = {
            "page": {"AXRole": "AXWebArea", "AXChildren": ["main"]},
            "main": {"AXRole": "AXGroup", "AXSubrole": "AXLandmarkMain",
                     "AXChildren": ["heading", "text", "reply", "link", "back"]},
            "heading": {"AXRole": "AXHeading", "AXTitle": "Family medical update"},
            "text": {"AXRole": "AXStaticText", "AXValue": "Dad's appointment is at 3 PM."},
            "reply": {"AXRole": "AXButton", "AXTitle": "Reply", "AXDescription": "Reply to Latha Nair"},
            "link": {"AXRole": "AXLink", "AXTitle": "Latha Nair <latha@example.test>"},
            "back": {"AXRole": "AXButton", "AXDescription": "Back to Sent Mail"},
        }
        controls = self.collect(nodes, INBOX.replace("#inbox", "#sent") + "/FMfcgzX0000000000")
        self.assertEqual([control.label for control in controls], ["Reply", "Back", "Open email"])
        self.assertEqual(controls[0].frame, VIEWPORT)
        self.assertNotIn("Latha", repr(controls))
        self.assertNotIn("appointment", repr(controls))

    def test_compose_exports_only_occupancy_of_allowlisted_fields(self):
        nodes = {
            "page": {"AXRole": "AXWebArea",
                     "AXChildren": ["to", "subject", "body", "cc", "unlabelled", "password", "send"]},
            "to": {"AXRole": "AXComboBox", "AXTitleUIElement": "to-label", "AXValue": "meenakshi@example.test"},
            "to-label": {"AXRole": "AXStaticText", "AXLabel": "To recipients"},
            "subject": {"AXRole": "AXTextField", "AXTitle": "Subject", "AXValue": "Personal tax records"},
            "body": {"AXRole": "AXTextArea", "AXTitle": "Message Body", "AXValue": "My report is attached."},
            "cc": {"AXRole": "AXTextField", "AXTitle": "Cc", "AXValue": " \t\n"},
            "unlabelled": {"AXRole": "AXTextArea", "AXValue": "Unrelated draft"},
            "password": {"AXRole": "AXTextField", "AXSubrole": "AXSecureTextField", "AXTitle": "Subject",
                         "AXValue": "Private password"},
            "send": {"AXRole": "AXButton", "AXTitle": "Send \u200e(⌘Enter)\u200e"},
        }
        controls = self.collect(nodes, INBOX + "?compose=new", value_fields={"to", "subject", "body", "cc"})
        self.assertEqual([(control.label, control.filled) for control in controls],
                         [("To", True), ("Subject", True), ("Message Body", True), ("Cc", False), ("Send", None)])
        self.assertTrue(all(control.identifier is None for control in controls))
        for text in ("meenakshi@example.test", "Personal tax records", "My report is attached.",
                     "Unrelated draft", "Private password"):
            self.assertNotIn(text, repr(controls))

    def test_recipient_chip_counts_without_exposing_address_or_reading_suggestions(self):
        nodes = {
            "page": {"AXRole": "AXWebArea", "AXChildren": ["row"]},
            "row": {"AXRole": "AXGroup", "AXChildren": ["to", "suggestions"], "frame": (40, 50, 400, 26)},
            "to": {"AXRole": "AXComboBox", "AXTitle": "To", "AXValue": "", "AXParent": "row",
                   "frame": (90, 50, 210, 23)},
            "chip": {"AXRole": "AXToken", "AXTitle": "Meenakshi <meenakshi@example.test>"},
            "suggestions": {"AXRole": "AXListBox", "AXChildren": ["suggested"]},
            "suggested": {"AXRole": "AXToken", "AXTitle": "Suggested Person"},
        }
        self.assertFalse(self.collect(nodes, value_fields={"to"})[0].filled)
        nodes["to"]["AXChildren"] = ["chip"]
        with_chip = self.collect(nodes, value_fields={"to"})
        self.assertTrue(with_chip[0].filled)
        self.assertNotIn("meenakshi@example.test", repr(with_chip))
        del nodes["to"]["AXChildren"]
        nodes["row"]["AXChildren"].append("chip")
        nodes["chip"] = {"AXRole": "AXButton", "AXTitle": "Remove meenakshi@example.test"}
        with_remove_button = self.collect(nodes, value_fields={"to"})
        self.assertTrue(with_remove_button[0].filled)
        self.assertNotIn("meenakshi@example.test", repr(with_remove_button))

    def test_snapshot_uses_private_projection_for_gmail_host(self):
        with (patch.object(reader, "is_trusted", return_value=True),
              patch.object(reader, "_browser_pid", return_value=7),
              patch.object(reader.AX, "AXUIElementCreateApplication", return_value="app"),
              patch.object(reader, "_web_getter", return_value=lambda el, name: INBOX),
              patch.object(reader, "_selected_web_page", return_value=("page", VIEWPORT, VIEWPORT, INBOX)),
              patch.object(reader, "_gmail_collect", return_value=reader._Collection((), 0)) as private,
              patch.object(reader, "_collect") as general):
            snapshot = reader.snapshot(reader.SAFARI)
        self.assertEqual(snapshot.window_title, "mail.google.com")
        private.assert_called_once()
        general.assert_not_called()

    def test_missing_browser_url_fails_closed_before_collecting_chrome(self):
        with (patch.object(reader, "is_trusted", return_value=True),
              patch.object(reader, "_browser_pid", return_value=7),
              patch.object(reader.AX, "AXUIElementCreateApplication", return_value="app"),
              patch.object(reader, "_selected_web_page", return_value=("page", VIEWPORT, VIEWPORT, "")),
              patch.object(reader, "_gmail_collect") as private, patch.object(reader, "_collect") as general):
            with self.assertRaisesRegex(reader.ReaderError, "no readable URL"):
                reader.snapshot(reader.SAFARI)
        private.assert_not_called()
        general.assert_not_called()


class PlayerSliderTests(unittest.TestCase):
    def test_web_sliders_keep_geometry_and_names_but_never_read_values(self):
        nodes = {"page": {"AXRole": "AXWebArea", "AXChildren": ["volume", "seek"]},
                 "volume": {"AXRole": "AXSlider", "AXDescription": "Volume"},
                 "seek": {"AXRole": "AXSlider", "AXTitle": "Seek slider"}}

        def get(el, name):
            self.assertNotEqual(name, "AXValue")
            return nodes[el].get(name)

        with patch.object(reader, "_frame", return_value=VIEWPORT):
            result = reader._collect("page", get, 10, VIEWPORT)
        self.assertEqual([(control.role, control.label, control.filled) for control in result.controls],
                         [("AXSlider", "Volume", None), ("AXSlider", "Seek slider", None)])
