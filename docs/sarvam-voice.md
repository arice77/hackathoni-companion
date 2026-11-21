# Sarvam voice adapter

Checked against Sarvam's hosted REST documentation on **21 November 2026**. The adapter passed **mock** HTTP tests. The live smoke attempt is **blocked**.

## Malayalam speech for the GSTR-3B demo

Use `translate_speech_to_english(wav_path)` to turn the owner's Malayalam question into English for the planner. Saaras v4's `translate` mode does this in one upload and returns English text in `transcript`. Use `transcribe(wav_path)` when you also need the Malayalam text for display. Pass the observed English control labels to the planner verbatim so the model can match the question against the actual screen. [Speech-to-text REST guide](https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/rest-api)

The adapter loads `SARVAM_API_KEY` from the process environment or the gitignored repo-root `.env`, in that order. It authenticates with the `api-subscription-key` header on every request. Sarvam also documents Bearer authentication for OpenAI-compatible clients. [Sarvam authentication](https://docs.sarvam.ai/api-reference/authentication)

## Speech-to-text and speech-to-English

Both calls use `POST https://api.sarvam.ai/speech-to-text` with `multipart/form-data`. Send the audio as the required `file` part, `model=saaras:v4`, and `language_code=ml-IN` for Malayalam. Use `mode=transcribe` for Malayalam output and `mode=translate` for English output. Omit `language_code` or use `unknown` for automatic detection. The API also supports `verbatim`, `translit`, and `codemix`, optional `with_timestamps`, and v4 `keyterms`. `saaras:v3` is the legacy model listed in the current REST schema. [REST request reference](https://docs.sarvam.ai/api-reference/speech-to-text/transcribe)

REST accepts clips up to **30 seconds**. Supported containers and codecs include WAV, MP3, AAC, AIFF, Ogg, Opus, FLAC, MP4/M4A, AMR, WMA and WebM. Raw PCM requires `input_audio_codec` (`pcm_s16le`, `pcm_l16`, or `pcm_raw`) and 16 kHz input. The adapter accepts WAV files. Prefer mono WAV at 16 kHz for the demo. [Audio limits and recommendations](https://docs.sarvam.ai/api/api-guides-tutorials/speech-to-text/rest-api)

The response contains `transcript`, `request_id`, and a nullable source `language_code`. The service can also return `language_probability` and requested timestamps. The adapter returns the shared `Transcript` with provider, model, request ID and HTTP latency in milliseconds. For native transcription it uses the returned language code when present and the requested code otherwise. For translation it sets `Transcript.language_code` to `en-IN` to describe the returned text. [REST response reference](https://docs.sarvam.ai/api-reference/speech-to-text/transcribe)

**Saarika** (`saarika:v2.5`) was the native-transcription model on the same `/speech-to-text` route. It took the audio `file` and optional `language_code` such as `ml-IN` or `unknown`, with the same 30-second cap, and returned the route's `transcript`, `language_code` and `request_id`. Sarvam now marks Saarika as deprecated and omits it from the current REST model enum. [Saarika model guide](https://docs.sarvam.ai/api/getting-started/models/saarika) · [Saarika default change](https://docs.sarvam.ai/changelog/2026/6/29)

The legacy `POST https://api.sarvam.ai/speech-to-text-translate` route originally served `saaras:v2.5`. Its REST reference now lists `saaras:v3` as the default for that route. It takes multipart `file`, optional `model`, `prompt`, and `input_audio_codec`, automatically detects the input language, and returns English `transcript`, source `language_code`, and `request_id`. It documents the same short-clip limit and audio format families. [Legacy speech translation REST reference](https://docs.sarvam.ai/api-reference/legacy/speech-to-text-translate/translate)

## Text translation

`POST https://api.sarvam.ai/translate` takes a JSON body with `input`, `source_language_code`, `target_language_code`, and the selected `model`. Swap `ml-IN` and `en-IN` for the two directions. The adapter pins `sarvam-translate:v1`, which supports formal translation and up to **2,000 characters**. `mayura:v1` also supports the pair with up to **1,000 characters** and additional style and script settings. The service responds with `translated_text`, `source_language_code`, and `request_id`. The adapter's `translate_text` returns the translated string. This endpoint handles text only. [Text translation reference](https://docs.sarvam.ai/api-reference/text/translate-text)

## Text-to-speech

`POST https://api.sarvam.ai/text-to-speech` takes JSON with required `text` and `language_code`. Optional controls include `model`, `speaker`, `speech_sample_rate`, `output_audio_codec`, `pace`, `pitch`, `loudness`, `temperature`, `enable_preprocessing`, `dict_id` and `enable_cached_responses`. REST takes **1–2,500 characters**. The adapter pins `bulbul:v3` with the documented Malayalam speaker `shubh` (or a v3 speaker override), `language_code=ml-IN`, and 16 kHz WAV. `bulbul:v4-flash` is the newer model. It accepts `ml-IN` but currently has no dedicated Malayalam persona. [TTS reference](https://docs.sarvam.ai/api-reference/text-to-speech/convert) · [Malayalam v3 voices](https://docs.sarvam.ai/api-reference-docs/api-guides-tutorials/text-to-speech/how-to/change-the-speaker-voice) · [v4 persona coverage](https://docs.sarvam.ai/api/api-guides-tutorials/text-to-speech/best-practices)

Supported output codecs are `wav`, `mp3`, `aac`, `flac`, `opus`, `linear16`, `mulaw` and `alaw`. REST supports 8, 16, 22.05, 24, 32, 44.1 and 48 kHz, with 22.05 kHz WAV as the default and a narrower rate set for Opus (8, 16, 24 or 48 kHz). The response contains `audios` (base64 strings) and `request_id`. For one utterance, `synthesize` returns the decoded WAV and metadata with model, language, speaker, request ID and HTTP latency. [TTS REST guide](https://docs.sarvam.ai/api/api-guides-tutorials/text-to-speech/rest-api)

## Chat completions for the planner

Use `POST https://api.sarvam.ai/v2/chat/completions` with `api-subscription-key` and a JSON body containing `model` and `messages` (role and content). `sarvam-105b` is a text-input model with a **128K-token context window** and support for Malayalam (`ml-IN`). Specify the desired language in the prompt. The chat request has no `language_code` field or audio input for this model. The V2 reference lists additional model IDs and `GET https://api.sarvam.ai/v2/models` provides model discovery. The legacy V1 route `POST https://api.sarvam.ai/v1/chat/completions` documents `sarvam-105b` and `sarvam-105b-conversations`. [Chat V2 reference](https://docs.sarvam.ai/api-reference/chat/chat-completions-v2) · [Chat V1 reference](https://docs.sarvam.ai/api-reference/chat/chat-completions-v1) · [Sarvam model and language coverage](https://docs.sarvam.ai/api/getting-started/models)

For a short call, send `stream: false`, set `max_tokens` to bound generation (default 2,048, including any reasoning tokens), and use `reasoning_effort: "none"` on V2 to disable reasoning. With `response_format.type` set to `json_schema`, pass the planner's schema in `response_format.json_schema`. Read `choices[0].message.content`, check `choices[0].finish_reason` for truncation, and retain the top-level `id` for tracing and `usage` for token counts. Validate the parsed control ID against the current Accessibility snapshot before showing a pointer. [V2 request and response reference](https://docs.sarvam.ai/api-reference/chat/chat-completions-v2) · [Sarvam reasoning settings](https://docs.sarvam.ai/api/token-factory/models)

## Smoke test

**Blocked on 21 November 2026.** `.venv/bin/python scripts/sarvam_smoke.py` returned exit code 2 and printed `BLOCKED: no SARVAM_API_KEY`. No live audio result or provider request ID was obtained.

1. Sign in to the Sarvam dashboard, open **API Keys**, and create a key. [Dashboard](https://indus.sarvam.ai/) · [Key setup](https://docs.sarvam.ai/api-reference/authentication)
2. In the shell running the smoke test, set `export SARVAM_API_KEY='...'`. Alternatively, add `SARVAM_API_KEY=...` to the gitignored repo-root `.env`. Replace the ellipsis locally.
3. Run the synthetic check and then supply a microphone WAV of the same question.

   ```sh
   .venv/bin/python scripts/sarvam_smoke.py
   .venv/bin/python scripts/sarvam_smoke.py --wav /path/to/gst-question.wav
   ```

The default run synthesizes “ഈ മാസത്തെ GST റിട്ടേണ്‍ എങ്ങനെ ഫയല്‍ ചെയ്യും?” (“How do I file this month's GST return?”), saves the WAV under `runs/`, then requests Malayalam transcription and direct English translation. TTS→STT uses synthetic audio and doesn't replace a real-microphone test. The supplied-WAV mode skips TTS and compares the Malayalam transcription to the same fixed question. The similarity score uses Unicode-normalized, case-folded characters with whitespace collapsed. Review the actual Malayalam and English texts to assess recognition and meaning.

A completed live run prints the texts, similarity, HTTP latencies and request IDs. It saves `runs/sarvam-smoke-<timestamp>.json` with evidence `live` and the audio source. A nonempty transcript in both modes passes the transport smoke check. The CLI returns 1 for a failed check or request and 2 for a missing key. The adapter exposes HTTP status and the Sarvam error body with credential redaction, and uses a 30-second socket timeout. For mock checks without a key, run `.venv/bin/python -m unittest tests.test_sarvam`.
