"""Exercise text shaping and paper layout together, without opening a window."""

from math import ceil, dist
import unittest

import AppKit as A

from companion.overlay.drawing import PAD_X, PAD_Y, TEXT_OPTIONS, SketchPointerView, arrow_ends


class NoteLayoutTests(unittest.TestCase):
    def layout(self, text, subtitle="", target=(240, 325, 122, 36)):
        A.NSApplication.sharedApplication()
        view = SketchPointerView.alloc().initWithFrame_(((0, 0), (800, 480)))
        view.configure(target, (0, 0, 800, 480), text, subtitle)
        return view

    def test_single_line_hugs_the_text_in_both_languages(self):
        for instruction in ("തുടരൂ", "Save"):
            with self.subTest(instruction=instruction):
                view = self.layout(instruction)
                self.assertEqual(len(view.lines), 1)
                measured = view.lines[0].size()
                self.assertAlmostEqual(view.paper_size[0], measured.width + 2 * PAD_X, delta=2)
                self.assertEqual(view.paper_size[1], ceil(measured.height) + 2 * PAD_Y)

    def test_long_instruction_wraps_without_losing_the_last_line(self):
        view = self.layout("‘Business Name’ എന്ന ബോക്സിൽ പരിശീലനത്തിനായി ഒരു സാങ്കൽപ്പിക കടപ്പേര് എഴുതുക.")
        self.assertLessEqual(view.paper_size[0], 420)
        line = view.lines[0]
        self.assertGreater(view.heights[0], line.size().height * 2)
        drawn = line.boundingRectWithSize_options_((view.text_width, 10000), TEXT_OPTIONS)
        self.assertEqual(view.heights[0], ceil(drawn.size.height))
        self.assertEqual(view.paper_size[1], view.heights[0] + 2 * PAD_Y)

    def test_rotated_note_and_arrow_fit_near_edges(self):
        for target in [(16, 17, 140, 34), (644, 17, 140, 34),
                       (16, 429, 140, 34), (644, 429, 140, 34)]:
            with self.subTest(target=target):
                view = self.layout("Click “Save Draft”", "Save this practice return.", target)
                x, y, w, h = view.note
                self.assertGreater(h, view.paper_size[1])
                self.assertGreaterEqual(min(x, y), 10)
                self.assertGreaterEqual(min(800 - x - w, 480 - y - h), 9.99)
                # The card reaches over a corner in x, leaving the button free in y.
                tx, ty, tw, th = target
                self.assertGreater(min(x + w, tx + tw) - max(x, tx), 0)
                self.assertTrue(y > ty + th or y + h < ty)
                length = dist(*arrow_ends(view.note, target))
                self.assertTrue(30 <= length <= 60, length)

    def test_wide_control_keeps_arrow_on_the_chosen_display(self):
        target = (-300, 300, 1400, 40)
        view = self.layout("Continue", target=target)
        start, end = arrow_ends(view.note, target)
        self.assertTrue(0 <= end[0] <= 800)
        self.assertTrue(30 <= dist(start, end) <= 60)
