# Transcript Repair

Use this reference after CC/ASR normalization and before knowledge extraction.

## Required Artifacts

Keep all three files when ASR is used:

- `source/asr/audio.srt`: raw Whisper SRT.
- `evidence/timeline.raw.jsonl`: normalized raw transcript evidence.
- `evidence/timeline.jsonl`: repaired transcript evidence used downstream.

If repair changes any row, preserve `original_content`, `repair_reason`, and `quality.repair_status=repaired`.

## Repair Workflow

1. Write the raw timeline with a raw id prefix, so the canonical timeline can
   point back at it:
   `vka normalize-srt --input <raw.srt> --acquisition asr --id-prefix raw- --output evidence/timeline.raw.jsonl`.
2. Run `vka build-repair-prompt --timeline evidence/timeline.raw.jsonl --output evidence/asr-repair-prompt.md --title "<video title>"`.
3. Review the prompt with the video title, nearby transcript context, and inspected frame notes.
4. Save model or human edits as JSON. Either shape is accepted:
   - an array of `evidence_id`, `original_content`, `repaired_content`, `confidence`, `reason`, `uncertain`;
   - an object `{"repairs": [...], "uncertain_ids": [...]}`. Use
     `uncertain_ids` for rows you read but cannot verify and do **not** want to
     rewrite. Never invent a `repaired_content` just to mark a row uncertain.
5. Run
   `vka apply-transcript-repairs --timeline evidence/timeline.raw.jsonl --repairs evidence/asr-repairs.json --parent-prefix raw- --output evidence/timeline.jsonl`.
   Canonical rows drop the raw prefix and record the raw identifier in
   `parent_ids`; every row records `quality.repair_status` as either
   `repaired` or `raw_preserved`.
6. Use `vka timeline-digest --timeline evidence/timeline.jsonl --output .tmp/timeline-digest.md`
   as the reading view when you build knowledge units. Cite ids from
   `timeline.jsonl`, not from the digest.
7. Use only `evidence/timeline.jsonl` for knowledge units and document views.
   Run `vka validate-knowledge --asset <asset>` before projecting any profile.

## Repair Rules

- Fix only evidence-supported ASR mistakes: technical terms, English names, punctuation, simplified/traditional normalization, and obvious homophones.
- Do not summarize, combine rows, invent missing explanations, or turn uncertain audio into confident claims.
- Mark unresolved phrases with `quality.uncertain=true` and use `insufficient_evidence` for affected knowledge units.
- `quality.uncertain=true` is a real constraint, not a note. A knowledge or
  content unit marked `video_explicit` must cite at least one checked frame or
  reviewed transcript row; `vka validate-knowledge` fails the asset otherwise.
  Metadata and audio records describe provenance, so citing them never makes a
  claim `video_explicit`.
- Prefer conservative technical repairs such as `Chad GPT -> ChatGPT`, `转制 -> 转置`, `攻势 -> 公式`, and `磁像量 -> 词向量` only when the surrounding context supports them.
