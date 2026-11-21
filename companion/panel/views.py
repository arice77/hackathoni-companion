"""Native controls and ink treatments for the companion's paper panel."""

from math import ceil
from functools import lru_cache

import AppKit as A
import Quartz as Q
import objc
from Foundation import NSAttributedString

from companion.overlay.drawing import INK, PAPER, TEXT_OPTIONS, color, descriptor, line_path, outline

WASH = color(251, 241, 219)
SHEET = color(255, 251, 240)
MUTED = color(103, 81, 91)
HAIR = color(167, 137, 151)
RULE = color(222, 204, 178)


@lru_cache(maxsize=20)
def hand(size):
    return A.NSFont.fontWithDescriptor_size_(descriptor(), size)


def text_style(value, size, *, ink=INK, system=False, center=False, leading=0):
    paragraph = A.NSMutableParagraphStyle.alloc().init()
    paragraph.setAlignment_(A.NSTextAlignmentCenter if center else A.NSTextAlignmentLeft)
    paragraph.setLineBreakMode_(A.NSLineBreakByWordWrapping)
    if leading:
        paragraph.setMinimumLineHeight_(leading)
    font = A.NSFont.systemFontOfSize_(size) if system else hand(size)
    return NSAttributedString.alloc().initWithString_attributes_(value, {
        A.NSFontAttributeName: font, A.NSForegroundColorAttributeName: ink,
        A.NSParagraphStyleAttributeName: paragraph})


def text_height(value, width):
    return ceil(value.boundingRectWithSize_options_((width, 100000), TEXT_OPTIONS).size.height) + 2


def rounded(x, y, w, h, radius):
    return A.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(((x, y), (w, h)), radius, radius)


def fill(path, tint):
    tint.setFill()
    path.fill()


def stroke(path, tint, weight):
    tint.setStroke()
    path.setLineWidth_(weight)
    path.stroke()


def ink_disc(x, y, w, h, tint):
    fill(A.NSBezierPath.bezierPathWithOvalInRect_(((x + 3, y + 3), (w - 6, h - 6))), tint)
    stroke(A.NSBezierPath.bezierPathWithOvalInRect_(((x + 1, y + 4), (w - 4, h - 6))), tint, 1.4)


def paper_edge(rect, base, edge):
    x, y, w, h = rect
    polygon = line_path([(x + 1, y + 2), (x + w - 2, y), (x + w, y + h - 2), (x, y + h)], 1, True)
    fill(polygon, base)
    # outline() includes the target's 8/7 pt breathing room.
    for seed, lean, weight in ((31, 1, 1.15), (47, -.8, .7)):
        stroke(outline((x + 8, y + 7, w - 16, h - 14), seed, lean), edge, weight)


@lru_cache(maxsize=48)
def symbol(name, size, tint):
    image = A.NSImage.imageWithSystemSymbolName_accessibilityDescription_(name, None)
    weight = A.NSImageSymbolConfiguration.configurationWithPointSize_weight_(size, A.NSFontWeightRegular)
    palette = A.NSImageSymbolConfiguration.configurationWithPaletteColors_([tint])
    return image.imageWithSymbolConfiguration_(weight.configurationByApplyingConfiguration_(palette))


def draw_symbol(name, size, tint, cx, cy):
    glyph = symbol(name, size, tint)
    w, h = glyph.size()
    glyph.drawInRect_fromRect_operation_fraction_respectFlipped_hints_(
        ((cx - w / 2, cy - h / 2), (w, h)), A.NSZeroRect,
        A.NSCompositingOperationSourceOver, 1, True, None)


class PaperPanelWindow(A.NSPanel):
    def canBecomeKeyWindow(self):
        return True

    def canBecomeMainWindow(self):
        return False


class PaperSurface(A.NSView):
    def isFlipped(self):
        return True

    def mouseDownCanMoveWindow(self):
        return True

    def drawRect_(self, dirty):
        w, h = self.bounds().size
        paper_edge((4, 4, w - 8, h - 8), PAPER, color(152, 116, 134))
        stroke(line_path([(24, 69), (w - 24, 69)], 1), RULE, .8)
        if self.ticket:
            paper_edge(self.ticket, SHEET, INK)
        if self.chip_box:
            chip = rounded(*self.chip_box, 6)
            fill(chip, WASH)
            stroke(chip, RULE, .75)
        if self.field_box:
            path = rounded(*self.field_box, 8)
            fill(path, SHEET)
            stroke(path, HAIR, .9)
        if self.badge:
            x, y = self.badge
            ink_disc(x - 38, y - 38, 76, 76, INK)
            stroke(line_path([(x - 14, y), (x - 4, y + 12), (x + 15, y - 13)], 5), A.NSColor.whiteColor(), 5)


