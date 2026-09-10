"""Compact reading views of the canonical transcript timeline.

An agent that has to read the whole JSONL timeline pays for every schema field
on every row. The digest keeps the identifiers, the time ranges, and the text
that knowledge extraction actually needs, so the full JSONL stays the machine
contract and the digest becomes the reading surface.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


DEFAULT_WINDOW_MS = 120_000


def build_timeline_digest(
    rows: Sequence[Mapping[str, Any]],
    *,
    window_ms: int = DEFAULT_WINDOW_MS,
) -> str:
    if not rows:
        raise ValueError("timeline rows must not be empty")
    if window_ms <= 0:
        raise ValueError("window_ms must be a positive integer")

    entries = [_digest_entry(row) for row in rows]
    repaired = sum(1 for entry in entries if entry["repair_status"] == "repaired")
    uncertain = sum(1 for entry in entries if entry["uncertain"])
    starts = [entry["start_ms"] for entry in entries if entry["start_ms"] is not None]
    ends = [entry["end_ms"] for entry in entries if entry["end_ms"] is not None]

    lines = [
        "# 转录时间线速览",
        "",
        f"- 行数：{len(entries)}",
        f"- 覆盖时间：{_format_time(min(starts)) if starts else '未知'}"
        f"–{_format_time(max(ends)) if ends else '未知'}",
        f"- 已修订：{repaired} 行；保留原文：{len(entries) - repaired} 行",
        f"- 标记不确定：{uncertain} 行（下文以 ⚠ 开头）",
        "",
        "> 这是阅读视图；引用证据时请使用完整 `timeline.jsonl` 中的同一 `evidence_id`。",
        "",
    ]

    current_window: int | None = None
    for entry in entries:
        window = None if entry["start_ms"] is None else entry["start_ms"] // window_ms
        if window != current_window:
            if current_window is not None:
                lines.append("")
            lines.append(f"## {_window_label(window, window_ms)}")
            lines.append("")
            current_window = window
        lines.append(_format_entry(entry))

    return "\n".join(lines) + "\n"


def _digest_entry(row: Mapping[str, Any]) -> dict[str, Any]:
    evidence_id = row.get("evidence_id")
    if not isinstance(evidence_id, str) or not evidence_id:
        raise ValueError("timeline row evidence_id must be a non-empty string")
    content = row.get("content")
    if not isinstance(content, str) or not content.strip():
        raise ValueError(f"{evidence_id} content must be a non-empty string")

    start_ms: int | None = None
    end_ms: int | None = None
    spans = row.get("spans")
    if isinstance(spans, list) and spans and isinstance(spans[0], Mapping):
        start = spans[0].get("start_ms")
        end = spans[0].get("end_ms")
        if isinstance(start, int):
            start_ms = start
        if isinstance(end, int):
            end_ms = end

    quality = row.get("quality")
    quality = quality if isinstance(quality, Mapping) else {}
    return {
        "evidence_id": evidence_id,
        "start_ms": start_ms,
        "end_ms": end_ms,
        "content": " ".join(content.split()),
        "uncertain": quality.get("uncertain") == "true",
        "repair_status": quality.get("repair_status"),
    }


def _format_entry(entry: Mapping[str, Any]) -> str:
    marker = "⚠ " if entry["uncertain"] else ""
    start = entry["start_ms"]
    timestamp = _format_time(start) if isinstance(start, int) else "--:--:--"
    return f"- {marker}{entry['evidence_id']} {timestamp} {entry['content']}"


def _window_label(window: int | None, window_ms: int) -> str:
    if window is None:
        return "时间未知"
    return f"{_format_time(window * window_ms)}–{_format_time((window + 1) * window_ms)}"


def _format_time(milliseconds: int) -> str:
    total_seconds = milliseconds // 1000
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
