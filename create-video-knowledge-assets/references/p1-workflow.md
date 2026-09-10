# P1 Workflow Decisions

Use these gates to decide whether to continue, degrade the output, or stop and ask the user.

## Preflight Tools

- Continue: every tool required by the selected path is available. Bilibili acquisition requires `yt-dlp`; local-video inspection requires `ffprobe`; frame and audio extraction require `ffmpeg`; ASR requires `whisper` only when reliable CC is unavailable; PDF compilation requires `xelatex`.
- Degrade: an optional path can be skipped without breaking the requested deliverable, such as skipping ASR when reliable CC exists.
- Stop and ask user: a required tool for the requested deliverable is missing and no schema-valid degraded path can produce the deliverable.

## Multipart Bilibili Source

- Continue: the URL resolves to a single part, or the user explicitly selected one part or a part range.
- Degrade: do not degrade silently for multipart ambiguity.
- Stop and ask user: the source has multiple parts and the user did not specify which part or range to process.

## CC Subtitle Quality

- Continue: reliable human CC is available, language matches the expected content, timestamps align with speech, and coverage is near complete.
- Degrade: CC exists but has minor gaps, light timestamp drift, or mixed terminology; keep the original SRT, note limitations, and repair only through transcript-window evidence.
- Stop and ask user: CC is unrelated, machine-garbled, wrong language, severely incomplete, or impossible to align, and ASR cannot be run.

## ASR Quality

- Continue: Whisper output is intelligible, mostly complete, and timestamps align well enough to support chapter windows and evidence references.
- Continue after repair: Whisper output has local term or punctuation errors, but the ASR repair prompt has been reviewed, `timeline.raw.jsonl` and `timeline.jsonl` are both preserved, and repaired rows record `original_content` plus repair metadata.
- Degrade: ASR has local errors, names or formulas are unclear, or noisy segments remain after repair; mark affected knowledge units as `insufficient_evidence` unless the claim can be supported as `video_explicit` by another evidence item.
- Stop and ask user: ASR fails, produces unusable text, or the audio is too poor to ground the notes.

## Keyframe Completeness

- Continue: each chapter has enough directly inspected frames to verify slides, diagrams, demos, formulas, code, or other visual evidence mentioned in notes.
- Degrade: some windows have weak visuals or repeated frames; omit unsupported visual claims or rely on transcript evidence only, using `video_explicit` when the transcript directly supports the unit and `insufficient_evidence` when it does not.
- Stop and ask user: essential visual material cannot be extracted, decoded, or inspected, and the task requires visual grounding.

## Evidence References

- Continue: every knowledge unit has valid `evidence_refs` pointing to evidence records for transcript windows, inspected frames, source files, or derived manifests.
- Stop and repair: a knowledge or content unit is marked `video_explicit` while every citation is an uncertain transcript row or a provenance-only metadata/audio record. `vka validate-knowledge --asset "$ASSET_DIR"` fails this case; cite a checked frame or a reviewed transcript row, or downgrade the unit.
- Degrade: nonessential enrichment lacks video evidence; remove it, attach external evidence and mark it `external_enrichment`, or mark it `agent_inference` only when cited evidence supports the inference.
- Stop and ask user: core claims, chapter boundaries, or examples cannot be tied to evidence.

## PDF Compilation

- Continue: LaTeX compiles successfully, figures render, citations are present, and the PDF opens without missing assets.
- Degrade: minor typography, line breaking, or noncritical figure placement issues remain; report them and keep the verified source artifacts.
- Stop and ask user: `xelatex` is missing, compilation fails, required fonts/assets are unavailable, or the PDF cannot be opened or validated.

## Document Quality

- Continue: `vka validate-teaching-outline` and `vka validate-document` both pass, headings render as real Chinese text, prose is long enough to teach, visual claims have inspected frame evidence, and each major section has a chapter summary.
- Degrade: minor typography or figure placement issues remain, but the Markdown/JSON semantic view is complete and readable; report the limitation and keep editable artifacts.
- Stop and repair: the view contains `???`, one-sentence summaries, timestamp clutter outside controlled PDF source footnotes, one-second timestamp guesses in provenance, missing title-page source metadata, weak first-chapter core framing, missing final synthesis, missing teaching images, unreviewed ASR-derived claims, or a document generated directly from knowledge units without a validated teaching outline.
