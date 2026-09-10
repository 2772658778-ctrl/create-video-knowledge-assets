import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

from vka.store import AssetStore


def test_asset_store_creates_manifest_and_standard_directories(tmp_path: Path) -> None:
    store = AssetStore.create(tmp_path, "asset-001", {"source_url": "https://example.test/video"})
    assert (store.root / "manifest.json").is_file()
    assert all(
        (store.root / name).is_dir()
        for name in ("source", "evidence", "knowledge", "views", "index", "outputs", "logs")
    )


def test_asset_store_manifest_records_asset_identity_and_source(tmp_path: Path) -> None:
    source = {"source_url": "https://example.test/video"}
    store = AssetStore.create(tmp_path, "asset-001", source)

    manifest = json.loads((store.root / "manifest.json").read_text(encoding="utf-8"))

    assert store.root == (tmp_path / "asset-001").resolve()
    assert manifest["asset_id"] == "asset-001"
    assert manifest["schema_version"] == "1.1"
    assert manifest["source"] == source
    assert manifest["input"] == source
    assert manifest["config"] == {}
    assert manifest["tool_versions"] == {}
    assert manifest["stages"] == {}
    assert isinstance(manifest["created_at"], str)


def test_asset_store_rejects_existing_manifest_without_clearing_stages(tmp_path: Path) -> None:
    asset_root = tmp_path / "asset-001"
    asset_root.mkdir()
    manifest_path = asset_root / "manifest.json"
    existing_manifest = {
        "asset_id": "asset-001",
        "schema_version": "1.0",
        "source": {"source_url": "https://example.test/video"},
        "created_at": "2026-07-11T00:00:00+00:00",
        "stages": {"evidence": {"outputs": [{"path": "evidence/transcript.jsonl", "sha256": "abc"}]}},
    }
    manifest_path.write_text(json.dumps(existing_manifest), encoding="utf-8")

    with pytest.raises(FileExistsError, match="asset already exists"):
        AssetStore.create(tmp_path, "asset-001", {"source_url": "https://example.test/other"})

    assert json.loads(manifest_path.read_text(encoding="utf-8")) == existing_manifest


def test_asset_store_rejects_second_create_for_same_asset_id(tmp_path: Path) -> None:
    AssetStore.create(tmp_path, "asset-001", {"source_url": "https://example.test/video"})

    with pytest.raises(FileExistsError, match="asset already exists"):
        AssetStore.create(tmp_path, "asset-001", {"source_url": "https://example.test/other"})


def test_write_jsonl_writes_utf8_json_lines(tmp_path: Path) -> None:
    store = AssetStore.create(tmp_path, "asset-001", {"source_url": "https://example.test/video"})

    path = store.write_jsonl(
        "knowledge/units.jsonl",
        [{"unit_id": "ku-001", "statement": "注意力机制"}, {"unit_id": "ku-002", "tags": ["中文"]}],
    )

    raw = path.read_text(encoding="utf-8")
    assert "注意力机制" in raw
    assert [json.loads(line) for line in raw.splitlines()] == [
        {"unit_id": "ku-001", "statement": "注意力机制"},
        {"unit_id": "ku-002", "tags": ["中文"]},
    ]


