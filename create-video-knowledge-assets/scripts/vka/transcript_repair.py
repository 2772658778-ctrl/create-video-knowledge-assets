from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from vka.models import Evidence


COMMON_ASR_REPAIRS = {
    "Chad GPT": "ChatGPT",
    "轉制": "转置",
    "转制": "转置",
    "攻势": "公式",
    "不被公式": "不背公式",
    "磁像量": "词向量",
    "詞向量": "词向量",
    "詞相量": "词向量",
    "開山鼻祖": "代表性应用",
    "冰語": "宾语",
    "冰语": "宾语",
    "素造": "塑造",
    "坐標品面": "坐标平面",
    "點擊": "点积",
    "点击": "点积",
    "全中矩陣": "权重矩阵",
    "全中矩阵": "权重矩阵",
    "句證": "矩阵",
    "句证": "矩阵",
    "sulfmax": "softmax",
    "t度消失": "梯度消失",
    "相量": "向量",
    "突阻和": "凸组合",
    "守尾相接": "首尾相接",
}


def build_asr_repair_prompt(
    timeline_rows: Sequence[Mapping[str, Any]],
    *,
    title: str | None = None,
    frame_notes: Sequence[str] | None = None,
) -> str:
    """Build the review prompt used by an agent/model to repair ASR text."""
    if not timeline_rows:
        raise ValueError("timeline_rows must not be empty")

    compact_rows = []
    for row in timeline_rows:
        evidence_id = _evidence_id(row)
        content = row.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError(f"{evidence_id} content must be a non-empty string")
        compact_rows.append(
            {
                "evidence_id": evidence_id,
                "time": _format_span_for_prompt(row),
                "content": content,
            }
        )

    lines = [
        "你是中文技术课程转录审校员。请修复 ASR 识别错误，但不要改写讲者原意。",
        "",
        "硬性规则：",
        "1. 只修复有证据支持的错字、术语、标点、繁简混杂和英文专名；不要补写视频里没有说的解释。",
        "2. 保留每条 evidence_id 和时间范围，不要合并、删除或重排记录。",
        "3. 听不准、画面也无法支持的内容必须标记 uncertain=true，repaired_content 保留最保守写法。",
        "4. 术语优先按技术语境修正，例如 ChatGPT、softmax、QK^T、转置、词向量。",
        "5. 输出严格 JSON 数组；每项包含 evidence_id、original_content、repaired_content、confidence、reason、uncertain。",
        "6. 读不准但无需改写的行，不要伪造 repaired_content，改为写进不确定清单：输出对象形式 {\"repairs\": [...], \"uncertain_ids\": [...]}。",
        "",
    ]
    if title:
        lines.append(f"视频标题：{title}")
    if frame_notes:
        lines.append("已检查画面线索：")
        lines.extend(f"- {note}" for note in frame_notes if note)
    lines.extend(
        [
            "",
            "待审校时间线：",
            json.dumps(compact_rows, ensure_ascii=False, indent=2),
        ]
    )
    return "\n".join(lines)


def suggest_asr_repairs(
    timeline_rows: Sequence[Mapping[str, Any]],
    *,
    glossary: Mapping[str, str] | None = None,
    simplified: bool = False,
) -> list[dict[str, object]]:
    """Return deterministic repair candidates for common ASR mistakes.

    `glossary` carries the domain vocabulary of one video. ASR tends to
    mis-hear the same proper noun over and over ("王老吉" arriving as
    "王老奇", "王老级", "王老集"), so a small per-run glossary removes most
    of the repair work without turning it into an opinion about the content.

    `simplified` also normalizes Simplified Chinese. Whisper-class models
    switch between Traditional and Simplified inside one Chinese transcript,
    which is a rendering artifact rather than a transcription error.
    """
    replacements = _merge_glossary(glossary)
    repairs: list[dict[str, object]] = []
    for row in timeline_rows:
        content = row.get("content")
        if not isinstance(content, str):
            continue

        repaired, reasons = _apply_replacements(content, replacements, simplified=simplified)

        repaired = _normalize_technical_spacing(repaired)
        if repaired != content:
            repairs.append(
                {
                    "evidence_id": _evidence_id(row),
                    "original_content": content,
                    "repaired_content": repaired,
                    "confidence": "medium",
                    "reason": "; ".join(reasons) or "technical term normalization",
                    "uncertain": False,
                }
            )
    return repairs


