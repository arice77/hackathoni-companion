import unittest

import AppKit as A
import CoreText as CT

from companion.overlay.drawing import lettering


class FontTests(unittest.TestCase):
    def test_actual_glyph_runs_and_variations(self):
        A.NSApplication.sharedApplication()
        text = lettering("“Prepare Online” തുറക്കൂ", 25)
        line = CT.CTLineCreateWithAttributedString(text)
        runs = CT.CTLineGetGlyphRuns(line)
        fonts = [CT.CTRunGetAttributes(run)[A.NSFontAttributeName] for run in runs]
        self.assertIn("ShantellSans", fonts[0].fontName())
        self.assertIn("Malayalam", fonts[-1].fontName())
        axes = {n.to_bytes(4, "big"): v for n, v in CT.CTFontCopyVariation(fonts[0]).items()}
        self.assertEqual(axes, {b"wght": 500, b"INFM": 35, b"BNCE": 16})
        for run in runs:
            count = CT.CTRunGetGlyphCount(run)
            self.assertGreater(count, 0)
            glyphs = CT.CTRunGetGlyphs(run, (0, count), None)
            self.assertNotIn(0, glyphs)
