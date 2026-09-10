---
name: create-video-knowledge-assets
description: Create evidence-backed Chinese video summaries, notes, articles, and scripts from Bilibili URLs or local knowledge videos. Use when Codex needs to produce a deep video summary, course notes, creator article, enterprise knowledge record, research brief, or short-video script with PDF as the primary deliverable and optional HTML or Markdown from the same document view.
---

# Create Video Knowledge Assets

Use this workflow for a Bilibili URL or a local video containing knowledge content. Keep the work evidence-first: every knowledge claim must trace back to transcript windows or checked visual frames. The main product boundary is the four production profiles (`deep-summary`, `deep-article`, `short-video-script`, `course-notes`), with PDF as the primary reader deliverable. HTML and Markdown must come from the same renderer-neutral document rather than separate rewrites.

## Profile And Input Selection

- Accept a Bilibili URL or a local video as input. Before acquiring or retaining any source, read `references/p2-u1-workflow.md` for input identity, recovery, retention, and L2 cleanup rules.
- Read `references/acquisition-recipes.md` before downloading subtitles, cover images, audio, video, or candidate frames. Use its direct commands only inside the current asset and evidence boundaries.
- Default to the `general-deep` profile for a deep summary. Read `references/profile-general-deep.md` before planning or writing that reader-facing explanation.
- Select the `course-notes` profile only when the user explicitly requests course notes, a teaching handout, or a course-notes PDF. Read `references/profile-course-notes.md` before producing it; the P1 teaching and visual quality gates remain mandatory for that route.
- Do not silently convert a local video or a Bilibili tutorial into course notes just because it is educational. Ask for clarification when the requested profile is ambiguous.
- Use `creator-article`, `enterprise-knowledge`, `research-brief`, and `short-video-script` only when the user explicitly requests that business view. Read `references/profile-routing.md`, `references/p3-profile-workflow.md`, `references/p3-profile-authoring.md`, `references/projection-plan.md`, the selected profile reference, and `references/document-schema.md` before authoring it.

## Required Workflow

