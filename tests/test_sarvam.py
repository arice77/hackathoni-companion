"""Mock HTTP tests for the Sarvam adapter and smoke CLI."""

import base64
import io
import json
import os
import tempfile
import unittest
import wave
from contextlib import redirect_stderr, redirect_stdout
from email import policy
from email.parser import BytesParser
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from companion.contracts import Transcript
from companion.voice import sarvam
from scripts import sarvam_smoke

FAKE_KEY = "unit-test-key"


class SarvamTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.enterContext(patch.object(sarvam, "_ROOT", self.root))
        self.enterContext(patch.dict(os.environ, {"SARVAM_API_KEY": FAKE_KEY}, clear=True))
        self.http = self.enterContext(patch.object(sarvam._OPENER, "open"))
        self.wav = self.root / "local-recording.wav"
        with wave.open(str(self.wav), "wb") as audio:
            audio.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
            audio.writeframes(b"\x00\x00" * 160)

    @staticmethod
    def response(**fields):
        return io.BytesIO(json.dumps(fields, ensure_ascii=False).encode("utf-8"))

    def request(self, endpoint, key=FAKE_KEY):
        request = self.http.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.sarvam.ai" + endpoint)
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Api-subscription-key"), key)
        self.assertEqual(request.get_header("Accept"), "application/json")
        self.assertGreater(self.http.call_args.kwargs["timeout"], 0)
        return request

    def speech_fields(self):
        request = self.request("/speech-to-text")
        content_type = request.get_header("Content-type")
        self.assertTrue(content_type.startswith("multipart/form-data; boundary="))
        multipart = BytesParser(policy=policy.default).parsebytes(
            b"Content-Type: " + content_type.encode() + b"\r\n\r\n" + request.data
        )
        fields = {}
        for part in multipart.iter_parts():
            name = part.get_param("name", header="Content-Disposition")
            if name == "file":
                self.assertEqual(part.get_content_type(), "audio/wav")
                self.assertEqual(part.get_filename(), "speech.wav")
                fields[name] = part.get_payload(decode=True)
            else:
                fields[name] = part.get_content()
        self.assertEqual(fields.pop("file"), self.wav.read_bytes())
        return fields

    def json_fields(self, endpoint, key=FAKE_KEY):
        request = self.request(endpoint, key)
        self.assertEqual(request.get_header("Content-type"), "application/json")
        return json.loads(request.data)

    def test_transcribe_malayalam(self):
        self.http.return_value = self.response(
            transcript="നമസ്കാരം", language_code="ml-IN", request_id="native-id"
        )
        result = sarvam.transcribe(self.wav)
        self.assertEqual(self.speech_fields(), {
            "model": "saarika:v2.5", "language_code": "ml-IN",
        })
        self.assertIsInstance(result, Transcript)
        self.assertEqual(result.text, "നമസ്കാരം")
        self.assertEqual(result.language_code, "ml-IN")
        self.assertEqual(result.provider, "sarvam")
        self.assertEqual(result.model, "saarika:v2.5")
        self.assertEqual(result.request_id, "native-id")
        self.assertGreaterEqual(result.latency_ms, 0)

    def test_transcribe_fallback_to_requested_language(self):
        self.http.return_value = self.response(transcript="Hello", language_code=None)
        result = sarvam.transcribe(str(self.wav), language_code="en-IN")
        self.assertEqual(self.speech_fields()["language_code"], "en-IN")
        self.assertEqual(result.language_code, "en-IN")

    def test_translate_speech_malayalam_to_english(self):
        self.http.return_value = self.response(
            transcript="Hello", language_code="ml-IN", request_id="english-id"
        )
        result = sarvam.translate_speech_to_english(self.wav)
        self.assertEqual(self.speech_fields(), {
            "model": "saaras:v4", "language_code": "ml-IN", "mode": "translate",
        })
        self.assertEqual(result.text, "Hello")
        self.assertEqual(result.language_code, "en-IN")
        self.assertEqual(result.request_id, "english-id")

    def test_translate_text_in_both_directions(self):
        for source, target, text, translated in (
            ("ml-IN", "en-IN", "നമസ്കാരം", "Hello"),
            ("en-IN", "ml-IN", "Hello", "നമസ്കാരം"),
        ):
            with self.subTest(source=source):
                self.http.return_value = self.response(translated_text=translated, request_id="text-id")
                self.assertEqual(sarvam.translate_text(text, source, target), translated)
                self.assertEqual(self.json_fields("/translate"), {
                    "input": text, "source_language_code": source, "target_language_code": target,
                    "model": "sarvam-translate:v1",
                })

    def test_synthesize_wav_with_default_and_explicit_speaker(self):
        wav_bytes = self.wav.read_bytes()
        encoded = base64.b64encode(wav_bytes).decode("ascii")
        for speaker, expected in ((None, "shubh"), ("pooja", "pooja")):
            with self.subTest(speaker=speaker):
                self.http.return_value = self.response(audios=[encoded], request_id="tts-id")
                actual, meta = sarvam.synthesize("നമസ്കാരം", speaker=speaker)
                self.assertEqual(self.json_fields("/text-to-speech"), {
                    "text": "നമസ്കാരം", "language_code": "ml-IN", "model": "bulbul:v3",
                    "speaker": expected, "output_audio_codec": "wav", "speech_sample_rate": 16000,
                })
                self.assertEqual(actual, wav_bytes)
                self.assertEqual(meta["request_id"], "tts-id")
                self.assertEqual(meta["speaker"], expected)
                self.assertGreaterEqual(meta["latency_ms"], 0)

    def test_missing_key_stops_all_calls_before_http_or_file_read(self):
        del os.environ["SARVAM_API_KEY"]
        nonexistent = self.root / "missing.wav"
        for operation, args in (
            (sarvam.transcribe, (nonexistent,)),
            (sarvam.translate_speech_to_english, (nonexistent,)),
            (sarvam.translate_text, ("Hello", "en-IN", "ml-IN")),
            (sarvam.synthesize, ("നമസ്കാരം",)),
        ):
            with self.subTest(operation=operation.__name__):
                with self.assertRaisesRegex(sarvam.SarvamMissingKeyError, "BLOCKED: no SARVAM_API_KEY"):
                    operation(*args)
        self.http.assert_not_called()

    def test_repo_env_fallback_and_environment_priority(self):
        (self.root / ".env").write_text('export SARVAM_API_KEY="fixture-key"\n', encoding="utf-8")
        self.http.side_effect = [self.response(translated_text="Hello") for _ in range(2)]
        sarvam.translate_text("നമസ്കാരം", "ml-IN", "en-IN")
        self.request("/translate")
        del os.environ["SARVAM_API_KEY"]
        sarvam.translate_text("നമസ്കാരം", "ml-IN", "en-IN")
        self.request("/translate", key="fixture-key")

    def test_non_wav_is_never_uploaded(self):
        dotenv = self.root / ".env"
        dotenv.write_text("SARVAM_API_KEY=fixture-key\n", encoding="utf-8")
        with self.assertRaisesRegex(sarvam.SarvamError, "WAV file"):
            sarvam.transcribe(dotenv)
        self.http.assert_not_called()

    def test_http_error_preserves_status_and_redacts_key(self):
        self.http.side_effect = HTTPError(
            "https://api.sarvam.ai/speech-to-text", 403, "Forbidden", {},
            self.response(error={"message": f"Rejected {FAKE_KEY}", "request_id": "error-id"}),
        )
        with self.assertRaises(sarvam.SarvamHTTPError) as raised:
            sarvam.transcribe(self.wav)
        error = raised.exception
        self.assertEqual(error.status, 403)
        self.assertIn("HTTP 403", str(error))
        self.assertIn("error-id", str(error))
        self.assertEqual(json.loads(error.body)["error"]["message"], "Rejected [redacted]")
        self.assertNotIn(FAKE_KEY, str(error))

    def test_direct_and_wrapped_timeouts(self):
        for error in (TimeoutError(), URLError(TimeoutError())):
            with self.subTest(error=type(error)):
                self.http.side_effect = error
                with self.assertRaisesRegex(sarvam.SarvamTimeoutError, "timed out"):
                    sarvam.transcribe(self.wav)

    def test_invalid_success_response(self):
        self.http.return_value = self.response(request_id="missing-transcript")
        with self.assertRaisesRegex(sarvam.SarvamError, "transcript"):
            sarvam.transcribe(self.wav)

    def test_success_fields_redact_echoed_key(self):
        self.http.return_value = self.response(transcript=f"Echoed {FAKE_KEY}", request_id=FAKE_KEY)
        transcript = sarvam.transcribe(self.wav)
        self.assertEqual(transcript.text, "Echoed [redacted]")
        self.assertEqual(transcript.request_id, "[redacted]")

    def test_invalid_tts_audio(self):
        self.http.return_value = self.response(audios=["%%invalid%%"])
        with self.assertRaisesRegex(sarvam.SarvamError, "invalid base64"):
            sarvam.synthesize("നമസ്കാരം")

    def run_smoke(self, *args):
        output, errors = io.StringIO(), io.StringIO()
        with patch.object(sarvam_smoke, "ROOT", self.root), redirect_stdout(output), redirect_stderr(errors):
            status = sarvam_smoke.main(list(args))
        return status, output.getvalue(), errors.getvalue()

    def test_smoke_default_writes_both_wavs_and_report(self):
        encoded = base64.b64encode(self.wav.read_bytes()).decode("ascii")
        self.http.side_effect = [
            self.response(audios=[encoded], request_id="ml-tts"),
            self.response(transcript=sarvam_smoke.QUESTIONS["ml-IN"], request_id="ml-stt"),
            self.response(transcript=sarvam_smoke.QUESTIONS["en-IN"], request_id="ml-to-en"),
            self.response(audios=[encoded], request_id="en-tts"),
            self.response(transcript=sarvam_smoke.QUESTIONS["en-IN"], request_id="en-stt"),
        ]
        status, output, errors = self.run_smoke()
        self.assertEqual((status, errors), (0, ""))
        self.assertIn(sarvam_smoke.SYNTHETIC_NOTE, output)
        for request_id in ("ml-tts", "ml-stt", "ml-to-en", "en-tts", "en-stt"):
            self.assertIn(request_id, output)
        [report_path] = (self.root / "runs").glob("sarvam-smoke-*.json")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["evidence"], "live")
        ml, en = report["checks"]
        self.assertEqual([ml["preference"], en["preference"]], ["ml-IN", "en-IN"])
        self.assertEqual(ml["transcription"]["english_translation"]["request_id"], "ml-to-en")
        self.assertIsNone(en["transcription"]["english_translation"])
        for check, tts_index, stt_index in ((ml, 0, 1), (en, 3, 4)):
            self.assertEqual(check["audio_source"], "synthetic_tts")
            self.assertEqual(check["character_similarity"], 1.0)
            self.assertEqual((report_path.parent / check["saved_wav"]).read_bytes(), self.wav.read_bytes())
            tts = self.http.call_args_list[tts_index].args[0]
            self.assertEqual(json.loads(tts.data)["language_code"], check["preference"])
            stt = self.http.call_args_list[stt_index].args[0]
            language_part = f'name="language_code"\r\n\r\n{check["preference"]}\r\n'.encode()
            self.assertIn(language_part, stt.data)
        self.assertNotIn(FAKE_KEY, report_path.read_text(encoding="utf-8"))
        self.assertEqual(self.http.call_count, 5)

    def test_smoke_supplied_wav_skips_tts(self):
        self.http.side_effect = [
            self.response(transcript=sarvam_smoke.QUESTIONS["en-IN"]),
        ]
        status, _, errors = self.run_smoke("--wav", str(self.wav), "--preference", "en-IN")
        self.assertEqual((status, errors), (0, ""))
        [report_path] = (self.root / "runs").glob("sarvam-smoke-*.json")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        [check] = report["checks"]
        self.assertEqual(check["audio_source"], "supplied_wav")
        self.assertEqual(check["preference"], "en-IN")
        self.assertIsNone(check["tts"])
        self.assertEqual(self.http.call_count, 1)
        self.assertEqual(list(report_path.parent.glob("*.wav")), [])

    def test_smoke_missing_key_is_blocked_and_writes_no_live_report(self):
        del os.environ["SARVAM_API_KEY"]
        for args in ((), ("--record", "--preference", "en-IN"), ("--wav", str(self.wav))):
            status, output, errors = self.run_smoke(*args)
            self.assertEqual((status, output, errors), (2, "", "BLOCKED: no SARVAM_API_KEY\n"))
        self.assertFalse((self.root / "runs").exists())
        self.http.assert_not_called()

    def test_smoke_records_one_preference_from_the_terminal(self):
        self.http.return_value = self.response(transcript=sarvam_smoke.QUESTIONS["en-IN"])
        with (
            patch.object(sarvam_smoke.sys.stdin, "isatty", return_value=True),
            patch("builtins.input", return_value=""),
            patch.object(sarvam_smoke.voice, "record_push_to_talk") as start,
            patch.object(sarvam_smoke.voice, "stop_recording", return_value=self.wav) as stop,
        ):
            status, _, errors = self.run_smoke("--record", "--preference", "en-IN")
        self.assertEqual((status, errors), (0, ""))
        start.assert_called_once_with()
        stop.assert_called_once_with()
        [report_path] = (self.root / "runs").glob("sarvam-smoke-*.json")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        [check] = report["checks"]
        self.assertEqual(check["audio_source"], "microphone")
        self.assertEqual(check["preference"], "en-IN")
        self.assertEqual(self.http.call_count, 1)
