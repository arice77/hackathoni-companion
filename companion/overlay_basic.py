"""Plain fallback pointer used until/unless companion.overlay.SketchOverlay is available.

Click-through, top-left -> AppKit coordinate conversion via the primary screen height.
"""

from __future__ import annotations

import objc
from AppKit import (
    NSBackingStoreBuffered, NSBezierPath, NSColor, NSFont, NSScreen, NSStatusWindowLevel, NSView, NSWindow,
    NSWindowCollectionBehaviorCanJoinAllSpaces, NSWindowCollectionBehaviorStationary,
    NSWindowStyleMaskBorderless, NSFontAttributeName, NSForegroundColorAttributeName,
)
from Foundation import NSMakeRect, NSString

from .contracts import Rect

INK = NSColor.colorWithSRGBRed_green_blue_alpha_(0x67 / 255, 0x40 / 255, 0x64 / 255, 1)
PAPER = NSColor.colorWithSRGBRed_green_blue_alpha_(1, 0xF4 / 255, 0xD8 / 255, 0.97)
PAD = 8


class _View(NSView):
    def initWithFrame_(self, frame):
        self = objc.super(_View, self).initWithFrame_(frame)
        self.text = ""
        return self

    def drawRect_(self, rect):
        b = self.bounds()
        tw, th = self.tw, self.th
        target = NSMakeRect(PAD, PAD, tw, th)
        INK.setStroke()
        p = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(target, 6, 6)
        p.setLineWidth_(3)
        p.stroke()
        attrs = {NSFontAttributeName: NSFont.systemFontOfSize_(16), NSForegroundColorAttributeName: INK}
        s = NSString.stringWithString_(self.text)
        size = s.sizeWithAttributes_(attrs)
        box = NSMakeRect(PAD, PAD + th + 6, min(size.width + 16, b.size.width - 2 * PAD), size.height + 10)
        PAPER.setFill()
        NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(box, 6, 6).fill()
        s.drawAtPoint_withAttributes_((box.origin.x + 8, box.origin.y + 5), attrs)


def to_appkit(frame: Rect) -> tuple[float, float, float, float]:
    x, y, w, h = frame
    primary_h = NSScreen.screens()[0].frame().size.height
    return x, primary_h - y - h, w, h


class BasicOverlay:
    def __init__(self):
        self.window = None

    def show(self, frame: Rect, instruction: str, subtitle: str = "") -> None:
        self.hide()
        x, y, w, h = to_appkit(frame)
        width = max(w + 2 * PAD, 640)
        height = h + 2 * PAD + 44
        win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(x - PAD, y - PAD, width, height), NSWindowStyleMaskBorderless, NSBackingStoreBuffered, False)
        win.setOpaque_(False)
        win.setBackgroundColor_(NSColor.clearColor())
        win.setLevel_(NSStatusWindowLevel)
        win.setIgnoresMouseEvents_(True)
        win.setHasShadow_(False)
        win.setCollectionBehavior_(NSWindowCollectionBehaviorCanJoinAllSpaces | NSWindowCollectionBehaviorStationary)
        view = _View.alloc().initWithFrame_(NSMakeRect(0, 0, width, height))
        view.text = instruction if not subtitle else f"{instruction}  ·  {subtitle}"
        view.tw, view.th = w, h
        win.setContentView_(view)
        win.orderFrontRegardless()
        self.window = win

    def hide(self) -> None:
        if self.window is not None:
            self.window.orderOut_(None)
            self.window = None
