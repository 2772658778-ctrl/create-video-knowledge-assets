# Projection Plan Contract

`views/<profile_id>/projection-plan.json` is the P3 bridge from canonical
knowledge to a reader-facing document. It is not prose and it is not a render
template. It records what a profile should explain, the evidence it may use,
and which inspected frames must become figures.

Only `creator-article`, `enterprise-knowledge`, and `research-brief` use this
contract. P1 `course-notes` continues to use its distinct
`knowledge/teaching_outline.json` bridge.

## Required Shape

```json
{
  "schema_version": "1.0",
  "plan_id": "pp-creator-001",
  "profile_id": "creator-article",
  "profile_spec_version": "1.0",
  "canonical_hash_tree": {"knowledge/units.jsonl": "<sha256>"},
  "reader_goal": "Help a reader understand and check the demonstrated practice.",
  "status": "ready",
  "sections": [
    {
      "section_id": "narrative",
      "kind": "narrative",
      "reader_question": "Why must the demonstrated steps stay separate?",
      "knowledge_refs": ["ku-flow"],
      "evidence_refs": ["ev-flow"],
      "required_blocks": ["paragraph", "paragraph"]
    }
  ],
  "selected_figures": [
    {
      "section_id": "narrative",
      "evidence_id": "ev-frame-1",
      "artifact_ref": "source/frames/frame-1.jpg",
      "reader_purpose": "Show the pivotal interface state.",
      "caption_intent": "Explain the state and its consequence.",
      "required": true
    }
  ],
  "rejected_frames": [],
  "quality_targets": {"minimum_meaningful_blocks": 8, "requires_visual": true}
}
```

`canonical_hash_tree` must exactly match the asset's `source/`, `evidence/`,
and `knowledge/` hashes at write time. A selected figure must name a directly
inspected video-frame evidence record and repeat its exact `artifact_ref`.
`status` may be `ready`, `declined`, or `evidence_inventory`; only `ready` may
be bound to a final profile document.

## Workflow

1. Run `vka verify-asset`, select the profile, and build the plan from canonical
   records only.
2. Run `vka validate-projection-plan --profile <id> --input <plan.json>`.
3. Persist it with `vka write-projection-plan --asset <asset> --profile <id>
   --input <plan.json>`.
4. Write `document.json` from the plan. A bound document declares
   `projection_plan_ref`, `projection_plan_id`, and `projection_plan_sha256`.
5. Reproject and render. Canonical data remains unchanged throughout.

## Future Profile Packs

Future hot-pluggable profiles are declarative, versioned packs: profile
manifest, plan schema/options, presentation tokens, and templates. They do not
load executable Python from an asset or the network. Every resulting plan and
document records the profile/spec/template version and hash; upgrades create a
new projection rather than silently changing a completed view.