def test_complete_stage_records_relative_path_sha256_and_schema_version(tmp_path: Path) -> None:
    store = AssetStore.create(tmp_path, "asset-001", {"source_url": "https://example.test/video"})
    output = store.write_jsonl("evidence/transcript.jsonl", [{"evidence_id": "tr-000001"}])

    store.complete_stage("evidence", [output], schema_version="1.1")

    manifest = json.loads((store.root / "manifest.json").read_text(encoding="utf-8"))
    stage_output = manifest["stages"]["evidence"]["outputs"][0]
    assert stage_output["path"] == "evidence/transcript.jsonl"
    assert stage_output["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    assert manifest["stages"]["evidence"]["schema_version"] == "1.1"


def test_completed_stage_requires_matching_schema_and_output_hash(tmp_path: Path) -> None:
    store = AssetStore.create(tmp_path, "asset-001", {"kind": "local_video"})
    output = store.write_jsonl("knowledge/units.jsonl", [{"unit_id": "ku-1"}])
    store.complete_stage("knowledge", [output], schema_version="1.1")
    output.write_text('{"unit_id":"changed"}\n', encoding="utf-8")

    assert store.verify_stage("knowledge", schema_version="1.1") == [
        "knowledge/units.jsonl sha256 does not match manifest"
    ]


def test_verify_stage_reports_invalid_jsonl(tmp_path: Path) -> None:
    store = AssetStore.create(tmp_path, "asset-001", {"kind": "local_video"})
    output = store.write_jsonl("knowledge/units.jsonl", [{"unit_id": "ku-1"}])
    store.complete_stage("knowledge", [output], schema_version="1.1")
    output.write_text("not-json\n", encoding="utf-8")

    assert store.verify_stage("knowledge", schema_version="1.1") == [
        "knowledge/units.jsonl sha256 does not match manifest",
        "knowledge/units.jsonl is not valid JSONL",
    ]


def test_verify_stage_reports_schema_mismatch(tmp_path: Path) -> None:
    store = AssetStore.create(tmp_path, "asset-001", {"kind": "local_video"})
    output = store.write_jsonl("knowledge/units.jsonl", [{"unit_id": "ku-1"}])
    store.complete_stage("knowledge", [output], schema_version="1.1")

    assert store.verify_stage("knowledge", schema_version="1.0") == [
        "knowledge schema_version does not match manifest"
    ]


@pytest.mark.parametrize("asset_id", ["", ".", "..", "asset/001", "asset\\001", str(Path.cwd())])
def test_asset_store_rejects_unsafe_asset_id(tmp_path: Path, asset_id: str) -> None:
    with pytest.raises(ValueError, match="asset_id"):
        AssetStore.create(tmp_path, asset_id, {"source_url": "https://example.test/video"})


def test_write_jsonl_rejects_paths_outside_asset_root(tmp_path: Path) -> None:
    store = AssetStore.create(tmp_path, "asset-001", {"source_url": "https://example.test/video"})

    with pytest.raises(ValueError, match="asset root"):
        store.write_jsonl("../x", [{"bad": True}])


def test_complete_stage_rejects_outputs_outside_asset_root(tmp_path: Path) -> None:
    store = AssetStore.create(tmp_path, "asset-001", {"source_url": "https://example.test/video"})
    external_output = tmp_path / "external.jsonl"
    external_output.write_text("{}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="asset root"):
        store.complete_stage("external", [external_output])


def test_complete_stage_refuses_to_modify_legacy_manifest(tmp_path: Path) -> None:
    asset_root = tmp_path / "asset-001"
    asset_root.mkdir()
    legacy_manifest = {
        "asset_id": "asset-001",
        "schema_version": "1.0",
        "stages": {},
    }
    manifest_path = asset_root / "manifest.json"
    manifest_path.write_text(json.dumps(legacy_manifest), encoding="utf-8")
    output = asset_root / "knowledge.jsonl"
    output.write_text('{"unit_id":"ku-1"}\n', encoding="utf-8")

    with pytest.raises(ValueError, match="only 1.1 manifests can be modified"):
        AssetStore(asset_root).complete_stage("knowledge", [output], schema_version="1.1")

    assert json.loads(manifest_path.read_text(encoding="utf-8")) == legacy_manifest


def test_verify_stage_reports_invalid_manifest_json(tmp_path: Path) -> None:
    asset_root = tmp_path / "asset-001"
    asset_root.mkdir()
    (asset_root / "manifest.json").write_text("not-json", encoding="utf-8")

    assert AssetStore(asset_root).verify_stage("knowledge", schema_version="1.1") == [
        "manifest.json is not valid JSON"
    ]


def test_verify_stage_reports_missing_manifest(tmp_path: Path) -> None:
    asset_root = tmp_path / "asset-001"
    asset_root.mkdir()

    assert AssetStore(asset_root).verify_stage("knowledge", schema_version="1.1") == [
        "manifest.json is missing"
    ]


def test_verify_stage_reports_invalid_manifest_utf8(tmp_path: Path) -> None:
    asset_root = tmp_path / "asset-001"
    asset_root.mkdir()
    (asset_root / "manifest.json").write_bytes(b"\xff")

    assert AssetStore(asset_root).verify_stage("knowledge", schema_version="1.1") == [
        "manifest.json is not valid UTF-8"
    ]


def test_verify_stage_reports_non_object_manifest(tmp_path: Path) -> None:
    asset_root = tmp_path / "asset-001"
    asset_root.mkdir()
    (asset_root / "manifest.json").write_text("[]", encoding="utf-8")

    assert AssetStore(asset_root).verify_stage("knowledge", schema_version="1.1") == [
        "manifest.json must be an object"
    ]


@pytest.mark.parametrize(
    ("manifest", "expected_error"),
    [
        (
            {"asset_id": "asset-001", "stages": {"knowledge": {"schema_version": "1.1", "outputs": []}}},
            "manifest schema_version is missing",
        ),
        (
            {
                "asset_id": "asset-001",
                "schema_version": 1.1,
                "stages": {"knowledge": {"schema_version": "1.1", "outputs": []}},
            },
            "manifest schema_version must be a string",
        ),
        (
            {
                "asset_id": "asset-001",
                "schema_version": "1.0",
                "stages": {"knowledge": {"schema_version": "1.1", "outputs": []}},
            },
            "manifest schema_version must be 1.1",
        ),
    ],
)
def test_verify_stage_reports_invalid_manifest_schema_version(
    tmp_path: Path, manifest: dict[str, object], expected_error: str
) -> None:
    asset_root = tmp_path / "asset-001"
    asset_root.mkdir()
    (asset_root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    assert AssetStore(asset_root).verify_stage("knowledge", schema_version="1.1") == [expected_error]


def test_resume_status_marks_only_dependent_profile_view_and_output_stale(tmp_path: Path) -> None:
    store = AssetStore.create(tmp_path, "asset-001", {"kind": "local_video"})
    evidence = store.write_jsonl("evidence/timeline.jsonl", [{"evidence_id": "ev-1"}])
    knowledge = store.write_jsonl("knowledge/units.jsonl", [{"unit_id": "ku-1"}])
    course_view = store.write_jsonl("views/course/document.jsonl", [{"block": 1}])
    other_view = store.write_jsonl("views/other/document.jsonl", [{"block": 2}])
    course_output = store.write_jsonl("outputs/course/document.jsonl", [{"rendered": True}])
    other_output = store.write_jsonl("outputs/other/document.jsonl", [{"rendered": True}])
    store.complete_stage("evidence", [evidence])
    store.complete_stage("knowledge", [knowledge])
    store.complete_stage("views/course", [course_view])
    store.complete_stage("views/other", [other_view])
    store.complete_stage("outputs/course", [course_output])
    store.complete_stage("outputs/other", [other_output])
    course_view.write_text('{"block":"changed"}\n', encoding="utf-8")

    assert store.resume_status() == {
        "evidence": "ready",
        "knowledge": "ready",
        "views/course": "invalid",
        "views/other": "ready",
        "outputs/course": "stale",
        "outputs/other": "ready",
    }


def test_complete_stage_rejects_legacy_manifest_tmp_link_without_touching_outside(
    tmp_path: Path,
) -> None:
    store = AssetStore.create(tmp_path, "asset-001", {"kind": "local_video"})
    output = store.write_jsonl("evidence/timeline.jsonl", [{"evidence_id": "ev-1"}])
    outside = tmp_path / "outside.json"
    outside.write_text('{"sentinel":"outside"}\n', encoding="utf-8")
    legacy_tmp = store.root / "manifest.json.tmp"
    try:
        legacy_tmp.symlink_to(outside)
    except OSError as exc:
        if os.name != "nt":
            pytest.skip(f"file symlinks unavailable: {exc}")
        outside_directory = tmp_path / "outside-directory"
        outside_directory.mkdir()
        junction = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(legacy_tmp), str(outside_directory)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if junction.returncode != 0:
            pytest.skip(f"file symlinks and junctions unavailable: {exc}")

    outside_before = outside.read_bytes()
    with pytest.raises(ValueError, match="manifest temporary path.*symlink|manifest temporary path.*asset root"):
        store.complete_stage("evidence", [output])

    assert outside.read_bytes() == outside_before
