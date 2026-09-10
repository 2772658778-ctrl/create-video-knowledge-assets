# Subagent Report

## Scope

- Input: `https://www.bilibili.com/video/BV1tHdoYnEGm`
- Selected profile: `deep-article`
- This run did not process `short-video-script` or `course-notes`.
- Existing `demos` were not modified.
- No commit was created.
- Sensitive authorization data was not copied into this report or any asset
  manifest/document/demo.

## Asset

- Asset path:
  `D:\秋招\个人作品\create-video-knowledge-assets\assets\bili-BV1tHdoYnEGm`
- Source identity: Bilibili `BV1tHdoYnEGm`
- Canonical URL:
  `https://www.bilibili.com/video/BV1tHdoYnEGm`
- Multipart check: passed; metadata returned one video and no part list.
- Title: `为什么除了中国，很少有国家吃笋呢？`
- Uploader: `赛博食录`
- Upload date: `2025-04-16`
- Duration: `708.948` seconds from metadata; downloaded media probes at
  `708.927667` seconds.
- Metadata: `source/metadata.json`
- Cover: `source/cover/BV1tHdoYnEGm.jpg`
- Downloaded video: `source/video/BV1tHdoYnEGm.mp4`
- Extracted audio: `source/asr/audio.wav`

## Acquisition And Transcription

- Runtime setup: passed via `scripts/setup-runtime.ps1`.
- Preflight: `yt-dlp`, `ffmpeg`, `ffprobe`, `whisper`, and `xelatex` were
  detected.
- URL normalization: passed; asset identity is `bili-BV1tHdoYnEGm`.
- Metadata acquisition: passed.
- Multipart metadata validation: passed.
- Platform subtitle acquisition: attempted through the VKA CLI; no subtitle
  SRT was returned.
- No reliable platform subtitle was available, so the run used Whisper ASR.
- Initial OpenAI Whisper `medium` loading hit a Windows certificate-store
  error (`ASN1: NOT_ENOUGH_DATA`). The verified model was later downloaded to
  `D:\秋招\个人作品\create-video-knowledge-assets\.cache\whisper\medium.pt`,
  but CPU transcription was too slow for this hardware.
- `faster-whisper` was then tested. CTranslate2 detected one CUDA device, but
  the GTX 1650 path failed because `cublas64_12.dll` was unavailable.
- Final usable ASR candidate: `faster-whisper base`, CPU `int8`, 4 threads,
  `beam_size=1`, VAD enabled, and previous-text conditioning disabled.
  It completed in about 68 seconds and produced 355 segments in
  `source/asr/audio-faster-base.srt`.
- The `faster-whisper base` model cache is under
  `D:\秋招\个人作品\create-video-knowledge-assets\.cache\hf\faster-whisper`.
- `source/asr/audio-faster-tiny.srt` and the earlier Whisper outputs are
  retained as comparison artifacts; they are not the selected downstream
  transcript.
- The selected base transcript was normalized and repaired conservatively.
  Downstream evidence uses `evidence/timeline.jsonl`; raw ASR remains in
  `evidence/timeline.raw.jsonl`, with repair provenance in
  `evidence/asr-repairs.json` and the review prompt in
  `evidence/asr-repair-prompt.md`.

## Outputs

- Evidence records and directly inspected frame records are present under
  `evidence/`.
- Knowledge records are present in `knowledge/units.jsonl`,
  `knowledge/relations.jsonl`, `knowledge/synthesis.json`, and
  `knowledge/outline.json`.
- Reusable content records are present in `content/units.jsonl` and
  `content/index.json`.
- The selected profile is `deep-article`; its selection is recorded in
  `views/deep-article/view-manifest.json`.
- Final projection plan, document, rendered Markdown/HTML/LaTeX, PDF, and
  stage verification remain to be checked by the main agent before acceptance.

## Quality Gates

- Source access: passed.
- Source metadata and single-part check: passed.
- Media decode/probe: passed.
- Subtitle quality gate: platform CC unavailable; ASR fallback used.
- ASR quality gate: base output is readable enough for conservative repair,
  but remaining uncertain rows must stay marked and must not be upgraded
  without evidence.
- Evidence grounding: frame candidates were extracted and six frames were
  directly inspected.
- Knowledge/content schema validation: generated artifacts are present and
  require main-agent validation.
- `verify-asset`, projection-plan validation, document validation, rendering,
  PDF compilation, and final image/path checks remain pending main-agent
  verification.

## Tests

- Earlier repository regression baseline: `494 passed, 6 skipped, 1 failed`;
  the failure was the pre-existing exact Q&A wording contract in
  `tests/test_skill_layout.py`.
- Focused transcript/content/projection/document regression tests later passed:
  `44 passed`.
- Final asset-specific verification is still pending.

## Risk And Required Recovery

- The selected transcript is ASR-derived and still contains uncertain or
  locally imperfect rows. The final article must not rely on unresolved rows
  for core claims.
- GPU acceleration remains unavailable until the matching CUDA/cuBLAS runtime
  is installed for the CTranslate2 build; the current result was produced on
  CPU and does not depend on that runtime.
- Main-agent acceptance must verify canonical hashes, evidence references,
  image paths, projection binding, document quality, and all selected output
  formats before treating this asset as complete.
