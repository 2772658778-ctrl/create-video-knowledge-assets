import json

import pytest

from vka.digest import build_timeline_digest
from vka_cli import main


def _row(evidence_id: str, start_ms: int, content: str, *, uncertain: bool = False) -> dict:
    quality = {"repair_status": "raw_preserved"}
    if uncertain:
        quality["uncertain"] = "true"
    return {
        "evidence_id": evidence_id,
        "origin": "video",
        "modality": "transcript",
        "spans": [{"start_ms": start_ms, "end_ms": start_ms + 2_000}],
        "content": content,
        "acquisition": "asr",
        "quality": quality,
        "schema_version": "1.0",
    }


ROWS = [
    _row("tr-000001", 0, "竹笋，中国人春日餐桌的主角"),
    _row("tr-000002", 2_500, "江南的腌笋、浙江的油焖笋"),
    _row("tr-000003", 130_000, "竹笋经过隆冬的蛰伏", uncertain=True),
]


def test_digest_keeps_identifiers_times_and_uncertainty() -> None:
    digest = build_timeline_digest(ROWS)

    assert "- 行数：3" in digest
    assert "覆盖时间：00:00:00–00:02:12" in digest
    assert "- tr-000001 00:00:00 竹笋，中国人春日餐桌的主角" in digest
    assert "- ⚠ tr-000003 00:02:10 竹笋经过隆冬的蛰伏" in digest
    assert "## 00:00:00–00:02:00" in digest
    assert "## 00:02:00–00:04:00" in digest


def test_digest_is_much_smaller_than_the_jsonl_timeline() -> None:
    jsonl = "\n".join(json.dumps(row, ensure_ascii=False) for row in ROWS)

    assert len(build_timeline_digest(ROWS)) < len(jsonl) / 2


def test_digest_rejects_empty_rows_and_bad_window() -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        build_timeline_digest([])
    with pytest.raises(ValueError, match="window_ms must be a positive integer"):
        build_timeline_digest(ROWS, window_ms=0)


def test_cli_timeline_digest_writes_the_reading_view(tmp_path, capsys) -> None:
    timeline = tmp_path / "timeline.jsonl"
    output = tmp_path / "timeline-digest.md"
    timeline.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in ROWS),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "timeline-digest",
            "--timeline",
            str(timeline),
            "--output",
            str(output),
        ]
    )

    assert exit_code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["rows"] == 3
    assert "tr-000002" in output.read_text(encoding="utf-8")
