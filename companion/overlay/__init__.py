"""Main-thread, click-through AppKit pointer."""

import AppKit as A
from Foundation import NSTimer

from companion.contracts import Rect
from .drawing import SketchPointerView, descriptor
from .geometry import display_index, to_appkit


def _rect(native):
    return native.origin.x, native.origin.y, native.size.width, native.size.height


class SketchPointerWindow(A.NSWindow):
    def canBecomeKeyWindow(self):
        return False

    def canBecomeMainWindow(self):
        return False

    def constrainFrameRect_toScreen_(self, rect, screen):
        # The AX target may touch the menu bar or a non-primary display edge.
        return rect


class SketchOverlay:
    def __init__(self):
        descriptor()
        self.window = None
        self.timer = None

    def show(self, frame: Rect, instruction: str, subtitle: str = "") -> None:
        self.hide()
        screens = A.NSScreen.screens()
        frames = [_rect(screen.frame()) for screen in screens]
        primary_height = frames[0][3]
        target = to_appkit(frame, primary_height)
        i = display_index(target, frames)
        sx, sy, sw, sh = frames[i]
        vx, vy, vw, vh = _rect(screens[i].visibleFrame())
        visible = (vx-sx, sy+sh-vy-vh, vw, vh)
        x, y, w, h = target
        local = (x-sx, sy+sh-y-h, w, h)
        view = SketchPointerView.alloc().initWithFrame_(((0, 0), (sw, sh)))
        view.configure(local, visible, instruction, subtitle)

        # Limit the transparent backing store to the ink and paper on this display.
        tx, ty, _, _ = local
        nx, ny, nw, nh = view.note
        left = max(0, min(tx, nx)-16)
        top = max(0, min(ty, ny)-16)
        right = min(sw, max(tx+w, nx+nw)+16)
        bottom = min(sh, max(ty+h, ny+nh)+16)
        size = (right-left, bottom-top)
        content = ((sx+left, sy+sh-bottom), size)
        win = SketchPointerWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            content, A.NSWindowStyleMaskBorderless, A.NSBackingStoreBuffered, False)
        win.setOpaque_(False)
        win.setBackgroundColor_(A.NSColor.clearColor())
        win.setLevel_(A.NSStatusWindowLevel)
        win.setIgnoresMouseEvents_(True)
        win.setHasShadow_(False)
        win.setAccessibilityElement_(False)
        win.setCollectionBehavior_(A.NSWindowCollectionBehaviorCanJoinAllSpaces |
                                   A.NSWindowCollectionBehaviorStationary |
                                   A.NSWindowCollectionBehaviorFullScreenAuxiliary)
        win.setContentView_(view)
        view.setBoundsOrigin_((left, top))
        self.window = win
        win.orderFrontRegardless()
        self.timer = NSTimer.scheduledTimerWithTimeInterval_repeats_block_(
            45, False, lambda timer: self.hide())

    def hide(self) -> None:
        if self.timer is not None:
            self.timer.invalidate()
            self.timer = None
        if self.window is not None:
            self.window.orderOut_(None)
            self.window = None
