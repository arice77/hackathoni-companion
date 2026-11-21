import unittest
from contextlib import ExitStack
from unittest.mock import patch

from companion import reader


BOUNDS = (0, 50, 800, 600)


class WebTimeoutTests(unittest.TestCase):
    def setUp(self):
        self.clock = 10.0
        self.faults = 0
        self.content_reads = 0
        self.page = "page-one"
        self.url = "https://example.test/form"
        self.scroll = 0.2
        patches = ExitStack()
        self.addCleanup(patches.close)
        for name, value in (("is_trusted", True), ("_browser_pid", 123)):
            patches.enter_context(patch.object(reader, name, return_value=value))
        patches.enter_context(patch.object(reader, "_last_web_snapshot", None))
        patches.enter_context(patch.object(reader.time, "monotonic", side_effect=lambda: self.clock))
        patches.enter_context(patch.object(reader.AX, "AXUIElementCreateApplication", return_value="browser"))
        self.set_timeout = patches.enter_context(patch.object(reader.AX, "AXUIElementSetMessagingTimeout"))
        patches.enter_context(patch.object(reader.AX, "AXUIElementCopyAttributeValue", side_effect=self.attribute))
        self.select = patches.enter_context(patch.object(reader, "_selected_web_page", side_effect=self.select_page))
        patches.enter_context(patch.object(reader, "_collect", side_effect=self.collect))

    def select_page(self, root, get, page_title, page_url_prefix):
        return self.page, BOUNDS, BOUNDS, self.url

    def collect(self, page, get, limit, viewport, **kwargs):
        get(page, "AXChildren")
        return reader._Collection((), 0)

    def attribute(self, element, name, _out):
        if name == "AXChildren":
            self.content_reads += 1
            if self.faults:
                self.faults -= 1
                self.clock += reader.WEB_AX_TIMEOUT_S
                return reader.AX.kAXErrorCannotComplete, None
        attrs = {"AXURL": self.url, "AXParent": "scroll-area", "AXRole": "AXScrollArea",
                 "AXVerticalScrollBar": "vertical-bar", "AXValue": self.scroll}
        return 0, attrs.get(name)

    def test_slow_ax_call_gets_one_retry(self):
        self.faults = 1
        self.assertEqual(reader.snapshot(reader.SAFARI).window_title, "example.test")
        self.assertEqual(self.content_reads, 2)
        self.assertEqual(self.select.call_count, 2)
        self.assertTrue(all(args[1] <= reader.WEB_AX_TIMEOUT_S for args, _kwargs in self.set_timeout.call_args_list))

    def test_repeated_timeout_returns_same_fresh_snapshot_without_restamping(self):
        last_good = reader.snapshot(reader.SAFARI)
        self.faults = 2
        recovered = reader.snapshot(reader.SAFARI)
        self.assertIs(recovered, last_good)
        self.assertEqual(self.content_reads, 3)
        self.assertEqual(self.select.call_count, 4)

    def test_never_reuses_cache_if_tab_changes_even_at_the_same_url(self):
        reader.snapshot(reader.SAFARI)
        self.page = "different-page"
        self.faults = 2
        with self.assertRaisesRegex(reader.ReaderError, "respond in time"):
            reader.snapshot(reader.SAFARI)

    def test_never_reuses_cache_if_page_scrolls(self):
        reader.snapshot(reader.SAFARI)
        self.scroll = 0.9
        self.faults = 2
        with self.assertRaisesRegex(reader.ReaderError, "respond in time"):
            reader.snapshot(reader.SAFARI)

    def test_never_reuses_expired_snapshot(self):
        reader.snapshot(reader.SAFARI)
        self.clock += reader.WEB_CACHE_MAX_AGE_S
        self.faults = 2
        with self.assertRaisesRegex(reader.ReaderError, "respond in time"):
            reader.snapshot(reader.SAFARI)

    def test_wrong_page_is_not_retried_or_hidden_by_cache(self):
        reader.snapshot(reader.SAFARI)
        self.select.side_effect = reader.ReaderError("Wrong page")
        with self.assertRaisesRegex(reader.ReaderError, "Wrong page"):
            reader.snapshot(reader.SAFARI)
        self.assertEqual(self.select.call_count, 2)

    def test_remaining_budget_caps_the_last_ax_call(self):
        end = self.clock + 0.025
        get = reader._web_getter(self.clock, deadline=end)
        get("page", "AXURL")
        self.assertAlmostEqual(self.set_timeout.call_args.args[1], 0.025)
