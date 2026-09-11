# Creator Article Profile

Use `creator-article` for a reader-facing article built from a completed
canonical knowledge layer. It creates only
`views/creator-article/document.json`; rendering is a separate step and must
not add facts.

`creator-article` remains available for compatibility. `deep-article` currently
uses the same six semantic sections and source-boundary rules while providing a
separate explicit profile ID for long-form article routing.

## Source Boundary

Read `knowledge/units.jsonl`, `knowledge/relations.jsonl`,
`knowledge/synthesis.json`, and the evidence records named by the selected
knowledge units. Do not use prompt anecdotes, prior author knowledge, or a
new web search as source material. Preserve each block's `knowledge_refs`,
`evidence_refs`, and video `source_spans`.

## Sections

The article must contain these semantic sections in order:

1. `reader_promise`: what the reader can understand or do after reading.
2. `core_point`: the source-backed central claim.
3. `narrative`: a coherent problem-to-method explanation.
4. `video_evidence`: concrete video evidence with source spans.
5. `actionable_takeaway`: actions faithfully derived from the source.

Scope, uncertainty, and source navigation do **not** belong in the article.
They go in the document's `notes` part and ship as a separate PDF, so the
article's table of contents stays a description of the video rather than a
description of the pipeline. See `document-schema.md`.

## Long-Form Craft

A reader decides in the first two paragraphs. The gate enforces three rules,
because each of them marks writing that sounds generated rather than written
for a person:

- **Open on the reader's situation, not on an announcement.** `在当今这个时代`,
  `随着…的发展`, `近年来`, `众所周知`, `大家好` are rejected. Name the moment the
  reader is actually in — a task, an hour, a stuck decision — before you name
  the topic.
- **No announcement register.** `综上所述`, `值得注意的是`, `接下来我们将`, and the
  business vocabulary `赋能` / `抓手` / `底层逻辑` / `打通` are rejected. They
  signal a template, and they carry no information.
- **Keep the claim and the evidence adjacent.** Every block keeps its
  `knowledge_refs` and `evidence_refs`, so a reader can move from a sentence to
  the moment in the video that supports it.

Two more things separate a readable article from a summary:

- Paragraphs should hand off. A paragraph that ends on a question sets up the
  next one; a paragraph that ends on a conclusion stops the read.
- Close by landing the argument, not by summarizing it. The last section
  states the boundary; it should not restate every heading on the way out.

Before drafting, follow `p3-profile-authoring.md`. The article's opening must
answer a reader problem and state the central claim in reader language. Its
`narrative` must explain the transition between the problem, method, and result
rather than paraphrasing the transcript in timestamp order. Make
`actionable_takeaway` a source-backed checklist or decision rule, and use a
directly inspected frame as an `image` block whenever the asset provides one.
The caption must identify the visible step and why it matters to the article's
central claim.

Do not write first-person author experience or revenue/business outcomes. A
`quote` block is permitted only when it retains non-empty video evidence and
each cited canonical knowledge unit declares `epistemic_status` as
`video_explicit`. A profile projection must never turn a video claim into
"I did this" or "this earned" language.
