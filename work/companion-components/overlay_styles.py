"""Local visual experiments; leave the reference source and fixture binary unchanged."""
import math

import AppKit

THEMES = {
    "focus": {
        "ink": (0.18, 0.36, 0.90, 1.0),
        "paper": (1.0, 1.0, 1.0, 0.98),
        "font": "system",
    },
    "terminal": {
        "ink": (0.35, 0.93, 0.77, 1.0),
        "paper": (0.055, 0.085, 0.11, 0.98),
        "font": "monospace",
    },
}


def apply_style(overlay_module, name):
    if name == "original":
        return
    theme = THEMES[name]
    overlay_module.GRAPHITE = theme["ink"]

    def color(rgba):
        return AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(*rgba)

    def font(size):
        size = max(12.0, size * 0.9)
        if theme["font"] == "monospace":
            return AppKit.NSFont.monospacedSystemFontOfSize_weight_(size, AppKit.NSFontWeightMedium)
        return AppKit.NSFont.systemFontOfSize_weight_(size, AppKit.NSFontWeightSemibold)

    def smooth_path(points, rnd, width, jitter):
        path = AppKit.NSBezierPath.bezierPath()
        path.setLineWidth_(width)
        path.setLineCapStyle_(AppKit.NSLineCapStyleRound)
        path.setLineJoinStyle_(AppKit.NSLineJoinStyleRound)
        for i, point in enumerate(points):
            path.moveToPoint_(point) if i == 0 else path.lineToPoint_(point)
        return [path]

    def card(x, y, w, h, rnd, color_arg=None):
        AppKit.NSGraphicsContext.saveGraphicsState()
        shadow = AppKit.NSShadow.alloc().init()
        shadow.setShadowOffset_((0, -3))
        shadow.setShadowBlurRadius_(12)
        shadow.setShadowColor_(AppKit.NSColor.colorWithCalibratedWhite_alpha_(0, 0.18))
        shadow.set()
        path = AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(((x, y), (w, h)), 10, 10)
        color(theme["paper"]).setFill()
        path.fill()
        AppKit.NSGraphicsContext.restoreGraphicsState()

    def frame(cx, cy, rnd, style, w=84, h=68, box=None):
        if box is None:
            box = (cx - w / 2, cy - h / 2, w, h)
        x, y, w, h = box
        path = AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(((x - 6, y - 6), (w + 12, h + 12)), 9, 9)
        color(theme["ink"]).setStroke()
        path.setLineWidth_(2.2)
        path.stroke()

    def arrow(start, end, rnd, width=1.6):
        color(theme["ink"]).setStroke()
        path = smooth_path([start, end], rnd, 1.8, 0)[0]
        path.stroke()
        angle = math.atan2(end[1] - start[1], end[0] - start[0])
        head = [(end[0] - 9 * math.cos(angle - 0.45), end[1] - 9 * math.sin(angle - 0.45)),
                end,
                (end[0] - 9 * math.cos(angle + 0.45), end[1] - 9 * math.sin(angle + 0.45))]
        smooth_path(head, rnd, 1.8, 0)[0].stroke()

    original_note = overlay_module._note

    def note(x, y, text, rnd, size=19, max_w=480, color=None, underline=True, bounds=None, placed=None):
        return original_note(x, y, text, rnd, size=size, max_w=max_w, underline=False,
                             bounds=bounds, placed=placed)

    overlay_module._hand_font = font
    overlay_module._wobble_path = smooth_path
    overlay_module._draw_paper = card
    overlay_module._frame = frame
    overlay_module._arrow = arrow
    overlay_module._note = note
