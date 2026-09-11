# P3 Profile Authoring And Figure Plan

Use this reference after `verify-asset` and before writing any P3
`document.json`. R3 is a grounded editorial projection, not a six-heading
summary. Start with an authoring plan; then write the renderer-neutral
document from that plan.

## Reader Copy

The reader came for the source's content, not for a report about a source.
These rules apply to every reader-facing profile and are enforced by the gate:

- **Retell the source; never make the video the subject.** The document *is* the
  source's content in written form, so write the claim itself: `油炒是…`,
  `《周礼》记载…`, `采后五小时被称为“黄金时间”`. `视频把油炒视为…` and
  `视频给出三点…` turn the reader into a spectator and are rejected. `视频` may
  still appear in metadata or when the video's own production is the topic.
- **Attribute the author's own view to the author.** Facts, documents, data,
  history, and mechanics are stated directly; a judgement, a name the author
  invents, or an unverified claim is attributed once: `作者把采后五小时称为
  “黄金时间”`. Do not keep re-introducing the author as the actor of ordinary
  sentences — `作者先肯定了 HTML 的优势` is worse than `HTML 的优势是…`.
- **Captions describe the picture.** A caption says what is visible and why it
  matters. Production directions ("开场用标题卡", "口播要说明") belong in the
  notes part, never mixed into reader copy.
- **Do not argue your own evidence in the body.** Sentences like "这张图支持…
  不单独证明…" turn a reader into an auditor. Source times are numbered in the
  body and listed under 来源时间 at the end; scope lives in the notes part.
- **Vary the sentence pattern.** `不是 A，而是 B` is strong once per section and
  a tic when it carries the whole text.
- **Keep one address.** Talk to the reader as `你`. Do not drift between `你`,
  `用户`, `人`, and `我` inside one document.

## Shared Planning Contract

Create a short private plan containing:

1. target reader and the decision, understanding, or action the document
   supports;
2. the source form — type, duration band, density, chapter mode — and the
   granularity it implies. Decide how many core claims the document carries and
   say why; do not import a number from a template, and do not quietly drop
   most of a tutorial's steps to keep the document short;
2. selected canonical knowledge IDs, split into video fact, inference, and
   limitation where applicable;
3. section-by-section reader question and the evidence that answers it;
4. a figure plan for every directly inspected, useful frame: `evidence_id`,
   `artifact_ref`, reader purpose, nearby claim, and a caption that states what
   the reader should learn from the image;
5. a negative decision for each rejected frame (unreadable, redundant, or low
   information). Never insert decorative screenshots.

Three rules follow from the source form:

- **A tutorial is measured by coverage, not by length.** Every source step and
  checkpoint ends in one of three states: told in full, merged into another
  step, or explicitly omitted with a reason. A nine-step tutorial that shows
  two steps has not been summarised. Record that ledger in the notes part with
  the output section each step lands in; the reader's document carries the
  steps themselves, not a report about covering them.
- **One claim per paragraph.** A paragraph develops one judgement. A number, a
  mechanism, and a historical source are three paragraphs, not one sentence
  with three commas.
- **Evidence is quoted per claim.** Each core claim cites one to three
  contiguous time windows. If a claim needs more than three disjoint windows,
  label it in the body as a synthesis and give it an evidence table in the
  notes part.

If the asset contains a directly inspected frame with an `artifact_ref`, every
creator, enterprise, and research projection must render at least one selected
frame as an `image` block. The block must cite that frame in `evidence_refs`,
use its exact `artifact_ref` as `path`, retain its source span, and explain the
image in its caption. If no useful inspected frame exists, say so in the
authoring plan; do not fabricate one.

When this visual requirement applies, the projection gate also rejects a thin
placeholder: creator articles need a source-backed actionable checklist,
enterprise records need a process/boundary/risk table, and research briefs need
an evidence or source-navigation table. These are minimum reader structures,
not interchangeable styling instructions.

Use the inspected-frame selection discipline from P1, but not its lecture
layout: choose a fully revealed, readable state close to the claim it supports,
then put the figure beside that claim. A sentence saying "the video has a
frame" is not a figure.

## Creator Article

Write for a reader who wants a coherent, publishable explanation. Shape the
article as:

`reader problem -> central tension/claim -> narrative of the method -> concrete
video evidence and figure -> practical checklist -> scope and limits`.

The opening should state a real reader payoff, not merely announce a summary.
Turn the takeaway into a concise checklist only when each item is supported by
the video. Use a figure to make one pivotal step, interface state, or before /
after contrast legible. Do not invent first-person experience, performance
results, quotes, or commercial outcomes.

## Enterprise Knowledge

Write for a teammate who needs to reuse a bounded practice without mistaking a
video demonstration for an approved decision. Shape the document as:

`purpose and applicability -> terms / preconditions -> process and evidence
figure -> inputs, outputs, and known roles -> risks and escalation boundary ->
source navigation`.

Use a compact table for a process, input/output boundary, or risk register when
the source supports it. Do not invent owners, deadlines, acceptance criteria,
or action items. When the source does not specify a role or decision, label it
as an open question rather than filling the gap with enterprise-sounding prose.

## Research Brief

Write for a reader assessing what the material does and does not establish.
Shape the brief as:

`research question and corpus boundary -> observations (with evidence figure or
evidence table) -> explicitly labelled analysis -> external material status ->
limitations / falsifiable questions -> claim-to-source navigation`.

An evidence table should make claim, status, and source distinguishable at a
glance. Analysis must add a testable interpretation or comparison boundary; a
single sentence that only says "this is an inference" is insufficient. If the
available material cannot support a meaningful research question, decline the
research brief or deliver an evidence inventory instead of a hollow report.