def _apply_replacements(
    content: str,
    replacements: Sequence[tuple[str, str]],
    *,
    simplified: bool,
) -> tuple[str, list[str]]:
    """Apply the term table and script normalization until they stop changing text.

    A glossary mixes Simplified and Traditional keys while the transcript mixes
    both scripts, so one pass is not enough: "引讓使" only matches after the
    Traditional form is normalized, and a Traditional key only matches before
    it is. Two passes settle both directions without guessing intent.
    """
    repaired = content
    reasons: list[str] = []
    for _ in range(2):
        for wrong, right in replacements:
            if wrong in repaired:
                repaired = repaired.replace(wrong, right)
                reasons.append(f"{wrong} -> {right}")
        if simplified:
            converted = to_simplified(repaired)
            if converted != repaired:
                repaired = converted
                reasons.append("繁体转简体")
    return repaired, list(dict.fromkeys(reasons))


def load_glossary(payload: object) -> dict[str, str]:
    """Validate a per-run ASR glossary."""
    if not isinstance(payload, Mapping):
        raise ValueError("glossary must be an object mapping wrong text to right text")
    glossary: dict[str, str] = {}
    for wrong, right in payload.items():
        if not isinstance(wrong, str) or not wrong.strip():
            raise ValueError("glossary keys must be non-empty strings")
        if not isinstance(right, str) or not right.strip():
            raise ValueError(f"glossary value for {wrong!r} must be a non-empty string")
        glossary[wrong] = right
    return glossary


def to_simplified(value: str) -> str:
    try:
        import warnings  # noqa: PLC0415 - scoped to the optional import

        warnings.filterwarnings("ignore", message="pkg_resources is deprecated")
        from zhconv import convert  # noqa: PLC0415 - optional dependency
    except ImportError as exc:
        raise ValueError(
            "zhconv is required for simplified normalization; install it in the workspace environment"
        ) from exc
    return convert(value, "zh-cn")


def _merge_glossary(
    glossary: Mapping[str, str] | None,
) -> list[tuple[str, str]]:
    merged = dict(COMMON_ASR_REPAIRS)
    if glossary:
        merged.update(glossary)
    # Longer keys first so "王老吉凉茶" is applied before "王老吉".
    return sorted(merged.items(), key=lambda item: len(item[0]), reverse=True)


def apply_transcript_repairs(
    timeline_rows: Sequence[Mapping[str, Any]],
    repairs: Sequence[Mapping[str, Any]] | Mapping[str, Any],
    *,
    uncertain_ids: Sequence[str] | None = None,
    reviewed_ids: Sequence[str] | None = None,
    assume_reviewed: bool = False,
    parent_prefix: str | None = None,
) -> list[dict[str, object]]:
    """Turn a raw transcript timeline into the canonical timeline.

    Every row records its repair state, so a reader can tell a row that was
    deliberately rewritten from one that was preserved as-is. When
    `parent_prefix` names the prefix written by
    `vka normalize-srt --id-prefix`, canonical rows drop the prefix and record
    the raw identifier in `parent_ids`; without it the canonical row would cite
    itself and the provenance chain would be meaningless.

    Rows are labeled honestly: `repaired` (the reviewer changed the text),
    `raw_preserved` (the reviewer read it and kept it), or `unreviewed` (nobody
    looked at it). Review cost then tracks what the run actually cites instead
    of the length of the transcript. Set `assume_reviewed` only when the
    reviewer genuinely read the whole transcript.
    """
    repair_entries, payload_uncertain, payload_reviewed = split_repair_payload(repairs)
    repair_by_id = {_repair_id(repair): repair for repair in repair_entries}
    uncertain = set(payload_uncertain)
    for value in uncertain_ids or ():
        uncertain.add(_required_id(value, "uncertain id"))
    reviewed = set(payload_reviewed)
    for value in reviewed_ids or ():
        reviewed.add(_required_id(value, "reviewed id"))
    reviewed.update(repair_by_id)
    reviewed.update(uncertain)

    output: list[dict[str, object]] = []
    canonical_ids: set[str] = set()
    known_ids: set[str] = set()

    for row in timeline_rows:
        copied = dict(row)
        raw_id = _evidence_id(copied)
        canonical_id = _canonical_id(raw_id, parent_prefix)
        if canonical_id in canonical_ids:
            raise ValueError(f"duplicate canonical evidence id: {canonical_id}")
        canonical_ids.add(canonical_id)
        known_ids.update({raw_id, canonical_id})

        repair = repair_by_id.get(raw_id) or repair_by_id.get(canonical_id)
        quality = dict(copied.get("quality") or {})
        if repair is None:
            quality["repair_status"] = (
                "raw_preserved"
                if assume_reviewed or raw_id in reviewed or canonical_id in reviewed
                else "unreviewed"
            )
        else:
            original = copied.get("content")
            repaired = repair.get("repaired_content")
            if not isinstance(original, str) or not isinstance(repaired, str) or not repaired.strip():
                raise ValueError(f"{raw_id} has invalid repair content")
            copied["content"] = repaired.strip()
            copied["original_content"] = original
            copied["repair_reason"] = str(repair.get("reason", ""))
            quality["repair_status"] = "repaired"
            quality["repair_confidence"] = str(repair.get("confidence", "unknown"))
            if bool(repair.get("uncertain")):
                quality["uncertain"] = "true"
        if canonical_id != raw_id:
            copied["evidence_id"] = canonical_id
            copied["parent_ids"] = [raw_id]
        if raw_id in uncertain or canonical_id in uncertain:
            quality["uncertain"] = "true"
        copied["quality"] = quality

        Evidence.model_validate(copied)
        output.append(copied)

    missing_ids = set(repair_by_id) - known_ids
    if missing_ids:
        raise ValueError(f"repairs reference missing evidence ids: {', '.join(sorted(missing_ids))}")
    unknown_ids = (uncertain | reviewed) - known_ids
    if unknown_ids:
        raise ValueError(
            f"reviewed or uncertain ids reference missing evidence ids: "
            f"{', '.join(sorted(unknown_ids))}"
        )

    return output


