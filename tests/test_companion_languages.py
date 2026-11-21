"""Offline coverage of language selection and translated turns, with no running app."""

import unittest
from contextlib import redirect_stderr
from io import StringIO
from threading import Lock
from unittest.mock import Mock, patch

from companion import app, voice
from companion.contracts import Decision
from companion.voice import sarvam


class LanguageTests(unittest.TestCase):
    def test_language_arguments_and_environment(self):
        for lang in ("ml", "en", "hi", "kn"):
            with self.subTest(lang=lang), patch.dict(app.os.environ, {"COMPANION_LANG": lang}):
                self.assertEqual(app.parse_args([]).lang, lang)
                self.assertEqual(app.parse_args(["--lang", "hi"]).lang, "hi")
                self.assertEqual(app.UI[lang].keys(), app.UI["en"].keys())
                self.assertEqual(app.WORDS[lang].keys(), app.WORDS["en"].keys())
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
            app.parse_args(["--lang", "fr"])
        with self.assertRaises(ValueError):
            voice.ask("unused.wav", "fr-FR")

    def test_labels_can_move_and_keep_spelling_quotes_and_apostrophes(self):
        text = """Don't open ‘Search’ or "Compose". Choose 'Playback speed' in “What's new” at 910001."""
        with patch.object(sarvam, "translate_text", return_value="910005 में 910004 चुनें। 910002 या 910003 न खोलें। 910001") as translate:
            self.assertEqual(voice.translate_instruction(text, "hi-IN"),
                             """“What's new” में 'Playback speed' चुनें। ‘Search’ या "Compose" न खोलें। 910001""")
        translate.assert_called_once_with("Don't open 910002 or 910003. Choose 910004 in 910005 at 910001.",
                                          "en-IN", "hi-IN")

    def test_native_speech_uses_english_for_planning_and_native_for_the_field(self):
        c = Mock()
        for pref, native in (("hi-IN", "मेरा बिल खोलें"), ("kn-IN", "ನನ್ನ ಬಿಲ್ ತೆರೆಯಿರಿ")):
            app.Companion.voiceHeard_(c, {"text": native, "planner": "Open my bill", "preference": pref})
            c.start_question.assert_called_with("Open my bill", shown=native)
            c.field.setStringValue_.assert_called_with(native)


