"""Run explicitly with python -m tests.test_overlay_live on an AX-trusted Mac."""

from concurrent.futures import ThreadPoolExecutor
import os
import time

import AppKit as A
import ApplicationServices as AX
from Foundation import NSDate, NSDefaultRunLoopMode, NSObject

from companion import reader
from companion.overlay import SketchOverlay


class SketchButtonCounter(NSObject):
    def clicked_(self, sender):
        self.clicks += 1


def pump_until(ready, seconds=5):
    app = A.NSApplication.sharedApplication()
    deadline = time.monotonic() + seconds
    while not ready():
        if time.monotonic() >= deadline:
            raise TimeoutError("fixture event loop timed out")
        event = app.nextEventMatchingMask_untilDate_inMode_dequeue_(
            A.NSEventMaskAny, NSDate.dateWithTimeIntervalSinceNow_(0.025), NSDefaultRunLoopMode, True)
        if event:
            app.sendEvent_(event)
        app.updateWindows()


def read_own_button():
    root = AX.AXUIElementCreateApplication(os.getpid())
    nodes = list(reader._attr(root, "AXWindows") or [])
    while nodes:
        node = nodes.pop()
        if reader._attr(node, "AXIdentifier") == "sketch-probe-button":
            return reader._frame(node)
        nodes.extend(reader._attr(node, "AXChildren") or [])
    raise RuntimeError("AX could not find the owned button")


def main():
    assert reader.is_trusted(), "Accessibility trust is required"
    app = A.NSApplication.sharedApplication()
    app.setActivationPolicy_(A.NSApplicationActivationPolicyAccessory)
    app.finishLaunching()
    win = A.NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        ((160, 260), (310, 150)), A.NSWindowStyleMaskTitled, A.NSBackingStoreBuffered, False)
    win.setTitle_("Companion pointer test")
    win.setLevel_(A.NSFloatingWindowLevel)
    counter = SketchButtonCounter.alloc().init()
    counter.clicks = 0
    button = A.NSButton.buttonWithTitle_target_action_("Practice", counter, "clicked:")
    button.setAccessibilityIdentifier_("sketch-probe-button")
    button.setFrame_(((90, 52), (130, 36)))
    win.contentView().addSubview_(button)
    app.activateIgnoringOtherApps_(True)
    win.makeKeyAndOrderFront_(None)
    overlay = SketchOverlay()
    try:
        pump_until(lambda: win.isKeyWindow())
        with ThreadPoolExecutor(1) as pool:
            future = pool.submit(read_own_button)
            pump_until(future.done)
            frame = future.result()
        overlay.show(frame, "“Practice” തുറക്കൂ", "Open the practice form.")
        panel = overlay.window
        panel.display()
        assert win.isKeyWindow() and not panel.canBecomeKeyWindow() and panel.ignoresMouseEvents()
        view = panel.contentView()
        centre = button.convertPoint_toView_((65, 18), None)
        centre = win.convertPointToScreen_(centre)
        local = view.convertPoint_fromView_(panel.convertPointFromScreen_(centre), None)
        errors = []
        for path in view.outlines:
            assert path.containsPoint_(local)
            bounds = path.bounds()
            errors.append(max(abs(A.NSMidX(bounds)-local.x), abs(A.NSMidY(bounds)-local.y)))
        assert max(errors) <= 3, errors
        print(f"AX frame {frame}, fixture centre {tuple(centre)}, stroke centre errors {errors}", flush=True)

        # Use the system hit-test result, then post to our own app queue. A
        # foreign window, including one moved here mid-test, cannot get a click.
        def window_at_centre():
            return A.NSWindow.windowNumberAtPoint_belowWindowWithWindowNumber_(centre, 0)

        pump_until(lambda: window_at_centre() == win.windowNumber())
        recipient = window_at_centre()
        assert recipient == win.windowNumber(), (recipient, win.windowNumber(), panel.windowNumber())
        location = win.convertPointFromScreen_(centre)
        for kind in (A.NSEventTypeLeftMouseDown, A.NSEventTypeLeftMouseUp):
            event = A.NSEvent.mouseEventWithType_location_modifierFlags_timestamp_windowNumber_context_eventNumber_clickCount_pressure_(
                kind, location, 0, time.monotonic(), recipient, None, 1, 1, 1.0)
            app.postEvent_atStart_(event, False)
        pump_until(lambda: counter.clicks == 1)
        assert panel.isVisible() and win.isKeyWindow()
        print(f"WindowServer hit the fixture; button actions = {counter.clicks}", flush=True)

        old_timer = overlay.timer
        overlay.show(frame, "Again")
        assert not panel.isVisible() and not old_timer.isValid() and overlay.window.isVisible()
        timer = overlay.timer
        assert 44 <= timer.fireDate().timeIntervalSinceNow() <= 45
        started = time.monotonic()
        pump_until(lambda: overlay.window is None, seconds=48)
        assert 44 <= time.monotonic() - started <= 48
        print("Replacement, focus preservation and timer expiry passed")
    finally:
        overlay.hide()
        win.orderOut_(None)


if __name__ == "__main__":
    main()
