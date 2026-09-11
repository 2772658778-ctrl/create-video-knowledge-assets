# Knowledge Schema

Knowledge units are scene-independent normalized facts, claims, procedures, and
interpretations derived from source evidence. They are the factual base a
reader-facing document is projected from. Every unit must remain traceable to
evidence and must preserve its epistemic status.

## Fields

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `unit_id` | string | yes | Stable non-empty identifier for this knowledge unit. |
| `type` | enum | yes | One of `concept`, `claim`, `mechanism`, `procedure`, `example`, `formula`, `code`, `quote`, `limitation`, `question`, or `takeaway`. |
| `title` | string | yes | Non-empty short title. |
| `statement` | string | yes | Non-empty normalized statement. |
| `evidence_refs` | list of strings | yes | One or more evidence identifiers supporting or motivating the unit. |
| `epistemic_status` | enum | yes | Relationship between the statement and its evidence. |
| `importance` | enum | yes | `low`, `medium`, or `high`. |
| `limitations` | list of strings | no | Known caveats, scope limits, or uncertainty notes. |
| `tags` | list of strings | no | Optional retrieval or grouping tags. |
| `extensions` | map string to object | no | Reserved for non-core, task-specific metadata. |
| `schema_version` | string | no | Schema version. Defaults to `1.0`. |

## Epistemic Status

`video_explicit` means the unit is directly stated or shown in the video
evidence. The statement should be a faithful normalization rather than an
unsupported extrapolation.

`agent_inference` means the unit is inferred by the agent from one or more
evidence items. The supporting evidence must be cited, and important assumptions
belong in `limitations`.

`external_enrichment` means the unit depends on external evidence beyond the
video. The external evidence must be referenced through `evidence_refs`.

`insufficient_evidence` means the unit captures an open question, uncertainty,
or plausible but unsupported interpretation. It still requires evidence
references showing why the issue arose.

## Reference Contract

Every knowledge unit must have at least one `evidence_refs` entry. References
must point to Evidence records, not raw timestamps, files, or informal notes.
Statements must not rely on uncited source material. If the evidence is weak,
incomplete, or indirect, keep the unit but mark the epistemic status and
limitations accordingly.

## Extensions Boundary

Use `extensions` only for optional metadata that does not change the meaning of
the core schema, such as local scoring signals, pipeline run identifiers, or
display hints. Do not put required provenance, source references, epistemic
status, or the main knowledge statement in `extensions`; those belong in the
core fields so downstream tooling can validate them consistently.

## U1 Knowledge Graph

Every U1 asset saves its normalized knowledge layer in these distinct files:

- `knowledge/outline.json`: the profile-specific authoring outline. A
  deep-summary view uses the contract in `profile-general-deep.md` for
  compatibility; a course-notes view keeps using
  `knowledge/teaching_outline.json` as its only mandatory teaching bridge.
- `knowledge/units.jsonl`: one `KnowledgeUnit` object per line.
- `knowledge/relations.jsonl`: one directed relation per line.
- `knowledge/synthesis.json`: source-backed video synthesis and clearly
  separated agent extension material.


Relations use `source_unit_id`, `target_unit_id`, and `relation_type`. Both
endpoints must refer to units in `units.jsonl`. The only allowed relation types are
`prerequisite`, `explains`, `supports`, `contradicts`, `causes`, `contrasts`,
`exemplifies`, and `part_of`.

`synthesis.json` keeps `video_summary` and agent extension content separate.
`video_summary_refs` lists the units supporting the source-backed video
summary. `agent_extension_refs` lists the units motivating an agent extension;
it must never silently turn the extension into a claim made by the video. Both
reference lists are non-empty lists of existing unit identifiers.
