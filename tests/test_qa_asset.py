import json
from pathlib import Path

import pytest

from vka.qa_asset import qa_asset_fingerprint, validate_qa_asset
from vka.store import AssetStore


def _qa_asset(tmp_path: Path, *, course_notes: bool = False) -> AssetStore:
    asset = AssetStore.create(
        tmp_path / "assets", "asset-001", {"kind": "bilibili", "bvid": "BV1test"}
    )
    metadata = asset.root / "source" / "metadata.json"
    metadata.write_text('{"title":"Lesson"}\n', encoding="utf-8")
    records = asset.write_jsonl("evidence/records.jsonl", [{"evidence_id": "ev-1"}])
    units = asset.write_jsonl("knowledge/units.jsonl", [{"unit_id": "ku-1"}])
    relations = asset.write_jsonl(
        "knowledge/relations.jsonl", [{"relation_id": "rel-1"}]
    )
    synthesis = asset.root / "knowledge" / "synthesis.json"
    synthesis.write_text('{"video_summary":"Lesson"}\n', encoding="utf-8")
    asset.complete_stage("source", [metadata])
    asset.complete_stage("evidence", [records])
    asset.complete_stage("knowledge", [units, relations, synthesis])

    if course_notes:
        outline = asset.root / "knowledge" / "teaching_outline.json"
        outline.write_text('{"sections":[{"title":"Lesson"}]}\n', encoding="utf-8")
        document = asset.root / "views" / "course-notes" / "document.json"
        document.parent.mkdir(parents=True, exist_ok=True)
        document.write_text('{"title":"Lesson","blocks":[]}\n', encoding="utf-8")
    return asset


def test_validate_qa_asset_reports_missing_knowledge_graph_files(tmp_path: Path) -> None:
    asset = _qa_asset(tmp_path)
    (asset.root / "knowledge" / "relations.jsonl").unlink()
    (asset.root / "knowledge" / "synthesis.json").unlink()

    errors = validate_qa_asset(asset, profile_id="general-deep")

    assert "required QA file is missing: knowledge/relations.jsonl" in errors
    assert "required QA file is missing: knowledge/synthesis.json" in errors


def test_qa_asset_fingerprint_ignores_deleted_remote_video(tmp_path: Path) -> None:
    asset = _qa_asset(tmp_path)
    remote_video = asset.root / "source" / "video" / "remote.mp4"
    remote_video.parent.mkdir(parents=True)
    remote_video.write_bytes(b"downloaded video")
    asset.complete_stage("source", [asset.root / "source" / "metadata.json", remote_video])

    before = qa_asset_fingerprint(asset)
    remote_video.unlink()

    assert qa_asset_fingerprint(asset) == before
    assert "source/video/remote.mp4" not in before


def test_course_notes_requires_outline_and_document(tmp_path: Path) -> None:
    asset = _qa_asset(tmp_path)

    errors = validate_qa_asset(asset)

    assert "required QA file is missing: knowledge/teaching_outline.json" in errors
    assert "required QA file is missing: views/course-notes/document.json" in errors


def test_malformed_manifest_records_fail_explicitly(tmp_path: Path) -> None:
    asset = _qa_asset(tmp_path)
    manifest_path = asset.root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["stages"]["knowledge"]["outputs"] = {"not": "a list"}
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="knowledge stage outputs must be a list"):
        validate_qa_asset(asset, profile_id="general-deep")
    with pytest.raises(ValueError, match="knowledge stage outputs must be a list"):
        qa_asset_fingerprint(asset)


def test_validate_qa_asset_requires_required_files_to_be_registered(tmp_path: Path) -> None:
    asset = _qa_asset(tmp_path)
    manifest_path = asset.root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["stages"]["evidence"]["outputs"] = []
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    errors = validate_qa_asset(asset, profile_id="general-deep")

    assert "P4 requires evidence/records.jsonl to be registered in evidence stage outputs" in errors


@pytest.mark.parametrize("path", ["source/video/../metadata.json", "../source/metadata.json"])
def test_qa_asset_rejects_noncanonical_registered_output_paths(tmp_path: Path, path: str) -> None:
    asset = _qa_asset(tmp_path)
    manifest_path = asset.root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["stages"]["source"]["outputs"][0]["path"] = path
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="source output path must be a canonical asset-relative path"):
        validate_qa_asset(asset, profile_id="general-deep")
    with pytest.raises(ValueError, match="source output path must be a canonical asset-relative path"):
        qa_asset_fingerprint(asset)


def test_qa_asset_fingerprint_rejects_nonstandard_sha256(tmp_path: Path) -> None:
    asset = _qa_asset(tmp_path)
    manifest_path = asset.root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["stages"]["source"]["outputs"][0]["sha256"] = "not-a-sha256"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="source output sha256 must be a 64-character lowercase hexadecimal string"):
        qa_asset_fingerprint(asset)


def test_qa_asset_rejects_backslash_output_paths_before_platform_parsing(tmp_path: Path) -> None:
    asset = _qa_asset(tmp_path)
    manifest_path = asset.root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["stages"]["source"]["outputs"][0]["path"] = "source\\metadata.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="source output path must use POSIX separators"):
        qa_asset_fingerprint(asset)


def test_qa_asset_fingerprint_rejects_uppercase_sha256(tmp_path: Path) -> None:
    asset = _qa_asset(tmp_path)
    manifest_path = asset.root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["stages"]["source"]["outputs"][0]["sha256"] = "A" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="source output sha256 must be a 64-character lowercase hexadecimal string"):
        qa_asset_fingerprint(asset)


def test_qa_asset_fingerprint_rejects_symlinked_asset_root(tmp_path: Path) -> None:
    asset = _qa_asset(tmp_path)
    linked_root = tmp_path / "linked-asset"
    try:
        linked_root.symlink_to(asset.root, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symlinks are unavailable: {exc}")

    with pytest.raises(ValueError, match="asset root must not be a symlink or junction"):
        qa_asset_fingerprint(linked_root)
