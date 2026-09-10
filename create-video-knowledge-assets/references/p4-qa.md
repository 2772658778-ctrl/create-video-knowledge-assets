# P4 Grounded Q&A

Use this workflow only for a completed `course-notes` asset. Do not use it to answer from an incomplete asset, raw source, an unverified index, course-notes prose, or any reader-facing document. QA facts always come from the canonical atomic knowledge and video evidence records; do not substitute a QA-only knowledge revision. For P4.2 `video_plus_context` or `explore`, also read `p4-external-evidence.md` and `p4-answer-presentation.md`; `video_only` cannot include external material.

1. Verify the asset first: `vka verify-asset --asset <asset>`. Stop when verification fails.
2. Build the course-notes index: `vka build-qa-index --asset <asset> --profile course-notes`.
3. Build the course-notes topology: `vka build-qa-topology --asset <asset> --profile course-notes`.
4. Retrieve grounding only: `vka retrieve-qa --asset <asset> --question <question> --mode <video_only|video_plus_context|explore> --limit 8`. Treat the JSON pack as video evidence and locations, not as an answer. `plan-qa` preserves only this selected video grounding in every mode; external material never enters its plan.
5. Plan references only: `vka plan-qa --input grounding-pack.json`. Treat the resulting plan as scope and citation structure, not as an answer.
6. For `video_only`, author the P4.1-compatible v1.1 `GroundedAnswer` with video blocks, claims, and the returned `answer_plan`; a v1.1 answer without an answer_plan is invalid. For `video_plus_context` or `explore`, author a v1.2 `GroundedAnswer`: its video blocks still bind only to the returned video plan, while external claims and visible non-video blocks stay in their dedicated P4.2 fields. Keep claim and answer statuses separate from top-level `extensions`; extensions must not carry canonical knowledge, evidence, or source-span references.
7. When the pack contains no relevant evidence, author an `out_of_scope` (OOS) answer when the video does not cover the question, or an `insufficient_evidence` answer when the retained evidence cannot support it. Do not invent a claim.
8. Validate before delivery: `vka validate-answer --asset <asset> --input answer.json`. Deliver only an answer that passes validation.
