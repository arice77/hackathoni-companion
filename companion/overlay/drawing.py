"""Original AppKit paths and text layout for the selected plum and paper style."""

from functools import lru_cache
from math import ceil, cos, hypot, radians, sin
from pathlib import Path
from random import Random

import AppKit as A
import CoreText as CT
from Foundation import NSAttributedString, NSURL
import objc

from .geometry import clamp, place_note

FONT_FILE = Path(__file__).resolve().parents[2] / "work/companion-style-preview/assets/ShantellSans.ttf"
TEXT_OPTIONS = A.NSStringDrawingUsesLineFragmentOrigin | A.NSStringDrawingUsesFontLeading


def color(red, green, blue):
    return A.NSColor.colorWithSRGBRed_green_blue_alpha_(red/255, green/255, blue/255, 1)


INK = color(103, 64, 100)
PAPER = color(255, 244, 216)
BORDER = color(217, 200, 166)


@lru_cache(maxsize=1)
def descriptor():
    url = NSURL.fileURLWithPath_(str(FONT_FILE))
    ok, error = CT.CTFontManagerRegisterFontsForURL(url, CT.kCTFontManagerScopeProcess, None)
    if not ok and error.code() != CT.kCTFontManagerErrorAlreadyRegistered:
        raise RuntimeError(str(error))
    source = CT.CTFontManagerCreateFontDescriptorsFromURL(url)[0]
    name = CT.CTFontDescriptorCopyAttribute(source, CT.kCTFontNameAttribute)
    axes = {b"INFM": 35, b"BNCE": 16, b"wght": 500}
    attributes = {
        A.NSFontNameAttribute: name,
        A.NSFontVariationAttribute: {int.from_bytes(tag, "big"): value for tag, value in axes.items()},
    }
    for font_name in ("MalayalamSangamMN", "MalayalamMN"):
        fallback = A.NSFont.fontWithName_size_(font_name, 25)
        if fallback is not None:
            attributes[A.NSFontCascadeListAttribute] = [fallback.fontDescriptor()]
            break
    return A.NSFontDescriptor.fontDescriptorWithFontAttributes_(attributes)


def lettering(text, size):
    font = A.NSFont.fontWithDescriptor_size_(descriptor(), size)
    attrs = {A.NSFontAttributeName: font, A.NSForegroundColorAttributeName: INK}
    return NSAttributedString.alloc().initWithString_attributes_(text, attrs)


def line_path(points, width, close=False):
    path = A.NSBezierPath.bezierPath()
    path.setLineWidth_(width)
    path.setLineJoinStyle_(A.NSLineJoinStyleRound)
    path.setLineCapStyle_(A.NSLineCapStyleRound)
    path.moveToPoint_(points[0])
    for point in points[1:]:
        path.lineToPoint_(point)
    if close:
        path.closePath()
    return path


ROUGHNESS = 1.9
PAPER_ANGLE = -2
TILT_SIN = abs(sin(radians(PAPER_ANGLE)))
TILT_COS = cos(radians(PAPER_ANGLE))
PAD_X, PAD_Y = 12, 7


def outline(target, seed, lean):
    """One pen pass. Bow each side, then extend its tangents beyond the corners."""
    x, y, w, h = target
    rng = Random(seed)
    left, right = x - 8, x + w + 8
    top, bottom = y - 7, y + h + 7
    # Each pass starts at slightly different corners. A modest offset plus
    # independent errors lets the lines meet at some corners and splay at others.
    corners = [(left, top), (right, top), (right, bottom), (left, bottom)]
    corners = [(a + lean * .85 + rng.uniform(-ROUGHNESS, ROUGHNESS),
                b + lean * .85 + rng.uniform(-ROUGHNESS, ROUGHNESS)) for a, b in corners]
    path = line_path(corners[:1], 1.8)
    tails = []
    for (sx, sy), (ex, ey) in zip(corners, corners[1:] + corners[:1]):
        dx, dy = ex - sx, ey - sy
        length = hypot(dx, dy)
        ux, uy = dx / length, dy / length
        bow = min(1.55 * ROUGHNESS, length * .035) * rng.uniform(.8, 1.2) * lean
        first = (sx + dx * .30 - uy * bow, sy + dy * .30 + ux * bow)
        second = (sx + dx * .72 - uy * bow, sy + dy * .72 + ux * bow)
        path.curveToPoint_controlPoint1_controlPoint2_((ex, ey), first, second)
        before, after = rng.uniform(.4, 1.6), rng.uniform(1.4, 4.2)
        tails.extend([((sx - ux * before, sy - uy * before), (sx, sy)),
                      ((ex, ey), (ex + ux * after, ey + uy * after))])
    path.closePath()
    for start, end in tails:
        path.moveToPoint_(start)
        path.lineToPoint_(end)
    return path


