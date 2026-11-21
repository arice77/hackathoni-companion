"""Explicit live AX probe, run with python -m tests.test_panel_ax on a trusted Mac."""

from concurrent.futures import ThreadPoolExecutor
import os

import AppKit as A
import ApplicationServices as AX
from Foundation import NSDate, NSDefaultRunLoopMode

from companion import reader
from companion.panel.render import make_sample, show_sample, STATES


def inspect_own_tree():
    queue = [AX.AXUIElementCreateApplication(os.getpid())]
    controls = []
    mode = None
    while queue:
        element = queue.pop(0)
        controls.append(tuple(reader._attr(element, key) for key in ("AXRole", "AXIdentifier", "AXTitle")))
        if controls[-1][1] == "companion-state":
            mode = reader._attr(element, "AXValue")
        queue.extend(reader._attr(element, "AXChildren") or [])
    return controls, mode


def main():
    assert reader.is_trusted()
    app = A.NSApplication.sharedApplication()
    app.setActivationPolicy_(A.NSApplicationActivationPolicyAccessory)
    app.finishLaunching()
    with ThreadPoolExecutor(1) as pool:
        for lang in ("ml", "en"):
            panel = make_sample(lang)
            panel.window.orderFrontRegardless()
            for state in STATES:
                show_sample(panel, state)
                panel.window.display()
                future = pool.submit(inspect_own_tree)
                while not future.done():
                    event = app.nextEventMatchingMask_untilDate_inMode_dequeue_(
                        A.NSEventMaskAny, NSDate.dateWithTimeIntervalSinceNow_(.01), NSDefaultRunLoopMode, True)
                    if event:
                        app.sendEvent_(event)
                controls, mode = future.result()
                assert mode == state, (mode, state)
                fields = [identifier for role, identifier, _ in controls if role == "AXTextField"]
                assert fields and fields[0] == "companion-field", (state, fields)
                assert ("AXButton", "companion-ask", "Ask" if lang == "en" else "ചോദിക്കൂ") in controls, controls
                expected = {"lang", "ask", "field", "instruction", "state"}
                if state == "guiding":
                    expected.update(("mic", "heard", "replay", "skip", "stop"))
                ids = {identifier for _, identifier, _ in controls}
                missing = {"companion-" + key for key in expected} - ids
                assert not missing, (state, missing, controls)
                print(f"{lang} {state}: field, Ask and {len(expected) - 2} other identifiers OK")
            panel.window.orderOut_(None)
            panel.window.close()


if __name__ == "__main__":
    main()
