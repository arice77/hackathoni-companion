# Sarvam voice adapter

Checked against Sarvam's hosted REST documentation on **21 November 2026**. Both preferences passed the **live** synthetic round trip. The native recorder built successfully, and real-microphone capture is **blocked** pending macOS permission.

## Panel integration

Import these functions from `companion.voice`.

```python
LanguagePreference = Literal["ml-IN", "en-IN"]

record_push_to_talk() -> None
stop_recording() -> Path
ask(wav_path: str | Path, preference: LanguagePreference) -> VoiceTranscript
speak(text: str, preference: LanguagePreference) -> sarvam.SynthesisMeta | None
stop_speaking() -> None
```

- Map the panel's Malayalam and English options to `ml-IN` and `en-IN`. Keep the preference used for a voice turn through transcription, reply planning, overlay text and playback.
- Start capture on press on a worker, then call `stop_recording()` on release after startup has completed. On a first-use permission prompt, grant access and make a fresh press-to-talk recording. Only one recorder is active per Python process. The helper caps capture at 29 seconds, and release finalizes a 16 kHz mono 16-bit PCM WAV under `runs/`.
- `VoiceTranscript` extends the shared `Transcript`. Use `result.text` for the native transcript and `result.planner_text` for the English question. For Malayalam, `result.english_translation` is a second `Transcript` with its own request ID and latency. For English, `planner_text` uses the native transcript. Supply the planner with the observed English control labels and the preference for the reply.
- Pass the same preference and localized instruction to `speak` and show that instruction on the overlay. `ask` and `speak` block and belong on workers. `speak` returns TTS metadata when playback finishes, or `None` if interrupted. `stop_speaking()` terminates the current `afplay` process and prevents any in-flight synthesis from starting late playback.

### macOS microphone permission

