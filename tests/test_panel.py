import unittest

import AppKit as A

from companion.panel.render import make_sample, show_sample


class PaperPanelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        A.NSApplication.sharedApplication()

    def setUp(self):
        self.panel = make_sample("en")

    def tearDown(self):
        A.NSWorkspace.sharedWorkspace().notificationCenter().removeObserver_(self.panel)
        self.panel.window.close()

    def test_language_updates_current_step_and_keeps_english_target(self):
        p = self.panel
        show_sample(p, "guiding")
        p.owner.lang = "ml"
        p.set_state("language")
        self.assertIn("ഫോൺ", p.instruction.stringValue())
        self.assertEqual(p.chip.stringValue(), "Enter Mobile Number")
        self.assertEqual(p.ask_button.title(), "ചോദിക്കൂ")
        self.assertTrue(p.heard.stringValue().startswith("കേട്ടത്"))

    def test_replay_uses_current_decision_and_existing_speech_path(self):
        from unittest.mock import Mock
        p = self.panel
        p.owner.speak = Mock()
        decision = object()
        p.set_state("guiding", en="Open Search.", decision=decision)
        p.replay.performClick_(None)
        p.owner.speak.assert_called_once_with(decision)
        self.assertIsNone(p.owner.last_spoken)

    def test_four_language_switch_preserves_ask_and_skip_accessibility(self):
        from companion.contracts import Decision
        from companion.panel import LANGUAGES, WORDS

        p = self.panel
        decision = Decision("point", "s", "തുറക്കൂ", "Open ‘Search’.", "c01")
        for lang, step in (("hi", "‘Search’ खोलें।"), ("kn", "‘Search’ ತೆರೆಯಿರಿ.")):
            with self.subTest(lang=lang):
                p.owner.lang = lang
                p.owner.text_for = lambda decision: step
                for state in ("idle", "listening", "thinking", "guiding", "done", "error"):
                    p.set_state("idle")
                    if state == "guiding":
                        p.set_state("decision", decision=decision, target="Search")
                        self.assertEqual(p.instruction.stringValue(), step)
                        self.assertEqual(p.chip.stringValue(), "Search")
                        self.assertEqual(p.skip_button.accessibilityIdentifier(), "companion-skip")
                    else:
                        p.set_state(state)
                    self.assertFalse(p.ask_button.isHidden())
                    self.assertEqual(p.ask_button.accessibilityTitle(), "Ask")
                    self.assertEqual(p.ask_button.title(), WORDS[lang]["ask"])
                control = p.lang_switch
                self.assertEqual(control.segmentCount(), 4)
                self.assertEqual(control.selectedSegment(), LANGUAGES.index(lang))
                self.assertLess(A.NSMaxX(control.frame()), A.NSMinX(p.more.frame()))
                self.assertTrue(p.window.styleMask() & A.NSWindowStyleMaskNonactivatingPanel)

    def test_speech_failure_keeps_visible_guidance_and_replay(self):
        p = self.panel
        show_sample(p, "guiding")
        p.set_state("voice_error")
        self.assertFalse(p.feedback.isHidden())
        self.assertFalse(p.replay.isHidden())
        self.assertFalse(p.skip_button.isHidden())
        self.assertIn("phone", p.instruction.stringValue())

    def test_recording_takes_visual_priority_over_background_decisions(self):
        p = self.panel
        p.set_state("listening")
        p.set_state("guiding", en="Open Search.")
        self.assertEqual(p.instruction.stringValue(), "Listening…")
        self.assertEqual(p.mic_button.glyph, "stop.fill")
        p.set_state("transcribing")
        self.assertEqual(p.voice_phase, "transcribing")
        p.set_state("question", heard="Search")
        p.set_state("done", en="Search is open.")
        self.assertEqual(p.instruction.stringValue(), "Search is open.")
        p.new.performClick_(None)
        self.assertEqual(p.state.name, "idle")
        self.assertEqual(p.field.stringValue(), "")

    def test_reader_recovery_restores_the_same_step(self):
        from companion.contracts import Decision
        p = self.panel
        decision = Decision("point", "s", "തുറക്കൂ", "Open Search.", "c01")
        p.set_state("decision", decision=decision, target="Search")
        p.set_state("page_error")
        p.set_state("decision", decision=decision, target="Search")
        self.assertEqual(p.state.name, "guiding")
        self.assertEqual(p.instruction.stringValue(), "Open Search.")
        self.assertFalse(p.replay.isHidden())

    def test_motion_and_details(self):
        p = self.panel
        show_sample(p, "listening")
        p.meter.update_motion(True)
        layers = p.meter.layer().sublayers()
        self.assertEqual(len(layers), 12)
        self.assertFalse(any(layer.animationKeys() for layer in layers))
        p.meter.update_motion(False)
        self.assertTrue(all(layer.animationKeys() for layer in p.meter.layer().sublayers()))
        self.assertTrue(p.status.isHidden())
        p.toggleDetails_(None)
        self.assertFalse(p.status.isHidden())

    def test_thinking_dots_follow_reduce_motion_and_clear_when_guiding(self):
        p = self.panel
        show_sample(p, "thinking")
        p.meter.update_motion(False)
        dots = p.meter.layer().sublayers()
        self.assertEqual(len(dots), 3)
        self.assertTrue(all(dot.animationForKey_("opacity") for dot in dots))
        p.meter.update_motion(True)
        self.assertFalse(any(dot.animationKeys() for dot in p.meter.layer().sublayers()))
        thinking_stop = p.stop_button.frame()
        show_sample(p, "guiding")
        self.assertEqual(thinking_stop.origin.x, p.stop_button.frame().origin.x)
        self.assertEqual(thinking_stop.size, p.stop_button.frame().size)
        self.assertFalse(p.meter.layer().sublayers())

    def test_long_steps_scroll_with_actions_inside_panel(self):
        p = self.panel
        p.set_state("guiding", en="Read the next line. " * 200, target="Search")
        self.assertGreater(p.instruction.frame().size.height, p.scroll.frame().size.height)
        self.assertLess(p.window.frame().size.height, A.NSScreen.mainScreen().visibleFrame().size.height)
        self.assertLess(A.NSMaxY(p.ask_button.frame()), p.root.bounds().size.height)
