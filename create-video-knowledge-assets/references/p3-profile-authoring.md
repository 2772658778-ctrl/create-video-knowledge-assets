# P3 Profile Authoring And Figure Plan

Use this reference after `verify-asset` and before writing any P3
`document.json`. R3 is a grounded editorial projection, not a six-heading
summary. Start with an authoring plan; then write the renderer-neutral
document from that plan.

## Reader Copy

The reader came for the source's content, not for a report about a source.
These rules apply to every reader-facing profile and are enforced by the gate:

- **State the content; never make the video the subject.** `视频把油炒视为…` and
  `视频给出三点…` turn the reader into a spectator. Write the claim itself, or
  name the author when the attribution matters: `作者把采后五小时称为“黄金时间”`.
  `视频` may still appear in metadata, in a one-off attribution, or when the
  video's own production is the topic.
- **Push attribution down, not out.** Documents, data, history, and mechanics
  are stated directly (`《周礼》记载…`); only the author's own judgement,
  naming, or unverified claim keeps `作者认为` / `作者把…称为`.
- **Captions describe the picture.** A caption says what is visible and why it
  matters. Production directions ("开场用标题卡", "口播要说明") belong in the
  notes part, never mixed into reader copy.
- **Do not argue your own evidence in the body.** Sentences like "这张图支持…
  不单独证明…" turn a reader into an auditor. Source times live in footnotes;
  scope lives in the notes part.
- **Vary the sentence pattern.** `不是 A，而是 B` is strong once per section and
  a tic when it carries the whole text.
- **Keep one address.** Talk to the reader as `你`. Do not drift between `你`,
  `用户`, `人`, and `我` inside one document.

## Shared Planning Contract

Create a short private plan containing:

1. target reader and the decision, understanding, or action the document
   supports;
2. selected canonical knowledge IDs, split into video fact, inference, and
   limitation where applicable;
3. section-by-section reader question and the evidence that answers it;
4. a figure plan for every directly inspected, useful frame: `evidence_id`,
   `artifact_ref`, reader purpose, nearby claim, and a caption that states what
   the reader should learn from the image;
5. a negative decision for each rejected frame (unreadable, redundant, or low
   information). Never insert decorative screenshots.

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
