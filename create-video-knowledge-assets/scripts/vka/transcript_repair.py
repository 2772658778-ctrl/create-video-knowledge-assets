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
) -> list[dict[str, object]]:
    """Return deterministic repair candidates for common ASR mistakes."""
    repairs: list[dict[str, object]] = []
    for row in timeline_rows:
        content = row.get("content")
        if not isinstance(content, str):
            continue

        repaired = content
        reasons: list[str] = []
        for wrong, right in COMMON_ASR_REPAIRS.items():
            if wrong in repaired:
                repaired = repaired.replace(wrong, right)
                reasons.append(f"{wrong} -> {right}")

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


def apply_transcript_repairs(
    timeline_rows: Sequence[Mapping[str, Any]],
    repairs: Sequence[Mapping[str, Any]],
) -> list[dict[str, object]]:
    repair_by_id = {_repair_id(repair): repair for repair in repairs}
    output: list[dict[str, object]] = []

    for row in timeline_rows:
        copied = dict(row)
        evidence_id = _evidence_id(copied)
        repair = repair_by_id.get(evidence_id)
        if repair is not None:
            original = copied.get("content")
            repaired = repair.get("repaired_content")
            if not isinstance(original, str) or not isinstance(repaired, str) or not repaired.strip():
                raise ValueError(f"{evidence_id} has invalid repair content")
            copied["content"] = repaired.strip()
            quality = dict(copied.get("quality") or {})
            quality["repair_status"] = "repaired"
            quality["repair_confidence"] = str(repair.get("confidence", "unknown"))
            if bool(repair.get("uncertain")):
                quality["uncertain"] = "true"
            copied["quality"] = quality
            copied["parent_ids"] = list(copied.get("parent_ids") or [])
            copied["original_content"] = original
            copied["repair_reason"] = str(repair.get("reason", ""))

        Evidence.model_validate(copied)
        output.append(copied)

    missing_ids = set(repair_by_id) - {_evidence_id(row) for row in timeline_rows}
    if missing_ids:
        raise ValueError(f"repairs reference missing evidence ids: {', '.join(sorted(missing_ids))}")

    return output


def _repair_id(repair: Mapping[str, Any]) -> str:
    evidence_id = repair.get("evidence_id")
    if not isinstance(evidence_id, str) or not evidence_id:
        raise ValueError("repair evidence_id must be a non-empty string")
    return evidence_id


def _evidence_id(row: Mapping[str, Any]) -> str:
    evidence_id = row.get("evidence_id")
    if not isinstance(evidence_id, str) or not evidence_id:
        raise ValueError("timeline row evidence_id must be a non-empty string")
    return evidence_id


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
