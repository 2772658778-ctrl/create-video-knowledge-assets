# Research Brief Profile

Use `research-brief` for an evidence-separated analysis of a completed video
asset. It writes only `views/research-brief/document.json`; renderers may
change presentation but cannot add, verify, or rewrite facts.

## Required Sections

The document keeps these sections in this exact order:

1. `video_evidence`: visible video viewpoints and evidence only.
2. `analysis_inference`: Agent analysis explicitly labelled as inference.
3. `external_enrichment`: user-provided background material, or an explicit
   `not_used` declaration when there is none.
4. `limitations_questions`: disputes, limits, and questions still to verify.
5. `source_navigation`: structured navigation across the preceding sources.

Every reader-facing claim includes `data.claim_status`,
`data.source_category`, `data.visible_label`, and `data.structured_refs`.
Structured references name the same `knowledge_id` and `evidence_id` records
as the block. A visible video label is valid only for canonical
`video_explicit` knowledge. Agent inference must never be worded or labelled
as a video statement.

Before drafting, follow `p3-profile-authoring.md`. Begin from a bounded
research question rather than the generic goal of summarising a video. Use an
evidence table or a directly inspected visual frame to distinguish observations
from later analysis at a glance. The analysis section must explain a testable
interpretation, comparison, or boundary; merely repeating that it is an
inference is not a substantive brief. If the evidence cannot support that much,
return an evidence inventory or decline the research brief instead of producing
five sentence-level placeholder sections.

## External Material Boundary

This profile does not run web search, automatic fact checking, or any other
external acquisition. `external_enrichment` may cite only evidence already
recorded in the asset and explicitly supplied by the user. Each cited record
must retain its URL, author or institution, publication date, access time, and
supporting snippet. The external material is background, not a substitute for
or silent rewrite of a video viewpoint.

When no external material is used, use an `external_enrichment` block with
`claim_status` and `source_category` set to `not_used`, a visible label such as
`未使用外部资料`, and a non-external canonical reference for the declaration.

## Source Boundary

Read the canonical `knowledge/` and `evidence/` records already in the asset.
Do not create a new fact while projecting this profile. Preserve each block's
`knowledge_refs`, `evidence_refs`, and video `source_spans`, and leave
`source/`, `evidence/`, and `knowledge/` unchanged.
