"""Show a live pointer, or draw the same view on an 800 × 480 pt transparent canvas."""

import argparse
import sys
from math import isfinite
from pathlib import Path

import AppKit as A
from Foundation import NSDate, NSRunLoop
from . import SketchOverlay
from .drawing import SketchPointerView


def parse_rect(value):
    try:
        x, y, w, h = map(float, value.split(","))
        if all(map(isfinite, (x, y, w, h))) and w > 0 and h > 0:
            return x, y, w, h
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("expected x,y,width,height with positive dimensions")


def render(path, frame, instruction, subtitle):
    canvas = ((0, 0), (800, 480))
    view = SketchPointerView.alloc().initWithFrame_(canvas)
    view.configure(frame, (0, 0, 800, 480), instruction, subtitle)
    image = A.NSImage.alloc().initWithSize_(canvas[1])
    image.lockFocusFlipped_(True)
    try:
        view.drawRect_(canvas)
    finally:
        image.unlockFocus()
    bitmap = A.NSBitmapImageRep.imageRepWithData_(image.TIFFRepresentation())
    png = bitmap.representationUsingType_properties_(A.NSBitmapImageFileTypePNG, {})
    path.write_bytes(bytes(png))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rect", type=parse_rect, required=True)
    parser.add_argument("--text", required=True)
    parser.add_argument("--subtitle", default="")
    parser.add_argument("--seconds", type=float, default=45)
    parser.add_argument("--render", type=Path)
    # argparse recognises a negative number, but treats a comma-separated
    # rectangle starting with a minus sign as another option.
    argv = sys.argv[1:]
    if "--rect" in argv:
        i = argv.index("--rect")
        if i + 1 < len(argv) and argv[i + 1].startswith("-") and "," in argv[i + 1]:
            argv[i:i + 2] = ["--rect=" + argv[i + 1]]
    args = parser.parse_args(argv)
    if not isfinite(args.seconds) or args.seconds <= 0:
        parser.error("--seconds must be a positive duration")
    A.NSApplication.sharedApplication()
    if args.render:
        render(args.render, args.rect, args.text, args.subtitle)
        return
    overlay = SketchOverlay()
    overlay.show(args.rect, args.text, args.subtitle)
    overlay.timer.invalidate()
    try:
        NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(args.seconds))
    finally:
        overlay.hide()


if __name__ == "__main__":
    main()
