"""Mock coverage for voice routing, microphone lifecycle and playback interruption."""

import io
import tempfile
import unittest
import wave
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event
from unittest.mock import patch

from companion import voice
from companion.contracts import Transcript
from companion.voice import microphone, sarvam


class VoiceTests(unittest.TestCase):
    def test_ask_returns_native_transcript_and_malayalam_translation(self):
        native = Transcript("ഈ ഫോം എങ്ങനെ പൂരിപ്പിക്കാം?", "ml-IN", "sarvam", request_id="native")
        english = Transcript("How do I fill this form?", "en-IN", "sarvam", request_id="translated")
        with (
            patch.object(sarvam, "transcribe", return_value=native) as transcribe,
            patch.object(sarvam, "translate_speech_to_english", return_value=english) as translate,
        ):
            result = voice.ask("question.wav", "ml-IN")
        transcribe.assert_called_once_with("question.wav", language_code="ml-IN")
        translate.assert_called_once_with("question.wav")
        self.assertIsInstance(result, Transcript)
        self.assertEqual(result.request_id, native.request_id)
        self.assertEqual(result.text, native.text)
        self.assertEqual(result.english_translation, english)
        self.assertEqual(result.planner_text, english.text)

    def test_ask_english_uses_native_transcript_for_planner(self):
        native = Transcript("How do I fill this form?", "en-IN", "sarvam")
        with (
            patch.object(sarvam, "transcribe", return_value=native) as transcribe,
            patch.object(sarvam, "translate_speech_to_english") as translate,
        ):
            result = voice.ask("question.wav", "en-IN")
        transcribe.assert_called_once_with("question.wav", language_code="en-IN")
        translate.assert_not_called()
        self.assertIsNone(result.english_translation)
        self.assertEqual(result.planner_text, native.text)

    def test_speak_uses_preference_and_temporary_wav(self):
        with (
            patch.object(sarvam, "synthesize", return_value=(b"audio", {"request_id": "tts"})) as synthesize,
            patch.object(voice.subprocess, "Popen") as popen,
        ):
            paths = []

            def start_player(args, **kwargs):
                self.assertEqual(args[0], "/usr/bin/afplay")
                path = Path(args[1])
                self.assertEqual(path.read_bytes(), b"audio")
                paths.append(path)
                return player

            player = popen.return_value
            player.wait.return_value = 0
            popen.side_effect = start_player
            for preference in ("ml-IN", "en-IN"):
                self.assertEqual(voice.speak("reply", preference), {"request_id": "tts"})
                synthesize.assert_called_with("reply", language_code=preference)
            self.assertEqual(len(paths), 2)
            self.assertTrue(all(not path.exists() for path in paths))

    def test_stop_speaking_cancels_pending_synthesis(self):
        synthesizing, resume = Event(), Event()

        def synthesize(*args, **kwargs):
            synthesizing.set()
            if not resume.wait(5):
                raise TimeoutError("Test did not resume synthesis")
            return b"audio", {}

        with (
            patch.object(sarvam, "synthesize", side_effect=synthesize),
            patch.object(voice.subprocess, "Popen") as popen,
            ThreadPoolExecutor(max_workers=1) as workers,
        ):
            future = workers.submit(voice.speak, "reply", "ml-IN")
            self.assertTrue(synthesizing.wait(5))
            voice.stop_speaking()
            resume.set()
            self.assertIsNone(future.result(timeout=5))
            popen.assert_not_called()

    def test_stop_speaking_terminates_active_player(self):
        playing, ended = Event(), Event()

        def wait_for_exit():
            playing.set()
            if not ended.wait(5):
                raise TimeoutError("Test did not stop playback")
            return -15

        with (
            patch.object(sarvam, "synthesize", return_value=(b"audio", {})),
            patch.object(voice.subprocess, "Popen") as popen,
            ThreadPoolExecutor(max_workers=1) as workers,
        ):
            player = popen.return_value
            player.poll.return_value = None
            player.wait.side_effect = wait_for_exit
            player.terminate.side_effect = ended.set
            future = workers.submit(voice.speak, "reply", "en-IN")
            self.assertTrue(playing.wait(5))
            voice.stop_speaking()
            self.assertIsNone(future.result(timeout=5))
            player.terminate.assert_called_once_with()
            self.assertFalse(Path(popen.call_args.args[0][1]).exists())


class MicrophoneTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch.object(microphone, "_ROOT", self.root))
        self.enterContext(patch.object(microphone, "_recording", None))
        self.enterContext(patch.object(microphone, "_recorder_binary", return_value=self.root / "helper"))
        self.popen = self.enterContext(patch.object(microphone.subprocess, "Popen"))
        self.wait_readable = self.enterContext(patch.object(microphone.select, "select"))
        self.wait_readable.return_value = ([self.popen.return_value.stdout], [], [])
        self.process = self.popen.return_value
        self.process.stdout = io.BytesIO(b"ready\n")
        self.process.returncode = 0
        self.process.communicate.return_value = (b"", b"")

    def test_start_and_stop_return_a_local_pcm_wav(self):
        self.assertIsNone(voice.record_push_to_talk())
        with self.assertRaisesRegex(voice.MicrophoneError, "already active"):
            voice.record_push_to_talk()
        wav_path = Path(self.popen.call_args.args[0][1])
        self.assertEqual(wav_path.parent, self.root / "runs")
        with wave.open(str(wav_path), "wb") as audio:
            audio.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
            audio.writeframes(b"\x00\x00" * 160)
        self.assertEqual(voice.stop_recording(), wav_path)
        self.process.communicate.assert_called_once_with(input=b"\n", timeout=5)
        with self.assertRaisesRegex(voice.MicrophoneError, "no active"):
            voice.stop_recording()

    def test_denied_permission_is_a_distinct_failure(self):
        self.process.stdout = io.BytesIO()
        self.process.returncode = 77
        self.process.poll.return_value = 77
        self.process.communicate.return_value = (b"", b"Microphone access was declined.")
        with self.assertRaisesRegex(voice.MicrophonePermissionError, "declined"):
            voice.record_push_to_talk()
        self.assertIsNone(microphone._recording)

    def test_startup_timeout_terminates_recorder(self):
        self.wait_readable.return_value = ([], [], [])
        self.process.poll.return_value = None
        with self.assertRaisesRegex(voice.MicrophoneError, "timed out"):
            voice.record_push_to_talk()
        self.process.kill.assert_called_once_with()
        self.process.communicate.assert_called_once_with()
        self.assertIsNone(microphone._recording)

    def test_stopping_an_empty_capture_cleans_up(self):
        voice.record_push_to_talk()
        wav_path = Path(self.popen.call_args.args[0][1])
        with wave.open(str(wav_path), "wb") as audio:
            audio.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        with self.assertRaisesRegex(voice.MicrophoneError, "No audio"):
            voice.stop_recording()
        self.assertFalse(wav_path.exists())
        self.assertIsNone(microphone._recording)
