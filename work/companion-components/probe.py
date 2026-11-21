"""Fixture-only reader/window checks, with optional local visual style adapters."""
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import sys
import time
import types
import uuid

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1] / "research-repos/h-companion"
BUNDLE = "in.hackathoni.component-fixture"
RUN_ID = uuid.uuid4().hex

# Import just these modules without running the project's CLI/package initializer.
pkg = types.ModuleType("hcs_agent")
pkg.__path__ = [str(REPO / "agent/src/hcs_agent")]
sys.modules["hcs_agent"] = pkg
from hcs_agent import a11y

a11y.NATIVE_APPLICATIONS = {BUNDLE: "Companion Test Pad"}
os.environ["HCS_AX_NATIVE_BUNDLE_ID"] = BUNDLE


def save(name, result):
    result = {"run_id": RUN_ID, "recorded_at": datetime.now(timezone.utc).isoformat(), **result}
    (ROOT / name).write_text(json.dumps(result, indent=2) + "\n")


def _read_fixture():
    if not a11y.available():
        save("reader-result.json", {"passed": False, "blocked": "macOS Accessibility permission", "scope": BUNDLE})
        raise RuntimeError("Reader blocked: macOS Accessibility permission is missing for the test process.")
    page = a11y.page()
    if page is None or not page.native or page.bundle_id != BUNDLE or not page.is_front:
        raise RuntimeError("Reader stopped: Companion Test Pad must be the foreground window.")
    controls = [{"role": e.role, "name": e.name, "frame": list(e.frame), "value": e.value} for e in page.elements]
    buttons = {e.name for e in page.elements if e.role == "AXButton"}
    expected = {"Export PDF", "Save draft", "Preview invoice", "Use question"}
    missing = expected - buttons
    assert not missing, f"Missing expected buttons: {sorted(missing)}"
    assert all(all(math.isfinite(v) for v in e.frame) and e.frame[2] > 0 and e.frame[3] > 0 for e in page.elements)
    assert "FIELD_VALUE_SHOULD_NOT_BE_READ" not in json.dumps(controls), "Input value leaked into the reader snapshot"
    assert all(e.value is None for e in page.elements), "Native field values should not be read"
    result = {"passed": True, "scope": BUNDLE, "title": page.title, "walk_seconds": page.walk_s,
              "checks": ["known buttons found", "valid positive rectangles", "typed input values excluded"], "controls": controls}
    save("reader-result.json", result)
    return page


