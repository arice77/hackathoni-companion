import unittest
from dataclasses import replace

from companion.contracts import Control, Decision, Snapshot
from companion.validator import validate


class ViewportTests(unittest.TestCase):
    def test_native_window_and_web_viewport(self):
        control = Control("c00", "AXButton", "Target", (10, 20, 20, 20))
        snapshot = Snapshot("sample", 1.0, "com.apple.Safari", 1, "example.test", (0, 0, 100, 100), (control,))
        decision = Decision("point", "sample", "Target", control_id="c00")
        self.assertEqual(validate(decision, snapshot, now=1.0), (True, "ok"))
        visible = replace(snapshot, viewport=(0, 20, 100, 80))
        self.assertEqual(validate(decision, visible, now=1.0), (True, "ok"))
        chrome = replace(snapshot, viewport=(0, 40, 100, 60))
        self.assertEqual(validate(decision, chrome, now=1.0), (False, "target centre is outside the page viewport"))
