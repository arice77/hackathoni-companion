"""Point geometry. Placement uses top-left coordinates local to the target display."""

from math import hypot

from companion.contracts import Rect


def to_appkit(frame: Rect, primary_height: float) -> Rect:
    x, y, w, h = frame
    return x, primary_height - y - h, w, h


def display_index(target: Rect, screens: list[Rect]) -> int:
    """Prefer the largest visible portion, then the display nearest the centre."""
    x, y, w, h = target
    cx, cy = x + w / 2, y + h / 2

    def score(index):
        sx, sy, sw, sh = screens[index]
        width = max(0, min(x + w, sx + sw) - max(x, sx))
        height = max(0, min(y + h, sy + sh) - max(y, sy))
        distance = hypot(max(sx - cx, 0, cx - sx - sw), max(sy - cy, 0, cy - sy - sh))
        return width * height, -distance

    return max(range(len(screens)), key=score)


def clamp(n, low, high):
    return max(low, min(high, n))


def place_note(target: Rect, bounds: Rect, width: float, height: float) -> Rect:
    """Try the preview's above-right placement first, then flip away from edges."""
    x, y, w, h = target
    sx, sy, sw, sh = bounds
    margin, gap = 10, 32
    left, top = sx + margin, sy + margin
    right, bottom = sx + sw - margin, sy + sh - margin
    width, height = min(width, right - left), min(height, bottom - top)
    max_x, max_y = right - width, bottom - height
    overlap = min(w / 2, 18)
    tx = x + w - overlap
    if tx > max_x:
        tx = x + overlap - width
    tx = clamp(tx, left, max_x)
    ty = clamp(y + h / 2 - height / 2, top, max_y)
    candidates = [
        (tx, y - gap - height), (tx, y + h + gap),
        (x + w + gap, ty), (x - gap - width, ty),
    ]

    def overflow(point):
        px, py = point
        return abs(px - clamp(px, left, max_x)) + abs(py - clamp(py, top, max_y))

    # min preserves preference order on ties. Even if a target fills the
    # display, choose the side that needs the smallest move to fit the paper.
    px, py = min(candidates, key=overflow)
    return clamp(px, left, max_x), clamp(py, top, max_y), width, height