def read_fixture():
    try:
        return _read_fixture()
    except Exception as error:
        save("reader-result.json", {"passed": False, "scope": BUNDLE,
                                    "error": str(error), "error_type": type(error).__name__,
                                    "requesting_process_id": os.getpid(),
                                    "permission_available": bool(a11y.available())})
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["read", "point", "pointer-check"])
    parser.add_argument("--seconds", type=float, default=45)
    style_path = ROOT / "overlay-style.json"
    default_style = json.loads(style_path.read_text())["style"] if style_path.exists() else "original"
    parser.add_argument("--style", choices=["original", "focus", "terminal"], default=default_style)
    args = parser.parse_args()
    assert args.style in {"original", "focus", "terminal"}, "Unknown overlay style"

    def renderer():
        from hcs_agent import overlay as overlay_module
        from overlay_styles import apply_style
        apply_style(overlay_module, args.style)
        return overlay_module.Overlay(), overlay_module.Scene

    if args.mode == "pointer-check":
        # Exercise the original window/coordinate conversion and selected drawing style.
        overlay, Scene = renderer()
        frame = (120, 160, 160, 34)
        center = (200, 177)
        overlay.show_scene(Scene(text="Pointer component check", target=center, target_box=frame), animate=False)
        assert overlay.view.scene.target == (200, overlay._screen_h - 177)
        assert overlay.view.scene.target_box == (120, overlay._screen_h - 194, 160, 34)
        assert overlay.window.ignoresMouseEvents(), "Overlay must let manual clicks through"
        # Render only this component's own view, not a screenshot of the user's desktop.
        bounds = overlay.view.bounds()
        rep = overlay.view.bitmapImageRepForCachingDisplayInRect_(bounds)
        overlay.view.cacheDisplayInRect_toBitmapImageRep_(bounds, rep)
        import AppKit
        png = rep.representationUsingType_properties_(AppKit.NSBitmapImageFileTypePNG, {})
        preview = ROOT / ("pointer-component.png" if args.style == "original" else f"pointer-component-{args.style}.png")
        assert png and png.writeToFile_atomically_(str(preview), True)
        # Compact view-only preview with a known target box, not a desktop screenshot.
        view = overlay.view
        view.setFrame_(((0, 0), (720, 260)))
        view.scene = Scene(text="Click Export PDF", target=(170, 105), target_box=(90, 87, 160, 36))
        compact = view.bitmapImageRepForCachingDisplayInRect_(view.bounds())
        view.cacheDisplayInRect_toBitmapImageRep_(view.bounds(), compact)
        data = compact.representationUsingType_properties_(AppKit.NSBitmapImageFileTypePNG, {})
        assert data.writeToFile_atomically_(str(ROOT / f"style-preview-{args.style}.png"), True)
        overlay.hide()
        result_name = "pointer-component-result.json" if args.style == "original" else f"pointer-component-{args.style}-result.json"
        save(result_name, {"passed": True, "style": args.style, "checks": ["renderer instantiated", "top-left screen coordinates converted correctly", "click-through enabled", "own view rendered to PNG"], "live_alignment_verified": False})
        print(f"Pointer style {args.style} passed component checks; live alignment still needs checking for this style.")
        return
    source = "accessibility"
    if args.mode == "point" and not a11y.available():
        layout = json.loads((ROOT / "fixture-layout.json").read_text())
        assert 0 <= time.time() - layout["captured_at"] < 10, "Fixture layout must be fresh"
        frame = tuple(layout["frame"])
        assert len(frame) == 4 and all(math.isfinite(v) for v in frame) and frame[2] > 0 and frame[3] > 0
        target = a11y.Candidate(role="AXButton", name="Export PDF", frame=frame)
        source = "fixture-supplied geometry (reader permission missing)"
    else:
        page = read_fixture()
        matches = [e for e in page.elements if e.role == "AXButton" and e.name == "Export PDF"]
        assert len(matches) == 1, "Target must match exactly one button"
        target = matches[0]
    if args.mode == "read":
        print(f"Reader passed: {len(page.elements)} controls/text elements; expected buttons found; input values excluded.")
        return
    from AppKit import NSWorkspace
    def stop_if_unfocused():
        front = NSWorkspace.sharedWorkspace().frontmostApplication()
        return front is None or front.bundleIdentifier() != BUNDLE
    assert not stop_if_unfocused(), "Practice app must be in front before showing the pointer"
    os.environ["HCS_OVERLAY_CAPTURE"] = "1"
    overlay, Scene = renderer()
    overlay.show_scene(Scene(text="Click Export PDF yourself", target=target.center, target_box=target.box))
    geometry_check = {"verified": False, "reason": "no fresh independent fixture geometry"}
    layout_path = ROOT / "fixture-layout.json"
    if source == "accessibility" and layout_path.exists():
        layout = json.loads(layout_path.read_text())
        if 0 <= time.time() - layout["captured_at"] < 10:
            x, y, w, h = layout["frame"]
            cx, cy = target.center
            inside = x <= cx <= x + w and y <= cy <= y + h
            delta = [cx - (x + w / 2), cy - (y + h / 2)]
            geometry_check = {"verified": inside and max(abs(v) for v in delta) <= 3,
                              "target_center_inside_fixture_button": inside,
                              "center_delta_points": delta, "fixture_frame": layout["frame"]}
            assert geometry_check["verified"], f"Pointer target disagrees with fixture button: {geometry_check}"
    save("pointer-result.json", {"started": True, "target": target.name, "frame": target.box,
                                 "style": args.style,
                                 "source": source,
                                 "center": target.center, "click_through": bool(overlay.window.ignoresMouseEvents()),
                                 "independent_geometry_check": geometry_check,
                                 "visual_alignment_verified": False, "automatic_clicks": False})
    start = time.monotonic()
    try:
        overlay.run_until(lambda: time.monotonic() - start >= args.seconds or stop_if_unfocused())
    finally:
        overlay.hide()
    print(f"Pointer test ended. Target source: {source}. No automatic clicks.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        if len(sys.argv) > 1 and sys.argv[1] == "point":
            save("pointer-result.json", {"started": False, "passed": False,
                                         "error": str(error), "error_type": type(error).__name__,
                                         "visual_alignment_verified": False, "automatic_clicks": False})
        print(f"{type(error).__name__}: {error}")
        sys.exit(1)
