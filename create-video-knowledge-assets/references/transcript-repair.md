# Transcript Review

Use this reference after CC/ASR normalization and before knowledge extraction.

Correcting speech recognition is a reading task. It needs the sentence, the
topic, and the frame the speaker was pointing at, so the reviewer — a model or
a person — rewrites the text. This skill deliberately ships **no** substitution
table or term glossary: a fixed word list can only fit the one video it was
written for, and it silently rewrites text the reviewer never read.

## Required Artifacts

Keep all four files when ASR is used:

- `source/asr/<backend>-<model>.srt`: the raw ASR output.
- `evidence/timeline.raw.jsonl`: normalized raw transcript evidence.
- `evidence/transcript-review.md`: the numbered sheet handed to the reviewer.
- `evidence/transcript-reviewed.txt`: the reviewer's corrected sheet.
- `evidence/timeline.jsonl`: canonical transcript evidence used downstream.

## Workflow

1. Normalize the raw SRT with a raw id prefix, so the canonical timeline can
   point back at it:
   `vka normalize-srt --input <raw.srt> --acquisition asr --id-prefix raw- --output evidence/timeline.raw.jsonl`.
2. Build the review sheet:
   `vka build-repair-prompt --timeline evidence/timeline.raw.jsonl --output evidence/transcript-review.md --title "<video title>"`.
   It is a numbered list of transcript lines — no timestamps, no JSON, no ids.
3. Read the sheet and answer in the same numbering:

   ```text
   1|竹笋，中国人春日餐桌的主角
   2|江南的腌笋、浙江的油焖笋
   5|?
   ```

   - `N|文本` — this is what the speaker said. Fix only what you are sure of:
     wrong characters, terms, English names, punctuation, mixed
     Traditional/Simplified. Write Simplified Chinese. Do not add explanations,
     quotes, or facts the speaker did not say.
   - `N|?` — you read the row and cannot verify it. The raw text is kept and
     the row is marked uncertain.
   - omitting a row means you did not read it. It stays `unreviewed`.
4. Apply it:
   `vka apply-reviewed-transcript --timeline evidence/timeline.raw.jsonl --reviewed evidence/transcript-reviewed.txt --parent-prefix raw- --output evidence/timeline.jsonl`.
   Canonical rows drop the raw prefix and record the raw identifier in
   `parent_ids`. Every row records `quality.repair_status` as `repaired`,
   `raw_preserved`, or `unreviewed`.
5. Build knowledge from `evidence/timeline.jsonl`. Use
   `vka timeline-digest --timeline evidence/timeline.jsonl --output logs/timeline-digest.md`
   as the reading view instead of re-reading the JSONL. Cite `evidence_id`
   values from `timeline.jsonl`, not row numbers from the digest.
6. Run `vka validate-knowledge --asset <asset>` before projecting any profile.

Reading a whole transcript is not required. Review what the deliverable will
cite; everything else stays `unreviewed`, which is honest and cannot ground a
`video_explicit` claim. Review cost tracks the citations a run makes, not the
length of the video.