class PaperButton(A.NSButton):
    def isFlipped(self):
        return True

    def acceptsFirstMouse_(self, event):
        return True

    def drawRect_(self, dirty):
        w, h = self.bounds().size
        if min(w, h) <= 1:
            return
        cx, cy = w / 2, h / 2
        kind = self.kind
        ink = INK if self.isEnabled() else HAIR
        if kind == "mic":
            ink_disc(0, 0, w, h, ink)
            draw_symbol(self.glyph, w * .37, PAPER, cx, cy)
        elif kind in ("replay", "more"):
            if kind == "replay" or self.state():
                fill(rounded(2, 2, w - 4, h - 4, 14), WASH)
            draw_symbol(self.glyph, 20, ink, cx, cy)
        else:
            primary = kind == "primary"
            if primary:
                paper_edge((4, 4, w - 8, h - 8), ink, ink)
            else:
                path = rounded(1, 1, w - 2, h - 2, 9)
                fill(path, SHEET)
                stroke(path, HAIR, .85)
            title = text_style(self.title(), 19, ink=PAPER if primary else ink)
            size = title.size()
            title.drawAtPoint_((cx - size.width / 2, cy - size.height / 2))
        if self.isHighlighted():
            fill(rounded(3, 3, w - 6, h - 6, cy if kind == "mic" else 8), INK.colorWithAlphaComponent_(.14))


class LanguagePills(A.NSSegmentedControl):
    def drawRect_(self, dirty):
        w, h = self.bounds().size
        segment_width = w / self.segmentCount()
        for i in range(self.segmentCount()):
            selected = i == self.selectedSegment()
            x = i * segment_width
            path = rounded(x + 1, 1, segment_width - 4, h - 2, (h - 2) / 2)
            fill(path, INK if selected else WASH)
            stroke(path, INK if selected else RULE, .8)
            title = text_style(self.labelForSegment_(i), 15, ink=PAPER if selected else INK)
            size = title.size()
            title.drawAtPoint_((x + (segment_width - size.width) / 2 - 1, (h - size.height) / 2))


class PanelActivityIndicator(A.NSView):
    """Status animations for planning and recording. Bars indicate recording activity."""
    def isFlipped(self):
        return True

    @objc.python_method
    def update_motion(self, reduce_motion):
        root = self.layer()
        for layer in list(root.sublayers() or []):
            layer.removeFromSuperlayer()
        if self.isHidden():
            return

        def animate(layer, key, low, high, duration, offset=0):
            if reduce_motion:
                return
            pulse = Q.CABasicAnimation.animationWithKeyPath_(key)
            pulse.setFromValue_(low)
            pulse.setToValue_(high)
            pulse.setDuration_(duration)
            pulse.setTimeOffset_(offset)
            pulse.setAutoreverses_(True)
            pulse.setRepeatCount_(float("inf"))
            pulse.setTimingFunction_(Q.CAMediaTimingFunction.functionWithName_(Q.kCAMediaTimingFunctionEaseInEaseOut))
            layer.addAnimation_forKey_(pulse, key)

        center = self.bounds().size.width / 2
        if self.mode == "thinking":
            for i in range(3):
                dot = Q.CALayer.layer()
                dot.setFrame_(((center - 5 + (i - 1) * 19, 6), (10, 10)))
                dot.setCornerRadius_(5)
                dot.setBackgroundColor_(INK.CGColor())
                root.addSublayer_(dot)
                animate(dot, "opacity", .42, 1, .85, (2 - i) * .20)
            return

        for diameter, alpha in ((112, .42), (126, .18)):
            ring = Q.CALayer.layer()
            ring.setFrame_(((center - diameter / 2, 66 - diameter / 2), (diameter, diameter)))
            ring.setCornerRadius_(diameter / 2)
            ring.setBorderWidth_(1.3)
            ring.setBorderColor_(INK.colorWithAlphaComponent_(alpha).CGColor())
            root.addSublayer_(ring)
            animate(ring, "transform.scale", .95, 1.04, 1.3)
        for i, h in enumerate((12, 24, 38, 20, 48, 30, 16, 36, 22, 12)):
            bar = Q.CALayer.layer()
            bar.setFrame_(((center - 67 + i * 14, 165 - h / 2), (8, h)))
            bar.setCornerRadius_(4)
            bar.setBackgroundColor_(INK.CGColor())
            root.addSublayer_(bar)
            animate(bar, "transform.scale.y", .48, 1, .4 + (i % 3) * .12)