class TranslatedTurnTests(unittest.TestCase):
    def setUp(self):
        # No Companion window, event loop, screen reader, player or microphone.
        self.c = c = app.Companion.alloc().init()
        c.voice = voice
        c.lang = "hi"
        c.mute = False
        c.recording = False
        c.active = True
        c.translations, c.pending_translations, c.failed_translations = {}, set(), set()
        c.panel, c.overlay, c.field, c.heard = Mock(), Mock(), Mock(), Mock()
        c.panel.voice_phase = None
        c.plan_lock, c.planner, c.question_version = Lock(), Mock(), 0
        c.panel.current_decision = Decision("point", "s", "തുറക്കൂ", "Open ‘Compose’.", "c01")
        c.shown_frame = (10, 20, 30, 40)
        c.last_spoken = None
        c.on_main, c.log = Mock(), Mock()
        self.workers = []
        thread = self.enterContext(patch.object(app.threading, "Thread"))
        thread.side_effect = lambda *, target, daemon: Mock(start=lambda: self.workers.append(target))
        self.translate = self.enterContext(patch.object(sarvam, "translate_text"))
        self.tts = self.enterContext(patch.object(voice, "speak"))

    def finish_translation(self):
        self.workers.pop(0)()
        selector, payload = self.c.on_main.call_args.args
        getattr(self.c, selector.replace(":", "_"))(payload)

    def test_cached_translation_is_shared_by_panel_pointer_and_speech(self):
        c = self.c
        d = c.panel.current_decision
        for lang, translation in (("hi", "910001 खोलें।"), ("kn", "910001 ತೆರೆಯಿರಿ.")):
            c.lang = lang
            self.translate.return_value = translation
            c.request_translation(d)
            c.request_translation(d)
            c.speak(d)
            self.assertEqual(len(self.workers), 1)
            self.finish_translation()
            expected = translation.replace("910001", "‘Compose’")
            self.assertEqual(c.text_for(d), expected)
            c.overlay.show.assert_called_with(c.shown_frame, expected, "")
            self.workers.pop(0)()
            self.tts.assert_called_with(expected, lang + "-IN")
            c.request_translation(d)
            self.assertEqual(self.workers, [])
        c.lang = "hi"
        c.request_translation(d)
        self.assertEqual(c.text_for(d), "‘Compose’ खोलें।")
        self.assertEqual(self.translate.call_count, 2)
        self.assertEqual(self.workers, [])

    def test_timeout_empty_or_damaged_labels_keep_the_full_english_step(self):
        c = self.c
        d = c.panel.current_decision
        for result in (sarvam.SarvamTimeoutError("timeout"), "", "खोलें", "910001 910001"):
            with self.subTest(result=str(result)):
                self.translate.side_effect = [result]
                c.failed_translations.clear()
                c.request_translation(d)
                self.finish_translation()
                self.assertEqual(c.text_for(d), d.instruction_en)
                c.overlay.show.assert_called_with(c.shown_frame, d.instruction_en, "")
                c.request_translation(d)
                for worker in self.workers:
                    worker()
                self.workers.clear()
                self.tts.assert_called_with(d.instruction_en, "hi-IN")

    def test_late_translation_after_stop_or_switch_cannot_repaint_or_speak(self):
        c = self.c
        self.translate.return_value = "910001 खोलें।"
        c.request_translation(c.panel.current_decision)
        c.lang = "en"
        self.finish_translation()
        c.overlay.show.assert_not_called()
        c.panel.render.assert_not_called()
        self.tts.assert_not_called()
        self.assertEqual(self.workers, [])
        c.lang = "kn"
        c.request_translation(c.panel.current_decision)
        c.panel.current_decision = None
        self.finish_translation()
        self.assertEqual(self.workers, [])

    def test_typed_question_is_translated_once_before_the_first_planner_tick(self):
        c = self.c
        c.lang = "kn"
        native = "ನನ್ನ ಬಿಲ್ ತೆರೆಯಿರಿ"
        c.field.stringValue.return_value = native
        self.translate.return_value = "Open my bill"
        with patch.object(app.Companion, "tick_") as tick:
            c.ask_(None)
            tick.assert_not_called()
            self.finish_translation()
            tick.assert_called_once()
        self.translate.assert_called_once_with(native, "kn-IN", "en-IN")
        self.assertEqual(c.question, "Open my bill")
        c.panel.set_state.assert_called_with("question", heard=native)

    def test_superseded_typed_question_and_failed_translation_never_reach_planner(self):
        c = self.c
        self.translate.side_effect = ["Old question", sarvam.SarvamError("unavailable")]
        with patch.object(app.Companion, "tick_") as tick:
            for question in ("बिल खोलें", "संदेश लिखें"):
                c.field.stringValue.return_value = question
                c.ask_(None)
            self.finish_translation()
            self.assertTrue(c.translating_question)
            self.finish_translation()
            c.panel.set_state.assert_called_with("question_error")
            self.assertFalse(c.active)
            tick.assert_not_called()

    def test_language_switch_translates_current_step_even_when_muted(self):
        c = self.c
        sender = Mock()
        sender.selectedSegment.return_value = app.LANGUAGES.index("kn")
        c.mute = True
        c.mic_button = Mock()
        self.translate.return_value = "910001 ತೆರೆಯಿರಿ."
        with patch.object(voice, "stop_speaking"):
            c.langChanged_(sender)
        self.assertEqual(c.lang, "kn")
        self.finish_translation()
        c.overlay.show.assert_called_with(c.shown_frame, "‘Compose’ ತೆರೆಯಿರಿ.", "")
        self.assertEqual(self.workers, [])
        self.tts.assert_not_called()
