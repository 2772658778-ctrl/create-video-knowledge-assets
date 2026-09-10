from __future__ import annotations

from datetime import timedelta

import srt

from vka.models import Evidence


SCHEMA_VERSION = "1.0"


def parse_srt_as_evidence(srt_text: str, acquisition: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    try:
        for subtitle in srt.parse(srt_text):
            content = _normalize_content(subtitle.content)
            if not content:
                continue

            start_ms = _timedelta_to_ms(subtitle.start)
            end_ms = _timedelta_to_ms(subtitle.end)
            if end_ms <= start_ms:
                raise ValueError(
                    f"invalid subtitle time span for subtitle {subtitle.index}: "
                    "end_ms must be greater than start_ms"
                )

            evidence_number = len(rows) + 1
            row: dict[str, object] = {
                "evidence_id": f"tr-{evidence_number:06d}",
                "origin": "video",
                "modality": "transcript",
                "spans": [{"start_ms": start_ms, "end_ms": end_ms}],
                "content": content,
                "acquisition": acquisition,
                "schema_version": SCHEMA_VERSION,
            }
            Evidence.model_validate(row)
            rows.append(row)
    except srt.SRTParseError as exc:
        raise ValueError(f"invalid SRT: {exc}") from exc
    return rows


def whisper_command(audio_path: str, output_dir: str, model: str = "medium") -> list[str]:
    return [
        "whisper",
        audio_path,
        "--model",
        model,
        "--language",
        "zh",
        "--output_format",
        "srt",
        "--output_dir",
        output_dir,
    ]


def _normalize_content(content: str) -> str:
    return " ".join(content.split())


def _timedelta_to_ms(value: timedelta) -> int:
    return ((value.days * 24 * 60 * 60 + value.seconds) * 1000) + (value.microseconds // 1000)
