# P4 Q&A Authoring

Use Q&A only for a completed `course-notes` asset. For `video_plus_context` or `explore`, also follow `p4-external-evidence.md` and `p4-answer-presentation.md`; keep external claims and citations in their dedicated fields, never in video-grounded blocks. Follow this order:

```text
retrieve-qa -> plan-qa -> author -> validate-answer
```

`retrieve-qa` returns candidates, selected topology, and bounded `evidence_windows`; it never returns an answer. Pass its JSON unchanged to `plan-qa`. The resulting plan is reference-only: each block names the selected knowledge, evidence, spans, windows, selected relations, and `expected_claim_ids`.

Write detailed video answer claims only from the plan's selected atomic units and their declared windows. Keep each factual video block bound to its plan block and its exact `expected_claim_ids`; retain only its declared video evidence references and source spans. Do not add facts from unselected units, nearby but undeclared windows, course-notes prose, external enrichment, or memory. State unsupported requested facets as limits or insufficient evidence instead of filling gaps. Use the P4.1-compatible v1.1 blocks, claims, and answer-plan metadata for `video_only`; use v1.2 for `video_plus_context` or `explore`, keeping the P4.2 external sections outside the video plan, then run `validate-answer`.
