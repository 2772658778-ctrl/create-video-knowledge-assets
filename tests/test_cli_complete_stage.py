import hashlib
import json
from pathlib import Path

import pytest

from vka.store import AssetStore
from vka_cli import main


def _asset(tmp_path: Path) -> Path:
    store = AssetStore.create(tmp_path, "asset-001", {"source_url": "https://example.test/video"})
    return store.root


def test_complete_stage_records_hashes_without_a_hand_written_script(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    asset_root = _asset(tmp_path)
    timeline = asset_root / "evidence" / "timeline.jsonl"
    timeline.write_text('{"evidence_id": "tr-000001"}\n', encoding="utf-8")

    exit_code = main(
        [
            "complete-stage",
            "--asset",
            str(asset_root),
            "--stage",
            "evidence",
            "--output",
            "evidence/timeline.jsonl",
        ]
    )

    assert exit_code == 0
    manifest = json.loads((asset_root / "manifest.json").read_text(encoding="utf-8"))
    recorded = manifest["stages"]["evidence"]
    assert recorded["schema_version"] == "1.1"
    assert recorded["outputs"] == [
        {
            "path": "evidence/timeline.jsonl",
            "sha256": hashlib.sha256(timeline.read_bytes()).hexdigest(),
        }
    ]
    assert json.loads(capsys.readouterr().out)["stage"] == "evidence"


def test_complete_stage_accepts_a_profile_view_stage(tmp_path: Path) -> None:
    asset_root = _asset(tmp_path)
    document = asset_root / "views" / "deep-article" / "document.json"
    document.parent.mkdir(parents=True, exist_ok=True)
    document.write_text('{"profile_id": "deep-article"}\n', encoding="utf-8")

    exit_code = main(
        [
            "complete-stage",
            "--asset",
            str(asset_root),
            "--stage",
            "views/deep-article",
            "--output",
            "views/deep-article/document.json",
        ]
    )

    assert exit_code == 0
    manifest = json.loads((asset_root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["stages"]["views/deep-article"]["outputs"][0]["path"] == (
        "views/deep-article/document.json"
    )


def test_complete_stage_rejects_an_unknown_stage_without_rewriting_the_manifest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    asset_root = _asset(tmp_path)
    before = (asset_root / "manifest.json").read_bytes()

    exit_code = main(
        [
            "complete-stage",
            "--asset",
            str(asset_root),
            "--stage",
            "../../outside",
            "--output",
            "evidence/timeline.jsonl",
        ]
    )

    assert exit_code == 1
    assert "unsupported stage name" in capsys.readouterr().err
    assert (asset_root / "manifest.json").read_bytes() == before


def test_complete_stage_reports_a_missing_output_without_a_traceback(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    asset_root = _asset(tmp_path)

    exit_code = main(
        [
            "complete-stage",
            "--asset",
            str(asset_root),
            "--stage",
            "evidence",
            "--output",
            "evidence/missing.jsonl",
        ]
    )

    assert exit_code == 1
    assert "failed to complete stage evidence" in capsys.readouterr().err
