import json
from pathlib import Path

import pytest

from vka.knowledge_gate import validate_asset_knowledge
from vka_cli import main


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def _transcript(evidence_id: str, *, uncertain: bool) -> dict:
    quality = {"repair_status": "repaired"}
    if uncertain:
        quality["uncertain"] = "true"
    return {
        "evidence_id": evidence_id,
        "origin": "video",
        "modality": "transcript",
        "spans": [{"start_ms": 0, "end_ms": 2_000}],
        "content": "字幕行",
        "acquisition": "asr",
        "quality": quality,
    }


def _frame(evidence_id: str) -> dict:
    return {
        "evidence_id": evidence_id,
        "origin": "video",
        "modality": "frame",
        "spans": [{"start_ms": 0, "end_ms": 2_000}],
        "content": "已直接检查的画面",
        "acquisition": "manual_review",
    }


def _metadata(evidence_id: str) -> dict:
    return {
        "evidence_id": evidence_id,
        "origin": "video",
        "modality": "metadata",
        "spans": [{"start_ms": 0, "end_ms": 2_000}],
        "content": "元数据",
        "acquisition": "yt-dlp metadata",
    }


def _unit(unit_id: str, status: str, evidence_refs: list[str]) -> dict:
    return {
        "unit_id": unit_id,
        "type": "claim",
        "title": "标题",
        "statement": "陈述",
        "evidence_refs": evidence_refs,
        "epistemic_status": status,
        "importance": "high",
    }


def _asset(tmp_path: Path, units: list[dict], records: list[dict]) -> Path:
    asset = tmp_path / "asset-001"
    _write_jsonl(asset / "evidence" / "timeline.jsonl", [_transcript("tr-000001", uncertain=True)])
    _write_jsonl(asset / "evidence" / "records.jsonl", records)
    _write_jsonl(asset / "knowledge" / "units.jsonl", units)
    _write_jsonl(
        asset / "knowledge" / "relations.jsonl",
        [
            {
                "relation_id": "kr-001",
                "source_unit_id": units[0]["unit_id"],
                "target_unit_id": units[-1]["unit_id"],
                "relation_type": "supports",
                "evidence_refs": [units[0]["evidence_refs"][0]],
                "schema_version": "1.1",
            }
        ],
    )
    (asset / "knowledge" / "synthesis.json").write_text(
        json.dumps(
            {
                "video_summary": "综合结论",
                "video_summary_refs": [units[0]["unit_id"]],
                "agent_extensions": [],
                "agent_extension_refs": [units[0]["unit_id"]],
                "evidence_refs": [units[0]["evidence_refs"][0]],
                "schema_version": "1.1",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return asset


def test_checked_frame_supports_a_video_explicit_unit(tmp_path: Path) -> None:
    asset = _asset(
        tmp_path,
        [_unit("ku-a", "video_explicit", ["tr-000001", "ev-frame-1"])],
        [_frame("ev-frame-1")],
    )

    report = validate_asset_knowledge(asset)

    assert report["valid"] is True
    assert report["counts"]["supporting_evidence"] == 1


def test_uncertain_transcripts_alone_cannot_support_video_explicit(tmp_path: Path) -> None:
    asset = _asset(
        tmp_path,
        [_unit("ku-a", "video_explicit", ["tr-000001"])],
        [_frame("ev-frame-1")],
    )

    report = validate_asset_knowledge(asset)

    assert report["valid"] is False
    assert any("no citation is checked content evidence" in error for error in report["errors"])


def test_provenance_only_evidence_cannot_support_video_explicit(tmp_path: Path) -> None:
    asset = _asset(
        tmp_path,
        [_unit("ku-a", "video_explicit", ["ev-metadata-1"])],
        [_metadata("ev-metadata-1")],
    )

    report = validate_asset_knowledge(asset)

    assert report["valid"] is False
    assert report["counts"]["supporting_evidence"] == 0


def test_agent_inference_may_rest_on_uncertain_transcripts(tmp_path: Path) -> None:
    asset = _asset(
        tmp_path,
        [_unit("ku-a", "agent_inference", ["tr-000001"])],
        [_frame("ev-frame-1")],
    )

    assert validate_asset_knowledge(asset)["valid"] is True


def test_missing_evidence_reference_is_reported(tmp_path: Path) -> None:
    asset = _asset(
        tmp_path,
        [_unit("ku-a", "agent_inference", ["tr-999999"])],
        [_frame("ev-frame-1")],
    )

    report = validate_asset_knowledge(asset)

    assert "ku-a references missing evidence tr-999999" in report["errors"]


def test_cli_validate_knowledge_reports_valid_asset(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    asset = _asset(
        tmp_path,
        [_unit("ku-a", "video_explicit", ["ev-frame-1"])],
        [_frame("ev-frame-1")],
    )

    exit_code = main(["validate-knowledge", "--asset", str(asset)])

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["valid"] is True