def split_repair_payload(
    payload: object,
) -> tuple[list[Mapping[str, Any]], list[str], list[str]]:
    """Accept either a repairs array or an object payload.

    The object form lets a reviewer flag rows it cannot verify without
    inventing a rewrite for every one of them:

    ``{"repairs": [...], "reviewed_ids": [...], "uncertain_ids": [...]}``
    """
    if isinstance(payload, Mapping):
        entries = payload.get("repairs", [])
        uncertain = payload.get("uncertain_ids", [])
        reviewed = payload.get("reviewed_ids", [])
    elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes)):
        entries, uncertain, reviewed = payload, [], []
    else:
        raise ValueError("repairs must be an array or an object with a repairs array")

    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
        raise ValueError("repairs must be an array")
    if not isinstance(uncertain, Sequence) or isinstance(uncertain, (str, bytes)):
        raise ValueError("uncertain_ids must be an array")
    if not isinstance(reviewed, Sequence) or isinstance(reviewed, (str, bytes)):
        raise ValueError("reviewed_ids must be an array")
    if any(not isinstance(entry, Mapping) for entry in entries):
        raise ValueError("each repair must be an object")
    return (
        list(entries),
        [_required_id(value, "uncertain id") for value in uncertain],
        [_required_id(value, "reviewed id") for value in reviewed],
    )


def _canonical_id(raw_id: str, parent_prefix: str | None) -> str:
    if parent_prefix is None:
        return raw_id
    if not parent_prefix:
        raise ValueError("parent prefix must not be empty")
    if not raw_id.startswith(parent_prefix) or len(raw_id) == len(parent_prefix):
        raise ValueError(f"timeline evidence id {raw_id} does not start with parent prefix {parent_prefix}")
    return raw_id[len(parent_prefix):]


def _required_id(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _repair_id(repair: Mapping[str, Any]) -> str:
    return _required_id(repair.get("evidence_id"), "repair evidence_id")


def _evidence_id(row: Mapping[str, Any]) -> str:
    return _required_id(row.get("evidence_id"), "timeline row evidence_id")


def _format_span_for_prompt(row: Mapping[str, Any]) -> str:
    spans = row.get("spans")
    if not isinstance(spans, list) or not spans:
        return "unknown"
    first = spans[0]
    if not isinstance(first, Mapping):
        return "unknown"
    start = first.get("start_ms")
    end = first.get("end_ms")
    if not isinstance(start, int) or not isinstance(end, int):
        return "unknown"
    return f"{_format_time(start)}--{_format_time(end)}"


def _format_time(milliseconds: int) -> str:
    total_seconds = milliseconds // 1000
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _normalize_technical_spacing(value: str) -> str:
    value = re.sub(r"\bChat GPT\b", "ChatGPT", value, flags=re.IGNORECASE)
    value = value.replace("Q乘以K的转置", "Q 乘以 K 的转置")
    value = value.replace("Q乘以K的轉置", "Q 乘以 K 的转置")
    return value