The Python process starts a local Swift executable whose bundled name is **HackaThoni Microphone**. The helper calls AVFoundation to request microphone access. macOS can show the app responsible for launching it, such as **Terminal** when run there or **Conductor** when launched through that app. On the prompt asking to access the microphone, Abin should click **Allow** (or **OK** if that is what macOS shows) for the requesting app. If access was previously declined, Abin can enable that app in **System Settings → Privacy & Security → Microphone**. The authorization probe returned `notDetermined` on this Mac, so the displayed app name is still to be confirmed. [Apple media capture authorization](https://developer.apple.com/documentation/bundleresources/requesting-authorization-for-media-capture-on-macos)

On first capture the adapter compiles the helper into the gitignored `.context/voice-tools/` directory with the same `swiftc` toolchain used by the practice fixture. The helper embeds `NSMicrophoneUsageDescription` and records with `AVAudioRecorder`. Playback uses the system `/usr/bin/afplay`. No new Python dependencies are required. The PyObjC AVFoundation wrapper would also require CoreMedia and CoreAudio. [AVAudioRecorder](https://developer.apple.com/documentation/avfaudio/avaudiorecorder) · [Microphone usage description](https://developer.apple.com/documentation/bundleresources/information-property-list/nsmicrophoneusagedescription)

The adapter loads `SARVAM_API_KEY` from the process environment or the gitignored repo-root `.env`, in that order. It authenticates with the `api-subscription-key` header on every request. Sarvam also documents Bearer authentication for OpenAI-compatible clients. [Sarvam authentication](https://docs.sarvam.ai/api-reference/authentication)

## Speech-to-text and speech-to-English

Both calls use `POST https://api.sarvam.ai/speech-to-text` with `multipart/form-data` and an audio `file` part.

| Call | Multipart fields alongside `file` |
|---|---|
| Native transcript | `model=saarika:v2.5`, `language_code=ml-IN` or `en-IN` by preference |
| Malayalam audio to English | `model=saaras:v4`, `language_code=ml-IN`, `mode=translate` |

**Saarika v2.5 is deprecated.** The hosted endpoint accepted it with both language codes on 21 November 2026. Omit `mode` for Saarika. The current REST schema shows `saaras:v4` with `mode=transcribe` as the supported migration path. Saaras also supports `verbatim`, `translit`, and `codemix`, optional `with_timestamps`, and v4 `keyterms`. Omit the language code or pass `unknown` for automatic detection. [Saarika model guide](https://docs.sarvam.ai/api/getting-started/models/saarika) · [REST request reference](https://docs.sarvam.ai/api-reference/speech-to-text/transcribe)

REST accepts clips up to **30 seconds**. Supported containers and codecs include WAV, MP3, AAC, AIFF, Ogg, Opus, FLAC, MP4/M4A, AMR, WMA and WebM. Raw PCM requires `input_audio_codec` (`pcm_s16le`, `pcm_l16`, or `pcm_raw`) and 16 kHz input. The adapter accepts WAV files. Prefer mono WAV at 16 kHz for the demo. [Audio limits and recommendations](https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/rest-api)

The response contains `transcript`, `request_id`, and a nullable source `language_code`. The service can also return `language_probability` and requested timestamps. The adapter returns the shared `Transcript` with provider, model, request ID and HTTP latency in milliseconds. For native transcription it uses the returned language code when present and the requested code otherwise. For translation it sets `Transcript.language_code` to `en-IN` to describe the returned text. [REST response reference](https://docs.sarvam.ai/api-reference/speech-to-text/transcribe)

The legacy `POST https://api.sarvam.ai/speech-to-text-translate` route originally served `saaras:v2.5`. Its REST reference now lists `saaras:v3` as the default for that route. It takes multipart `file`, optional `model`, `prompt`, and `input_audio_codec`, automatically detects the input language, and returns English `transcript`, source `language_code`, and `request_id`. It documents the same short-clip limit and audio format families. [Legacy speech translation REST reference](https://docs.sarvam.ai/api-reference/legacy/speech-to-text-translate/translate)

## Text translation

`POST https://api.sarvam.ai/translate` takes a JSON body with `input`, `source_language_code`, `target_language_code`, and the selected `model`. Swap `ml-IN` and `en-IN` for the two directions. The adapter pins `sarvam-translate:v1`, which supports formal translation and up to **2,000 characters**. `mayura:v1` also supports the pair with up to **1,000 characters** and additional style and script settings. The service responds with `translated_text`, `source_language_code`, and `request_id`. The adapter's `translate_text` returns the translated string. This endpoint handles text only. [Text translation reference](https://docs.sarvam.ai/api-reference/text/translate-text)

## Text-to-speech

`POST https://api.sarvam.ai/text-to-speech` takes JSON with required `text` and `language_code`. Optional controls include `model`, `speaker`, `speech_sample_rate`, `output_audio_codec`, `pace`, `pitch`, `loudness`, `temperature`, `enable_preprocessing`, `dict_id` and `enable_cached_responses`. REST takes **1–2,500 characters**. The adapter pins `bulbul:v3` with the documented Malayalam speaker `shubh` (or a v3 speaker override), `language_code=ml-IN` or `en-IN`, and 16 kHz WAV. `bulbul:v4-flash` is the newer model. It accepts `ml-IN` but currently has no dedicated Malayalam persona. [TTS reference](https://docs.sarvam.ai/api-reference/text-to-speech/convert) · [Malayalam v3 voices](https://docs.sarvam.ai/api-reference-docs/api-guides-tutorials/text-to-speech/how-to/change-the-speaker-voice) · [v4 persona coverage](https://docs.sarvam.ai/api/api-guides-tutorials/text-to-speech/best-practices)

Supported output codecs are `wav`, `mp3`, `aac`, `flac`, `opus`, `linear16`, `mulaw` and `alaw`. REST supports 8, 16, 22.05, 24, 32, 44.1 and 48 kHz, with 22.05 kHz WAV as the default and a narrower rate set for Opus (8, 16, 24 or 48 kHz). The response contains `audios` (base64 strings) and `request_id`. For one utterance, `synthesize` returns the decoded WAV and metadata with model, language, speaker, request ID and HTTP latency. [TTS REST guide](https://docs.sarvam.ai/api/api-guides-tutorials/text-to-speech/rest-api)

## Chat completions for the planner

Use `POST https://api.sarvam.ai/v2/chat/completions` with `api-subscription-key` and a JSON body containing `model` and `messages` (role and content). `sarvam-105b` is a text-input model with a **128K-token context window** and support for Malayalam (`ml-IN`). Specify the desired language in the prompt. The chat request has no `language_code` field or audio input for this model. The V2 reference lists additional model IDs and `GET https://api.sarvam.ai/v2/models` provides model discovery. The legacy V1 route `POST https://api.sarvam.ai/v1/chat/completions` documents `sarvam-105b` and `sarvam-105b-conversations`. [Chat V2 reference](https://docs.sarvam.ai/api-reference/chat/chat-completions-v2) · [Chat V1 reference](https://docs.sarvam.ai/api-reference/chat/chat-completions-v1) · [Sarvam model and language coverage](https://docs.sarvam.ai/api/getting-started/models)

For a short call, send `stream: false`, set `max_tokens` to bound generation (default 2,048, including any reasoning tokens), and use `reasoning_effort: "none"` on V2 to disable reasoning. With `response_format.type` set to `json_schema`, pass the planner's schema in `response_format.json_schema`. Read `choices[0].message.content`, check `choices[0].finish_reason` for truncation, and retain the top-level `id` for tracing and `usage` for token counts. Validate the parsed control ID against the current Accessibility snapshot before showing a pointer. [V2 request and response reference](https://docs.sarvam.ai/api-reference/chat/chat-completions-v2) · [Sarvam reasoning settings](https://docs.sarvam.ai/api/token-factory/models)

## Smoke test

The first attempt returned exit code 2 with `BLOCKED: no SARVAM_API_KEY`. After a key became available, the **live** synthetic smoke test passed on 21 November 2026. Both native transcripts matched their reference text at 100% character similarity for this run. Saaras translated the Malayalam audio to “How to fill out this form?” The report is `runs/sarvam-smoke-20261121T143628.346348Z.json` in the adapter worktree.

1. Sign in to the Sarvam dashboard, open **API Keys**, and create a key. [Dashboard](https://indus.sarvam.ai/) · [Key setup](https://docs.sarvam.ai/api-reference/authentication)
2. In the shell running the smoke test, set `export SARVAM_API_KEY='...'`. Alternatively, add `SARVAM_API_KEY=...` to the gitignored repo-root `.env`. Replace the ellipsis locally.
3. Run the synthetic check. For real speech, capture a WAV with `--record` in an interactive terminal or supply the recording with `--wav`.

   ```sh
   .venv/bin/python scripts/sarvam_smoke.py
   .venv/bin/python scripts/sarvam_smoke.py --record --preference ml-IN
   .venv/bin/python scripts/sarvam_smoke.py --record --preference en-IN
   .venv/bin/python scripts/sarvam_smoke.py --wav /path/to/form-question.wav --preference en-IN
   ```

The default run synthesizes “ഈ ഫോം എങ്ങനെ പൂരിപ്പിക്കാം?” and “How do I fill this form?” and saves both WAVs under `runs/`. TTS→STT uses synthetic audio and doesn't replace a real-microphone test. Recorded and supplied WAV modes skip TTS and use Malayalam unless a preference is supplied. The similarity score uses Unicode-normalized, case-folded characters with whitespace collapsed.

A completed live run prints the texts, similarity, HTTP latencies and request IDs. It saves `runs/sarvam-smoke-<timestamp>.json` with evidence `live` and the audio source for each preference. The check requires nonempty native and planner transcripts. The CLI returns 1 for a failed check or request and 2 for a missing key, denied mic access or a noninteractive `--record` launch. The adapter exposes HTTP status and the Sarvam error body with credential redaction and uses a 30-second socket timeout. For **mock** tests, run `.venv/bin/python -m unittest tests.test_sarvam tests.test_sarvam_voice`.
