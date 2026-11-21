"""Original AppKit paths and text layout for the selected plum and paper style."""

from functools import lru_cache
from math import ceil, hypot
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


def outline(target, seed):
    x, y, w, h = target
    rng = Random(seed)

    def jitter():
        return rng.uniform(-1.9, 1.9)

    left, right = x - 8, x + w + 8
    top, bottom = y - 7, y + h + 7
    corners = [(left, top), (right, top), (right, bottom), (left, bottom)]
    corners = [(a + jitter(), b + jitter()) for a, b in corners]
    path = line_path(corners[:1], 1.8)
    for (sx, sy), (ex, ey) in zip(corners, corners[1:] + corners[:1]):
        dx, dy = ex - sx, ey - sy
        first = (sx + dx * .33 + jitter(), sy + dy * .33 + jitter())
        second = (sx + dx * .67 + jitter(), sy + dy * .67 + jitter())
        path.curveToPoint_controlPoint1_controlPoint2_((ex, ey), first, second)
    path.closePath()
    return path


def draw_arrow(note, target):
    x, y, w, h = note
    tx, ty, tw, th = target
    # Select facing edges. A small horizontal offset gives the stem a bend.
    if y+h <= ty or ty+th <= y:
        above = y+h <= ty
        ex = clamp(x+w/2, tx+tw*.22, tx+tw*.78)
        ey = ty-11 if above else ty+th+11
        sx = clamp(ex+22, x+16, x+w-16)
        sy = y+h-2 if above else y+2
    else:
        left = x+w <= tx
        ex, sx = (tx-12, x+w-2) if left else (tx+tw+12, x+2)
        ey = clamp(y+h/2, ty, ty+th)
        sy = clamp(ey+12, y+10, y+h-10)
    dx, dy = ex-sx, ey-sy
    length = max(1, hypot(dx, dy))
    nx, ny = -dy/length, dx/length
    path = line_path([(sx, sy)], 1.8)
    c2 = (ex-dx*.28+nx*4, ey-dy*.28+ny*4)
    path.curveToPoint_controlPoint1_controlPoint2_((ex,ey), (sx+dx*.3+nx*4, sy+dy*.3+ny*4), c2)
    path.stroke()
    length = max(1, hypot(c2[0]-ex, c2[1]-ey))
    ax, ay = (c2[0]-ex)/length, (c2[1]-ey)/length
    line_path([(ex+ax*9-ay*4, ey+ay*9+ax*4), (ex,ey),
               (ex+ax*8+ay*4, ey+ay*8-ax*4)], 1.8).stroke()


class SketchPointerView(A.NSView):
    def isFlipped(self):
        return True

    @objc.python_method
    def configure(self, target, visible, instruction, subtitle):
        self.target = target
        self.outlines = [outline(target, seed) for seed in (31, 47)]
        self.lines = []
        for text, size in ((instruction, 25), (subtitle, 17)):
            if text:
                self.lines.append(lettering(text, size))
        natural = max((line.size().width for line in self.lines), default=0)
        width = min(visible[2]-16, 460, max(120, ceil(natural)+38))
        self.heights = [ceil(line.boundingRectWithSize_options_(
            (width-36, 10000), TEXT_OPTIONS).size.height) for line in self.lines]
        height = 26 + sum(self.heights) + 4 * max(0, len(self.lines)-1)
        self.note = place_note(target, visible, width, height)

    def drawRect_(self, dirty):
        INK.setStroke()
        for path in self.outlines:
            path.stroke()
        draw_arrow(self.note, self.target)
        x, y, w, h = self.note
        paper = line_path([(x+4,y+4), (x+w-3,y), (x+w,y+h-4), (x,y+h)], .8, True)
        PAPER.setFill()
        BORDER.setStroke()
        paper.fill()
        paper.stroke()
        top = y+12
        for line, height in zip(self.lines, self.heights):
            room = min(height, y+h-10-top)
            if room <= 0:
                break
            line.drawWithRect_options_(((x+18, top), (w-36, room)), TEXT_OPTIONS)
            top += height+4
