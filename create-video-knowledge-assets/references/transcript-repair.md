# Transcript Repair

Use this reference after CC/ASR normalization and before knowledge extraction.

## Required Artifacts

Keep all three files when ASR is used:

- `source/asr/audio.srt`: raw Whisper SRT.
- `evidence/timeline.raw.jsonl`: normalized raw transcript evidence.
- `evidence/timeline.jsonl`: repaired transcript evidence used downstream.

If repair changes any row, preserve `original_content`, `repair_reason`, and `quality.repair_status=repaired`.

## Repair Workflow

1. Run `vka build-repair-prompt --timeline evidence/timeline.raw.jsonl --output evidence/asr-repair-prompt.md --title "<video title>"`.
2. Review the prompt with the video title, nearby transcript context, and inspected frame notes.
3. Save model or human edits as a JSON array with `evidence_id`, `original_content`, `repaired_content`, `confidence`, `reason`, and `uncertain`.
4. Run `vka apply-transcript-repairs --timeline evidence/timeline.raw.jsonl --repairs evidence/asr-repairs.json --output evidence/timeline.jsonl`.
5. Use only `evidence/timeline.jsonl` for knowledge units and document views.

## Repair Rules

- Fix only evidence-supported ASR mistakes: technical terms, English names, punctuation, simplified/traditional normalization, and obvious homophones.
- Do not summarize, combine rows, invent missing explanations, or turn uncertain audio into confident claims.
- Mark unresolved phrases with `quality.uncertain=true` and use `insufficient_evidence` for affected knowledge units.
- Prefer conservative technical repairs such as `Chad GPT -> ChatGPT`, `转制 -> 转置`, `攻势 -> 公式`, and `磁像量 -> 词向量` only when the surrounding context supports them.
