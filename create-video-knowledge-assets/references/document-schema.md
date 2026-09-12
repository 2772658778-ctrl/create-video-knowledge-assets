# Document Schema

`views/<profile_id>/document.json` is the renderer-neutral, profile-specific
document view for a U1 asset. Renderers may change presentation, but must not
add facts or alter conclusions. Documents use schema version `1.1`.

## DocumentView

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `profile_id` | string | yes | Registered profile that selected the document's content and structure. |
| `title` | string | yes | Non-empty document title. |
| `blocks` | list of `DocumentBlock` | yes | One or more ordered, renderer-neutral content blocks. |
| `evidence_origins` | object mapping evidence ID to `video`, `external`, or `generated` | no | Provenance catalog used to determine whether a cited block can omit video time ranges. |
| `schema_version` | string | no | Defaults to `1.1`. |

## Two Delivered Parts

A view delivers two documents, and the split is part of the contract:

- `sections` is the reader's document. A reader wants the video's content, so
  every chapter must be about the video. Boundary, uncertainty, and source
  navigation material must **not** appear here; the table of contents is the
  first thing a reader uses to decide whether to keep reading, and it has to
  describe the video rather than the pipeline.
- `notes` is the separate boundary-and-source document:
  `{"title": "...", "sections": [...]}` using the same block shape. It carries
  scope, uncertainty, what the video claims versus what the view inferred, and
  where each claim came from.

Both parts keep `knowledge_refs` and `evidence_refs` on every block and are
validated the same way. Render either part with
`vka render-document --part main|notes`, and publish both with
`vka package-demo` as `summary.pdf` + `summary.html` and `notes.pdf` +
`notes.html`. The PDF is the archiving copy; the HTML is the same document
without page breaks, for continuous reading on screen. A document is rendered
twice, never rewritten twice.

## P3 Projection Binding

For a new creator, enterprise, or research view authored from a persisted
projection plan, the document also declares `projection_plan_ref`,
`projection_plan_id`, and `projection_plan_sha256`. The reference is exactly
`views/<profile_id>/projection-plan.json`; its ID and SHA-256 must match the
stored plan. This binds reader prose to the selected reader questions, evidence
scope, and figure decisions without changing canonical knowledge.

## DocumentBlock

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `kind` | enum | yes | `heading`, `paragraph`, `list`, `table`, `formula`, `code`, `image`, `caption`, `callout`, `quote`, or `summary`. |
| `text` | string or null | no | Textual payload when applicable. |
| `items` | list of strings | no | Ordered list payload when applicable. |
| `data` | object | no | Structured block payload, such as table, formula, code, or image details. |
| `knowledge_refs` | non-empty list of strings | yes | Knowledge units used to create this block. |
| `evidence_refs` | non-empty list of strings | yes | Evidence records grounding this block. |
| `source_spans` | list of `SourceSpan` | no | Direct video time ranges when available. |

Every block must retain both knowledge and evidence references. `source_spans`
are optional because external evidence has no video time range. Required
provenance belongs in these core fields, never in `data`.

When a block has no `source_spans`, every entry in its `evidence_refs` must be
listed in `evidence_origins` as `external` or `generated`. A block-local origin
claim cannot override the catalog. Uncatalogued evidence remains conservative:
it needs a video time range before rendering.

## Knowledge Relations

`knowledge/relations.jsonl` records `KnowledgeRelation` objects. Each relation
has `relation_id`, `source_unit_id`, `target_unit_id`, `relation_type`, and one
or more `evidence_refs`. Relation types are `prerequisite`, `explains`,
`supports`, `contradicts`, `causes`, `contrasts`, `exemplifies`, and `part_of`.

## Synthesis

`knowledge/synthesis.json` contains a `Synthesis` object. `video_summary`
records what the source supports and `video_summary_refs` names its knowledge
units. `agent_extensions` records any additional agent interpretation as
non-empty text entries; `agent_extension_refs` names the units motivating those
extensions.
Both reference lists must be non-empty, point to units in `units.jsonl`, and
must not make an agent extension appear to be a video claim. Both categories
are also grounded by non-empty `evidence_refs`.

## Compatibility

The `1.1` manifest records `input`, `config`, `tool_versions`, a schema version
for every completed stage, and SHA-256 for every stage output. Existing P1
`1.0` asset directories remain readable as historical artifacts; validation
never rewrites or silently migrates them.
