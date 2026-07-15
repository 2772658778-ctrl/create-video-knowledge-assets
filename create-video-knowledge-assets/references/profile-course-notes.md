# Course-Notes Profile

Use this profile when generating the Chinese `course-notes` view. The notes must be teachable, evidence-backed, and useful without replaying the whole video.

## Required Structure

Include all of the following:

- Learning objectives: state what the learner should understand or be able to do after the lesson.
- Prerequisite knowledge: list the concepts, tools, math, or programming background assumed by the video.
- Motivation: explain why the topic matters and what problem the lesson is solving.
- Concepts: define the core terms and distinguish similar ideas.
- Mechanisms: explain how the process, system, algorithm, proof, or implementation works.
- Examples: include worked examples or concrete cases from the video where available.
- Formula or code explanations: explain formulas, derivations, code blocks, commands, configuration, or pseudocode that appear in the transcript or frames.
- Chapter summaries: end each chapter with the main takeaway and unresolved questions if any.
- Title-page promise: include `theme`, `one_sentence_summary`, and source `metadata` so the first page states what the video is about, why it matters, and where the data came from.
- Source provenance: keep timestamped `source_spans` on claims, examples, formulas, code explanations, and visual observations for validation and later QA. Render compact source-time footnotes in the PDF at the bottom of the page. Markdown/HTML may stay clean by default, but must preserve the same structured provenance in `document.json`.
- Final synthesis and extension: conclude with an integrated summary, common mistakes, practice prompts, and sensible next topics.

Use a reader-facing hierarchy comparable to `bilibili-render-pdf`: every major teaching chapter before the final synthesis should contain at least two meaningful `subsection` blocks before its `本章小结` subsection. Good chapter shapes include `动机 -> 机制 -> 本章小结`, `错误直觉 -> 修正方案 -> 本章小结`, or `例子 -> 公式/实现 -> 本章小结`. Do not submit a chapter that only has a single subsection such as `2.1`, and do not rely on one long paragraph plus a figure as a chapter.

For visual lecture videos, align images to the concept they teach. Mechanism chapters that introduce a new visual state, formula stage, projection, architecture, demo, or geometric relationship should include the inspected frame for that state near the relevant subsection. Do not skip a key frame merely because the chapter already has a formula or teaching box. Prefer the fully revealed readable frame over early sparse frames, and crop or replace frames with large unused dark areas when the relevant content would otherwise be hard to read at PDF scale.

Before drafting `document.json`, create and validate `knowledge/teaching_outline.json`. Treat knowledge units as factual ingredients and the teaching outline as the authoring plan. Do not map one knowledge unit to one section or one paragraph. Merge, reorder, and rewrite units into a coherent explanation that a learner can follow without watching the video.

The first chapter is the golden prelude. It must quickly deliver the video's core question or main thesis in plain language, then unfold enough depth that a reader knows why the rest of the document is worth reading. Use a high-signal box near the opening for the core insight, followed by at least two teaching moves such as motivation, wrong intuition, roadmap, concrete example, or mechanism preview. This rule is generic: adapt the opening to the video's subject and audience rather than using a QKV- or technical-lecture-specific template.

## Minimum Quality Floor

Before rendering final LaTeX/PDF, run `vka validate-document --input views/course-notes/document.json`.

The view is not acceptable if it:

- contains unresolved `???`, replacement characters, or garbled headings;
- is mostly one-sentence summaries instead of teaching prose;
- lacks a concise title-page theme, one-sentence core summary, or source metadata;
- fails to make the first chapter a readable golden prelude with a core insight near the opening;
- lacks chapter-level motivation, mechanism, examples, at least two semantic subsections, and chapter summaries;
- has flat top-level chapters with no `subsection` blocks, or chapters whose only subsection is a summary;
- reads like a chronological evidence digest or schema projection instead of a teacher-authored lesson;
- lacks a validated teaching outline with motivation, mechanism, example/formula/visual, misconception, and takeaway moves;
- lacks a final synthesis/extension section;
- cites only one-second timestamp guesses instead of transcript windows;
- includes too few directly inspected teaching images for the lecture's visual explanations, or omits frames for major visual states such as projections, matching scores, normalization, or final weighted output;
- lacks high-signal teaching blocks such as key ideas, background notes, or common mistakes.

Use `vka render-markdown --input views/course-notes/document.json --output outputs/course-notes.md` or `vka render-html --input views/course-notes/document.json --output outputs/course-notes.html` as an iteration surface when prose is weak. Render to PDF only after the semantic view passes the quality gate.

## Evidence Rules

Every chapter and paragraph should preserve `evidence_refs` from timeline records, inspected frames, or other evidence records so knowledge can be traced back to evidence. Use only schema-valid knowledge statuses: `video_explicit`, `agent_inference`, `external_enrichment`, or `insufficient_evidence`. Mark unsupported or weak interpretation as `insufficient_evidence`, and avoid presenting it as video-supported fact.

## Renderer Input Contract

For the `render-course` document view, every paragraph block must include a non-empty `source_spans` list. Each span must have the shape `{start_ms,end_ms}` with integer millisecond offsets where `end_ms` is greater than `start_ms`. These spans are required for grounding and quality gates. The LaTeX/PDF renderer turns them into bottom-of-page source-time footnotes; Markdown/HTML renderers validate them but do not need to show them inline.

Derive each paragraph block's `source_spans` from its `evidence_refs`: resolve the referenced evidence records, collect their video `spans`, and copy only the time ranges that support that paragraph. Do not send a paragraph block to the renderer if its source spans are empty.

Supported renderer block kinds are `paragraph`, `subsection`, `bullet_list`, `numbered_list`, `importantbox`, `knowledgebox`, `warningbox`, `formula`, `code`, `quote`, and `image`. Prefer these semantic blocks over encoding visual style in prose.

At the top level, include `teaching_outline_ref`, normally `knowledge/teaching_outline.json`, so the reader-facing document is explicitly derived from the validated teaching outline.

Also include `theme`, `one_sentence_summary`, and `metadata`. Required metadata fields for Bilibili course notes are `source_title`, `author` or `uploader`, `publish_date`, and at least one of `subtitle_source`, `transcript_source`, or `data_sources`. If a field is unknown after metadata inspection, state that explicitly rather than omitting it.

Place `subsection` blocks before the paragraphs, figures, formulas, or lists they organize. For each non-final chapter, include a closing `subsection` titled `本章小结` followed by a teaching paragraph grounded in source spans.

Keep outline move labels such as `synthesis`, `motivation`, `mechanism`,
`takeaway`, and `practice` inside `knowledge/teaching_outline.json` only. Do not
render these internal schema labels into user-visible section or subsection
titles; rewrite them as natural Chinese teaching headings.
