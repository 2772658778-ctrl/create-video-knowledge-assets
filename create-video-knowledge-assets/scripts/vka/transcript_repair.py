"""ASR transcript review.

Correcting speech recognition is a reading task: it needs the sentence, the
topic, and the frame the speaker was pointing at. A substitution table cannot
do it, and a table baked into this skill would only fit the one video it was
written for. So the reviewer — a model or a person — rewrites the text, and
this module owns the mechanical part: numbering, diffing, provenance labels,
and the refusal to invent content.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from vka.models import Evidence


REVIEW_LINE = re.compile(r"^(\d{1,9})\|(.*)$")
UNCERTAIN_MARK = "?"


def build_asr_review_prompt(
    timeline_rows: Sequence[Mapping[str, Any]],
    *,
    title: str | None = None,
    frame_notes: Sequence[str] | None = None,
) -> str:
    """Build the numbered reading sheet the reviewer corrects.

    Only the number and the text are shown: the reviewer edits sentences, and
    the tool keeps timestamps, identifiers, and spans out of the way.
    """
    if not timeline_rows:
        raise ValueError("timeline_rows must not be empty")

    numbered: list[str] = []
    for index, row in enumerate(timeline_rows, start=1):
        content = row.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError(f"row {index} content must be a non-empty string")
        numbered.append(f"{index}|{' '.join(content.split())}")

    lines = [
        "你是中文转录审校员。请修正语音识别错误，但不要改写讲者原意。",
        "",
        "硬性规则：",
        "1. 只修正有把握的错误：错字、术语、英文专名、标点、繁简混用。不要补写视频里没有说的话。",
        "2. 输出格式与输入一致：每行 `序号|修订后文本`，不要输出时间、解释或 JSON。",
        "3. 没有把握的行写成 `序号|?`，该行保持原文并记为不确定。",
        "4. 只输出你真正读过的行。没读过的行不要输出，它们会被记为未审阅。",
        "5. 统一使用简体中文。",
        "",
        "示例：",
        "7|我至少都有一两年没喝过了",
        "9|?",
        "",
    ]
    if title:
        lines.extend([f"视频标题：{title}", ""])
    if frame_notes:
        lines.append("已检查画面线索：")
        lines.extend(f"- {note}" for note in frame_notes if note)
        lines.append("")
    lines.extend(["待审校时间线：", *numbered])
    return "\n".join(lines)


def parse_reviewed_transcript(text: str) -> dict[int, str | None]:
    """Read a reviewed sheet into ``{row_number: corrected text or None}``.

    ``None`` means the reviewer read the row and could not verify it.
    """
    reviewed: dict[int, str | None] = {}
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = REVIEW_LINE.match(line)
        if match is None:
            raise ValueError(
                f"line {line_number} must look like '12|修订后的文本' or '12|?'"
            )
        index = int(match.group(1))
        if index < 1:
            raise ValueError(f"line {line_number} row number must be a positive integer")
        if index in reviewed:
            raise ValueError(f"row {index} is reviewed twice")
        body = match.group(2).strip()
        if not body:
            raise ValueError(f"row {index} has no text; use '?' when you cannot verify it")
        reviewed[index] = None if body == UNCERTAIN_MARK else body
    if not reviewed:
        raise ValueError("the reviewed sheet has no rows")
    return reviewed


def apply_reviewed_transcript(
    timeline_rows: Sequence[Mapping[str, Any]],
    reviewed: Mapping[int, str | None],
    *,
    parent_prefix: str | None = None,
) -> list[dict[str, object]]:
    """Turn the raw transcript into the canonical timeline.

    Every row is labeled: `repaired` (the reviewer rewrote it), `raw_preserved`
    (the reviewer read it and kept it), or `unreviewed` (nobody looked at it).
    When `parent_prefix` names the prefix written by
    `vka normalize-srt --id-prefix`, canonical rows drop the prefix and record
    the raw identifier in `parent_ids`.
    """
    for index in reviewed:
        if index > len(timeline_rows):
            raise ValueError(
                "reviewed sheet references row "
                f"{index} but the timeline has {len(timeline_rows)} rows"
            )

    output: list[dict[str, object]] = []
    canonical_ids: set[str] = set()

    for index, row in enumerate(timeline_rows, start=1):
        copied = dict(row)
        raw_id = _required_string(copied.get("evidence_id"), "timeline row evidence_id")
        canonical_id = _canonical_id(raw_id, parent_prefix)
        if canonical_id in canonical_ids:
            raise ValueError(f"duplicate canonical evidence id: {canonical_id}")
        canonical_ids.add(canonical_id)

        quality = dict(copied.get("quality") or {})
        if index not in reviewed:
            quality["repair_status"] = "unreviewed"
        elif reviewed[index] is None:
            quality["repair_status"] = "raw_preserved"
            quality["uncertain"] = "true"
        elif reviewed[index] == copied.get("content"):
            quality["repair_status"] = "raw_preserved"
        else:
            original = copied.get("content")
            if not isinstance(original, str) or not original.strip():
                raise ValueError(f"{raw_id} content must be a non-empty string")
            copied["original_content"] = original
            copied["content"] = str(reviewed[index])
            quality["repair_status"] = "repaired"
        copied["quality"] = quality

        if canonical_id != raw_id:
            copied["evidence_id"] = canonical_id
            copied["parent_ids"] = [raw_id]

        Evidence.model_validate(copied)
        output.append(copied)

    return output


def _canonical_id(raw_id: str, parent_prefix: str | None) -> str:
    if parent_prefix is None:
        return raw_id
    if not parent_prefix:
        raise ValueError("parent prefix must not be empty")
    if not raw_id.startswith(parent_prefix) or len(raw_id) == len(parent_prefix):
        raise ValueError(
            f"timeline evidence id {raw_id} does not start with parent prefix {parent_prefix}"
        )
    return raw_id[len(parent_prefix) :]


def _required_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value