1. Run preflight before any extraction or generation. Check the tools required by the selected path: Bilibili acquisition needs `yt-dlp`; local-video inspection needs `ffprobe`; frame and audio extraction need `ffmpeg`; missing or unreliable CC needs `faster-whisper`; PDF compilation needs `xelatex`. If a required tool is missing, stop or degrade only according to `references/p1-workflow.md`, and report the missing items.
2. Inspect Bilibili metadata before processing: title, duration, cover, available subtitles, and part list. If the source has multiple Bilibili parts, stop and ask the user which part or range to process.
3. Prefer reliable human CC subtitles. If no reliable CC exists, run `vka transcribe-asr` (faster-whisper, base, cpu, int8). Preserve the raw SRT, normalize it into `timeline.raw.jsonl` with `--id-prefix raw-`, review the transcript line by line as described in `references/transcript-repair.md`, and apply the reviewed sheet with `--parent-prefix raw-` to write `timeline.jsonl`. Read `vka timeline-digest` output when you build knowledge units instead of re-reading the full JSONL.
4. Create the asset with `vka create-asset --assets-root <root> --input <normalized-input.json> [--config <config.json>] [--tool-version name=value]`. Store raw inputs and downloads under `source/`; store `timeline.jsonl`, frame manifests, and grounding records under `evidence/`. Record every finished stage with `vka complete-stage --asset <asset> --stage <stage> --output <path>` (repeat `--output` per artifact). Never hand-write `manifest.json`, and never hash stage outputs in a throwaway script.
5. Build chapters around transcript time windows, then sample frames densely inside each chapter window. Inspect final images directly for relevance and clarity; do not use OCR text or subtitles as a substitute for visual judgment.
6. Build a rich knowledge layer, not a thin summary: include concepts, mechanisms, examples, formulas, visual states, misconceptions, transitions, and takeaways with `evidence_refs` and a schema-valid `epistemic_status`.
7. Build the reader-facing plan from the evidence and knowledge layers. Run `vka validate-knowledge --asset <asset>` before any profile projection: it fails when a `video_explicit` unit cites nothing but uncertain transcript rows or provenance-only records. For the default `general-deep` profile, create the outline required by `references/profile-general-deep.md`. For an explicit `course-notes` request, generate `knowledge/teaching_outline.json` and validate it with `vka validate-teaching-outline`. Do not project `knowledge/units.jsonl` directly into any reader-facing format.
8. For `general-deep` and `course-notes`, generate and validate one renderer-neutral document, then render the requested Markdown, HTML, and LaTeX outputs from it. Compile and inspect PDF as the primary deliverable unless the user explicitly requests a non-PDF-only result. Publish a shareable copy with `vka package-demo --asset <asset> --profile <profile>`: it copies the cover and the cited inspected frames next to the document and rewrites their paths. For `course-notes`, the title page must include a concise theme, a one-sentence core summary, and source metadata such as video title, author/uploader, publish date, and subtitle/transcript source. PDF output should show compact source-time footnotes at the bottom of the page; keep structured provenance in JSON for all formats. Do not render or deliver one-sentence chapter summaries, unresolved `???` placeholders, unreviewed ASR, uninspected visual claims, or notes that fail to teach the video's main idea.
9. Before R3 profile projection, run `vka verify-asset --asset <asset>`. Build, validate, and persist the selected profile's `projection-plan.json` before drafting its supplied authored document. When a directly inspected usable frame exists, include it as a grounded `image` block; do not replace it with a textual description. R3 may write `views/<profile_id>` and `outputs/<profile_id>` only; it must not change `source/`, `evidence/`, or `knowledge/`. Verify canonical hashes before and after projection, then close the view with `vka complete-stage --stage views/<profile_id>` and the render with `vka complete-stage --stage outputs/<profile_id>`. When a stage artifact changes after it was recorded, re-run `complete-stage` for that stage instead of leaving `verify-asset` failing.

## References

- Read `references/acquisition-recipes.md` before acquiring subtitles, cover images, audio, video, or candidate frames, and before deciding whether an acquisition artifact belongs in `source/` or `evidence/`.
- Read `references/p2-u1-workflow.md` before accepting a local video, normalizing a Bilibili URL, retaining source material, recovering an interrupted run, or issuing an L2 cleanup decision.
- Read `references/evidence-schema.md` before generating evidence artifacts, timeline records, frame observations, or source-span references.
- Read `references/knowledge-schema.md` before generating knowledge artifacts or assigning `epistemic_status`.
- Read `references/profile-general-deep.md` before drafting the default `general-deep` view or its authoring plan.
- Read `references/teaching-outline.md` before converting knowledge units into course-note prose.
- Read `references/profile-course-notes.md` before drafting the course-notes view, creating renderer input, or deciding whether the notes are pedagogically complete.
- Read `references/profile-routing.md` before selecting an explicit profile, choosing formats, or recording a selection reason.
- Read `references/p3-profile-workflow.md` before reprojecting a completed asset into creator, enterprise, or research profile views.
- Read `references/p3-profile-authoring.md` before drafting a creator article, enterprise knowledge document, or research brief. It defines the distinct reader purpose, figure plan, and zero-value-output stop conditions for those profiles.
- Read `references/projection-plan.md` before writing, validating, or binding a P3 projection plan. It is the versioned transfer contract and defines the future declarative profile-pack boundary.
- Read `references/document-schema.md` before drafting any profile document or rendering a profile-selected document.
- Read `references/p1-workflow.md` before making any gate decision about preflight tools, source quality, multipart selection, ASR quality, frame completeness, evidence references, or PDF compilation.
- Read `references/transcript-repair.md` before using Whisper ASR output for knowledge extraction or course-note prose.

### Future Q&A

Q&A is not part of the main product boundary. It may become a separate
future skill that consumes the same asset protocol after a course-notes asset
is complete.
