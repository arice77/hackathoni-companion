import time
import unittest
from unittest.mock import Mock, patch

from companion import reader
from companion.contracts import Control, Snapshot
from companion.planner import ScriptedPlanner
from companion.reader import is_placeholder_choice
from companion.tasks import load


class PlaceholderTests(unittest.TestCase):
    def test_placeholders(self):
        for v in ["Select", "---Select Classification---", "---Select My Service---", "", "  ", "Choose...", "--select--"]:
            self.assertTrue(is_placeholder_choice(v), v)

    def test_real_choices(self):
        for v in ["Flood", "Insurance & Calamity Relief Services", "Crop Insurance Compensation", "12-08-2026 (TEST FIR)"]:
            self.assertFalse(is_placeholder_choice(v), v)


class NativeReaderTests(unittest.TestCase):
    @staticmethod
    def instance_at(path):
        app = Mock()
        app.bundleURL.return_value.path.return_value = str(path)
        return app

    def test_prefers_this_worktree_and_matches_path_components(self):
        sibling = reader.REPO_ROOT.with_name(reader.REPO_ROOT.name + "-sibling")
        other = self.instance_at(sibling / "apps/native-fixture/Fixture.app")
        local = self.instance_at(reader.REPO_ROOT / "apps/native-fixture/Fixture.app")
        finder = Mock()
        finder.runningApplicationsWithBundleIdentifier_.return_value = [other, local]
        with patch.object(reader, "NSRunningApplication", finder):
            self.assertIs(reader.find_app("in.hackathoni.native-fixture"), local)
            self.assertIs(reader.find_app("example.native-fixture"), local)
            finder.runningApplicationsWithBundleIdentifier_.return_value = [other]
            self.assertIsNone(reader.find_app("in.hackathoni.native-fixture"))

    def test_external_apps_fall_back_to_first_instance(self):
        safari = self.instance_at("/Applications/Safari.app")
        alternate = self.instance_at("/Applications/Safari Alternate.app")
        finder = Mock()
        finder.runningApplicationsWithBundleIdentifier_.return_value = [safari, alternate]
        with patch.object(reader, "NSRunningApplication", finder):
            self.assertIs(reader.find_app(reader.SAFARI), safari)
            finder.runningApplicationsWithBundleIdentifier_.return_value = []
            self.assertIsNone(reader.find_app(reader.SAFARI))


