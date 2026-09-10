# Content Schema

Content units are reusable editorial building blocks derived from knowledge and
evidence. They are designed for reuse across profiles, layouts, and rendering
targets while still preserving grounding metadata.

## Fields

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `content_unit_id` | string | yes | Stable non-empty identifier for this content unit. |
| `kind` | enum | yes | One of `thesis`, `argument`, `narrative_beat`, `example`, `quote`, `procedure`, `comparison`, `scene`, `clip_candidate`, `limitation`, or `transition`. |
| `title` | string | yes | Non-empty short title. |
| `editorial_text` | string | yes | Non-empty reusable editorial text. |
| `knowledge_refs` | list of strings | yes | One or more knowledge identifiers used by the unit. |
| `evidence_refs` | list of strings | yes | One or more evidence identifiers grounding the unit. |
| `source_spans` | list of `SourceSpan` | no | Video spans supporting the unit. Defaults to an empty list. |
| `epistemic_status` | enum | yes | One of `video_explicit`, `agent_inference`, `external_enrichment`, or `insufficient_evidence`. |
| `speaker_refs` | list of strings | no | Optional speaker identifiers. Defaults to an empty list. |
| `visual_refs` | list of strings | no | Optional visual identifiers. Defaults to an empty list. |
| `standalone_level` | enum | yes | One of `standalone`, `needs_intro`, `needs_previous_context`, or `cannot_reuse_alone`. |
| `context_requirements` | list of strings | no | Optional context notes needed for reuse. |
| `adaptation` | map string to object | no | Optional adaptation metadata for downstream rendering or reuse. |
| `fidelity_notes` | list of strings | no | Optional notes about fidelity, omissions, or editorial compromises. |
| `schema_version` | string | no | Schema version. Defaults to `1.0`. |

## Reference Contract

Every content unit must carry at least one `knowledge_refs` entry and at least
one `evidence_refs` entry. The references must point to existing knowledge and
evidence records, not raw timestamps or informal notes.

Blank strings are not valid inside reference lists. Enum fields must use the
declared values exactly so downstream tooling can validate the payload without
special cases.
