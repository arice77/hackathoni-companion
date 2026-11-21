"""Live launch and typed-question focus probe. Run with python -m tests.test_panel_focus."""

from pathlib import Path
import subprocess
import sys
import time

import AppKit as A
import ApplicationServices as AX

from companion import reader
from scripts.qa.run import acquire_lock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/qa/checks"))
import _web


def main():
    assert reader.is_trusted()
    lock = acquire_lock()
    assert lock is not None
    app = None
    try:
        assert _web.open_fresh_page(_web.load_drive()) is None
        workspace = A.NSWorkspace.sharedWorkspace()

        def safari_front():
            return workspace.frontmostApplication().bundleIdentifier() == "com.apple.Safari"

        assert safari_front()
        app = subprocess.Popen([sys.executable, "-m", "companion.app", "--task", "web_practice",
                                "--mute", "--lang", "en"], cwd=ROOT, stdout=subprocess.DEVNULL)
        for _ in range(25):
            time.sleep(.1)
            assert app.poll() is None and safari_front(), "Safari lost focus during launch"
        print("Safari frontmost for all 25 launch samples")

        # Send AX input only to the Companion process we just started.
        queue = [AX.AXUIElementCreateApplication(app.pid)]
        controls = {}
        while queue:
            el = queue.pop(0)
            ident = reader._attr(el, "AXIdentifier")
            if ident:
                controls[ident] = el
            queue.extend(reader._attr(el, "AXChildren") or [])
        field, ask = controls["companion-field"], controls["companion-ask"]
        assert reader._attr(ask, "AXTitle") == "Ask"
        assert AX.AXUIElementSetAttributeValue(field, "AXFocused", True) == 0
        assert AX.AXUIElementSetAttributeValue(field, "AXValue", "Help me fill this practice form") == 0
        assert reader._attr(field, "AXValue") == "Help me fill this practice form"
        assert AX.AXUIElementPerformAction(ask, "AXPress") == 0
        for _ in range(10):
            time.sleep(.1)
            assert safari_front(), "Companion activated during AX input"
        print("Typed question submitted to the panel; Safari frontmost for all 10 subsequent samples")
    finally:
        if app is not None:
            app.terminate()
            app.wait(timeout=8)
        _web.close_and_settle()


if __name__ == "__main__":
    main()