class WebReaderTests(unittest.TestCase):
    def test_identifier_prefers_native_and_falls_back_to_dom(self):
        for native, expected in (("native", "native"), ("", "html-id"), (None, "html-id")):
            self.assertEqual(reader._identifier({"AXIdentifier": native, "AXDOMIdentifier": "html-id"}, dict.get),
                             expected)

    def test_intersection_clips_partial_control_and_rejects_outside(self):
        viewport = (0, 80, 100, 100)
        self.assertEqual(reader._intersection((90, 70, 20, 20), viewport), (90, 80, 10, 10))
        self.assertIsNone(reader._intersection((0, 180, 20, 20), viewport))

    def test_only_selected_front_page_and_optional_constraints(self):
        window_frame = (0, 0, 100, 120)
        viewport = (0, 35, 100, 85)
        url = "http://127.0.0.1:8765/"
        nodes = {
            "app": {"AXWindows": ["other", "practice"], "AXFocusedWindow": "practice"},
            "practice": {"AXRole": "AXWindow", "AXTitle": reader.PRACTICE_TITLE,
                         "AXChildren": ["toolbar", "outer-scroll"]},
            "toolbar": {"AXRole": "AXToolbar"},
            "outer-scroll": {"AXRole": "AXScrollArea", "AXChildren": ["inner-scroll"]},
            "inner-scroll": {"AXRole": "AXScrollArea", "AXChildren": ["wrapper"]},
            "wrapper": {"AXRole": "AXGroup", "AXChildren": ["page"]},
            "page": {"AXRole": "AXWebArea", "AXURL": url},
        }

        def get(el, name):
            if el == "other" or (el == "toolbar" and name == "AXChildren") or name == "AXWindows":
                self.fail(f"Read outside the front page: {el} {name}")
            return nodes[el].get(name)

        frames = {"practice": window_frame, "page": (0, 20, 100, 150),
                  "outer-scroll": (0, 35, 100, 95), "inner-scroll": (0, 25, 100, 110)}
        with patch.object(reader, "_frame", side_effect=lambda el, get: frames[el]):
            self.assertEqual(reader._selected_web_page("app", get), ("page", window_frame, viewport, url))
            self.assertEqual(reader._selected_web_page("app", get, reader.PRACTICE_TITLE, url),
                             ("page", window_frame, viewport, url))
            with self.assertRaisesRegex(reader.ReaderError, "window doesn't match"):
                reader._selected_web_page("app", get, "Unrelated title")
            with self.assertRaisesRegex(reader.ReaderError, "page doesn't match"):
                reader._selected_web_page("app", get, page_url_prefix="http://127.0.0.1:1234/")

    def test_url_prefix_cannot_match_a_different_host(self):
        self.assertFalse(reader._url_matches("https://example.test.evil.test/page", "https://example.test"))
        self.assertTrue(reader._url_matches("https://example.test/page?private=1", "https://example.test/page"))
        self.assertEqual(reader._host("https://someone:secret@example.test/page?private=1"), "example.test")

    def test_elapsed_budget_fails_before_ax_call(self):
        get = reader._web_getter(time.monotonic() - reader.WEB_READ_BUDGET_S)
        with self.assertRaisesRegex(reader.ReaderError, "time budget"):
            get("unreadable", "AXRole")

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
            controls = reader._collect("page", lambda el, name: nodes[el].get(name), 10, (0, 80, 100, 100)).controls
        self.assertEqual(len(controls), 1)
        self.assertEqual((controls[0].identifier, controls[0].label, controls[0].frame, controls[0].filled),
                         ("business-name", "Business Name", (0, 80, 20, 10), True))

    def test_launch_guard_rejects_default_profile_and_helpers(self):
        flags = " --user-data-dir=/tmp/hackathoni-brave.ABC123 --force-renderer-accessibility=complete"
        self.assertTrue(reader._launch_isolated_brave("Brave Browser" + flags))
        for command in ("Brave Browser", "Brave Browser --user-data-dir=/tmp/other --force-renderer-accessibility=complete",
                        "Brave Browser" + flags + " --type=renderer", "Brave Browser" + flags + " --user-data-dir=other"):
            self.assertFalse(reader._launch_isolated_brave(command))

    def test_secure_fields_are_not_collected_or_read_for_values(self):
        nodes = {
            "page": {"AXRole": "AXWebArea", "AXChildren": ["role-password", "subrole-password"]},
            "role-password": {"AXRole": "AXSecureTextField"},
            "subrole-password": {"AXRole": "AXTextField", "AXSubrole": "AXSecureTextField"},
        }

        def get(el, name):
            if el != "page" and name not in {"AXRole", "AXSubrole"}:
                self.fail(f"Accessed a password field's {name}")
            return nodes[el].get(name)

        self.assertEqual(reader._collect("page", get, 10, (0, 0, 100, 100)).controls, ())

    def test_generic_headings_and_labels_are_capped_and_prose_is_not_read(self):
        nodes = {
            "page": {"AXRole": "AXWebArea", "AXChildren": ["heading", "prose", "button", "long"]},
            "heading": {"AXRole": "AXHeading", "AXTitle": "Go to https://example.test/page?secret=1"},
            "prose": {"AXRole": "AXStaticText", "AXValue": "Private prose"},
            "button": {"AXRole": "AXButton", "AXTitle": "Next"},
            "long": {"AXRole": "AXLink", "AXTitle": "Details " * 100},
        }

        def get(el, name):
            self.assertFalse(el == "prose" and name == "AXValue")
            return nodes[el].get(name)

        with patch.object(reader, "_frame", return_value=(0, 25, 50, 10)):
            controls = reader._collect("page", get, 10, (0, 0, 100, 100)).controls
        self.assertEqual([control.id for control in controls], ["c00", "c01", "c02"])
        self.assertEqual([control.label for control in controls[:2]], ["Go to example.test", "Next"])
        self.assertEqual(len(controls[2].label), reader.MAX_WEB_LABEL_LENGTH)

    def test_input_label_does_not_echo_value_even_if_title_does(self):
        nodes = {
            "page": {"AXRole": "AXWebArea", "AXChildren": ["input", "time"]},
            "input": {"AXRole": "AXTextField", "AXTitle": "Internal reference", "AXValue": "Internal reference",
                      "AXDescription": "Business Name"},
            "time": {"AXRole": "AXDateTimeArea", "AXTitle": "Preferred delivery time:"},
        }

        def get(el, name):
            self.assertFalse(el == "time" and name in {"AXValue", "AXChildren"})
            return nodes[el].get(name)

        with patch.object(reader, "_frame", return_value=(0, 25, 50, 10)):
            field, time_picker = reader._collect("page", get, 10, (0, 0, 100, 100)).controls
        self.assertEqual((field.label, field.filled), ("Business Name", True))
        self.assertEqual((time_picker.label, time_picker.filled), ("Preferred delivery time:", None))

    def test_web_any_has_no_script_or_page_constraints(self):
        task = load("web_any")
        self.assertIsNone(task.page_title)
        self.assertIsNone(task.page_url_prefix)
        self.assertTrue(task.intent.search("എങ്ങനെ?"))
        self.assertFalse(task.intent.search(" \n"))
        status = Control("c00", "AXStaticText", "Training complete", (1, 1, 50, 24), identifier="status")
        snapshot = Snapshot("sample", time.time(), task.bundle_id, 1, "example.test", (0, 0, 100, 100), (status,))
        self.assertEqual(ScriptedPlanner(task).decide("How do I fill this?", snapshot).kind, "unsupported")


if __name__ == "__main__":
    unittest.main()