def arrow_ends(note, target):
    x, y, w, h = note
    tx, ty, tw, th = target
    # Start just inside the paper. The last few points are covered by the
    # rotated card, so the ink meets its edge cleanly in either direction.
    if y + h <= ty or ty + th <= y:
        above = y + h <= ty
        points_left = x + w / 2 >= tx + tw / 2
        inset = min(30, tw * .25)
        ex = tx + tw - inset if points_left else tx + inset
        reach = 46 if points_left else -46
        sx = clamp(ex + reach, x + 10, x + w - 10)
        # A control can extend beyond both screen edges. Choose a reachable
        # point on its border after the paper has been clamped to this display.
        ex = clamp(sx - reach, tx + inset, tx + tw - inset)
        sy = y + h - 11 if above else y + 11
        ey = ty - 11 if above else ty + th + 11
    else:
        left = x + w <= tx
        ex, sx = (tx - 12, x + w - 6) if left else (tx + tw + 12, x + 6)
        ey = clamp(y + h / 2, ty, ty + th)
        sy = clamp(ey + 23, y + 10, y + h - 10)
    return (sx, sy), (ex, ey)


def draw_arrow(note, target):
    start, end = arrow_ends(note, target)
    sx, sy = start
    ex, ey = end
    dx, dy = ex - sx, ey - sy
    length = max(1, hypot(dx, dy))
    nx, ny = -dy / length, dx / length
    path = line_path([start], 1.8)
    first = (sx + dx * .3 + nx * 5, sy + dy * .3 + ny * 5)
    second = (ex - dx * .28 + nx * 4, ey - dy * .28 + ny * 4)
    path.curveToPoint_controlPoint1_controlPoint2_(end, first, second)
    path.stroke()
    length = max(1, hypot(second[0] - ex, second[1] - ey))
    ax, ay = (second[0] - ex) / length, (second[1] - ey) / length
    line_path([(ex + ax * 10 - ay * 4, ey + ay * 10 + ax * 4), end,
               (ex + ax * 8 + ay * 4, ey + ay * 8 - ax * 4)], 1.8).stroke()


class SketchPointerView(A.NSView):
    def isFlipped(self):
        return True

    @objc.python_method
    def configure(self, target, visible, instruction, subtitle):
        self.target = target
        self.outlines = [outline(target, 31, 1), outline(target, 47, -.8)]
        self.lines = [lettering(text, size) for text, size in ((instruction, 25), (subtitle, 17))
                      if text.strip()]

        # Reserve room for rotation before measuring. Use the widest actual
        # wrapped line so short translations and single-word prompts fit snugly.
        available_w, available_h = visible[2] - 20, visible[3] - 20
        max_width = min(420, available_w - min(available_h, 420) * TILT_SIN)
        measure_width = max(1, max_width - 2 * PAD_X)
        sizes = [line.boundingRectWithSize_options_((measure_width, 10000), TEXT_OPTIONS).size
                 for line in self.lines]
        self.text_width = min(measure_width, ceil(max((size.width for size in sizes), default=0)) + 1)
        self.heights = [ceil(size.height) for size in sizes]
        width = self.text_width + 2 * PAD_X
        height = 2 * PAD_Y + sum(self.heights) + 2 * max(0, len(sizes) - 1)
        # Keep even an unusually tall note's rotated paper inside the screen.
        height = min(height, (available_h - width * TILT_SIN) / TILT_COS,
                     (available_w - width * TILT_COS) / TILT_SIN)
        self.paper_size = width, height
        self.note = place_note(target, visible, width * TILT_COS + height * TILT_SIN,
                               height * TILT_COS + width * TILT_SIN)

    def drawRect_(self, dirty):
        INK.setStroke()
        for path in self.outlines:
            path.stroke()
        draw_arrow(self.note, self.target)

        x, y, nw, nh = self.note
        w, h = self.paper_size
        A.NSGraphicsContext.saveGraphicsState()
        try:
            transform = A.NSAffineTransform.transform()
            transform.translateXBy_yBy_(x + nw / 2, y + nh / 2)
            transform.rotateByDegrees_(PAPER_ANGLE)
            transform.translateXBy_yBy_(-w / 2, -h / 2)
            transform.concat()
            paper = line_path([(3, 1), (w - 2, 0), (w, h - 1), (0, h)], .8, True)
            A.NSGraphicsContext.saveGraphicsState()
            try:
                shadow = A.NSShadow.alloc().init()
                shadow.setShadowColor_(A.NSColor.colorWithSRGBRed_green_blue_alpha_(.28, .18, .10, .24))
                shadow.setShadowOffset_((0, -3))
                shadow.setShadowBlurRadius_(5)
                shadow.set()
                PAPER.setFill()
                paper.fill()
            finally:
                A.NSGraphicsContext.restoreGraphicsState()
            BORDER.setStroke()
            paper.stroke()
            top = PAD_Y
            for line, height in zip(self.lines, self.heights):
                room = min(height, h - PAD_Y - top)
                if room <= 0:
                    break
                line.drawWithRect_options_(((PAD_X, top), (self.text_width, room)), TEXT_OPTIONS)
                top += height + 2
        finally:
            A.NSGraphicsContext.restoreGraphicsState()
