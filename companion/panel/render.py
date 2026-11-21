"""Render the real panel's six states offscreen using synthetic questions and decisions."""

import argparse
from pathlib import Path
from types import SimpleNamespace

import AppKit as A
from Foundation import NSObject

from . import PaperPanel

STATES = ("idle", "listening", "thinking", "guiding", "done", "error")


class SamplePanelOwner(NSObject):
    """Render-only owner. No planner, recording, narration or Safari session runs."""


def make_sample(lang):
    owner = SamplePanelOwner.alloc().init()
    owner.lang = lang
    owner.voice = True
    owner.mute = False
    owner.active = False
    owner.recording = False
    owner.planner = SimpleNamespace(name="sample")
    owner.overlay_kind = "sketch"
    return PaperPanel.alloc().initWithOwner_(owner)


def show_sample(panel, mode):
    panel.owner.active = mode in ("thinking", "guiding")
    panel.set_state("idle")
    if mode == "guiding":
        panel.set_state("question", heard="എന്റെ കറന്റ് ബിൽ എങ്ങനെ നോക്കാം?" if panel.lang == "ml"
                        else "How can I see my electricity bill?")
        panel.set_state(mode, ml="KSEB-യിൽ രജിസ്റ്റർ ചെയ്ത ഫോൺ നമ്പർ ഇവിടെ നൽകൂ.",
                        en="Enter the phone number registered with KSEB.", target="Enter Mobile Number")
    elif mode == "done":
        panel.set_state(mode, ml="പരിശീലന ബില്ലിന്റെ വിവരങ്ങൾ തുറന്നു.", en="Your practice bill details are open.")
    elif mode == "error":
        panel.set_state("voice_error")
    else:
        panel.set_state(mode)


def render_all(folder):
    A.NSApplication.sharedApplication()
    folder.mkdir(parents=True, exist_ok=True)
    for lang in ("ml", "en"):
        panel = make_sample(lang)
        for mode in STATES:
            show_sample(panel, mode)
            view = panel.root
            view.layoutSubtreeIfNeeded()
            bitmap = view.bitmapImageRepForCachingDisplayInRect_(view.bounds())
            view.cacheDisplayInRect_toBitmapImageRep_(view.bounds(), bitmap)
            png = bitmap.representationUsingType_properties_(A.NSBitmapImageFileTypePNG, {})
            (folder / f"{mode}-{lang}.png").write_bytes(bytes(png))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder", type=Path)
    render_all(parser.parse_args().folder)
