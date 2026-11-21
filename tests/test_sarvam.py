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
            "model": "saaras:v4", "language_code": "ml-IN", "mode": "transcribe",
        })
        self.assertIsInstance(result, Transcript)
        self.assertEqual(result.text, "നമസ്കാരം")
        self.assertEqual(result.language_code, "ml-IN")
        self.assertEqual(result.provider, "sarvam")
        self.assertEqual(result.model, "saaras:v4")
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

    def test_smoke_default_writes_wav_and_report(self):
        encoded = base64.b64encode(self.wav.read_bytes()).decode("ascii")
        self.http.side_effect = [
            self.response(audios=[encoded], request_id="tts-id"),
            self.response(transcript=sarvam_smoke.QUESTION, request_id="native-id"),
            self.response(transcript="How do I file this month's GST return?", request_id="english-id"),
        ]
        status, output, errors = self.run_smoke()
        self.assertEqual((status, errors), (0, ""))
        self.assertIn(sarvam_smoke.SYNTHETIC_NOTE, output)
        for request_id in ("tts-id", "native-id", "english-id"):
            self.assertIn(request_id, output)
        [report_path] = (self.root / "runs").glob("sarvam-smoke-*.json")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["evidence"], "live")
        self.assertEqual(report["audio_source"], "synthetic_tts")
        self.assertEqual(report["character_similarity"], 1.0)
        self.assertEqual((report_path.parent / report["generated_wav"]).read_bytes(), self.wav.read_bytes())
        self.assertNotIn(FAKE_KEY, report_path.read_text(encoding="utf-8"))
        self.assertEqual(self.http.call_count, 3)

    def test_smoke_supplied_wav_skips_tts(self):
        self.http.side_effect = [
            self.response(transcript=sarvam_smoke.QUESTION),
            self.response(transcript="How do I file this month's GST return?"),
        ]
        status, _, errors = self.run_smoke("--wav", str(self.wav))
        self.assertEqual((status, errors), (0, ""))
        [report_path] = (self.root / "runs").glob("sarvam-smoke-*.json")
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["audio_source"], "supplied_wav")
        self.assertIsNone(report["tts"])
        self.assertEqual(self.http.call_count, 2)
        self.assertEqual(list(report_path.parent.glob("*.wav")), [])

    def test_smoke_missing_key_is_blocked_and_writes_no_live_report(self):
        del os.environ["SARVAM_API_KEY"]
        status, output, errors = self.run_smoke()
        self.assertEqual((status, output, errors), (2, "", "BLOCKED: no SARVAM_API_KEY\n"))
        self.assertFalse((self.root / "runs").exists())
        self.http.assert_not_called()
