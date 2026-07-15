# Evidence Schema

Evidence records source-grounded material that appears in a video, an external
source, or a deterministic/generated artifact derived from those sources. It is
not a place for normalized knowledge claims or scene-independent interpretation.

## Fields

| Field | Type | Required | Description |
| --- | --- | --- | --- |
| `evidence_id` | string | yes | Stable non-empty identifier for this evidence item. |
| `origin` | enum | yes | Source class: `video`, `external`, or `generated`. |
| `modality` | enum | yes | Source modality: `metadata`, `transcript`, `audio`, `frame`, or `document`. |
| `spans` | list of `SourceSpan` | conditional | Time ranges in the source video. Required for every `video` evidence item. |
| `content` | string | yes | Non-empty source content, transcription, observation, or derived artifact description. |
| `artifact_ref` | string or null | no | Optional path or identifier for an associated artifact, such as an extracted frame. |
| `acquisition` | string | yes | Non-empty method label, for example `asr`, `ffmpeg`, `metadata`, or `manual_review`. |
| `quality` | map string to string | no | Optional quality signals such as confidence, OCR status, or review state. |
| `parent_ids` | list of strings | no | Evidence identifiers this item was derived from. |
| `schema_version` | string | no | Schema version. Defaults to `1.0`. |

`SourceSpan` has `start_ms` and `end_ms` integer fields. `start_ms` must be at
least `0`, `end_ms` must be greater than `0`, and `end_ms` must be greater than
`start_ms`.

## Origin Types

`video` evidence comes directly from the input video, including metadata,
transcript/audio segments, and inspected frames. Every `video` evidence item must
carry at least one source span so it can be traced back to a concrete time range.

`external` evidence comes from non-video sources such as documentation, papers,
web pages, or user-provided files. It must identify its acquisition method and
should use `artifact_ref` when a durable source artifact is available.

`generated` evidence is a deterministic artifact derived from other evidence,
such as a cleaned transcript segment or extracted still image. When parent
evidence is available, `parent_ids` should be used to preserve provenance.

## Visual Evidence Rule

Visual descriptions may only be written after the agent directly inspects the
corresponding frame or frame range. Candidate frames produced by extraction or
sampling are not formal visual descriptions by themselves. Keep candidate frame
records distinct from final inspected-frame evidence, and only promote visual
content into evidence when direct visual inspection supports the description.
