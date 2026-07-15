import json
from pathlib import Path

import pytest

from vka.lifecycle import execute_l2_cleanup, plan_l2_cleanup, verify_asset
from vka.store import AssetStore
from vka_cli import main


def completed_asset_with_selected_frame(tmp_path: Path) -> tuple[AssetStore, Path]:
    external_video = tmp_path / "original.mp4"
    external_video.write_bytes(b"original local video")
    asset = AssetStore.create(
        tmp_path / "assets",
        "asset-001",
        {"kind": "local_video", "original_path": str(external_video.resolve())},
    )
    timeline = asset.write_jsonl("evidence/timeline.jsonl", [{"evidence_id": "ev-1"}])
    units = asset.write_jsonl("knowledge/units.jsonl", [{"unit_id": "ku-1"}])
    document = asset.root / "views" / "course-notes" / "document.json"
    document.parent.mkdir(parents=True)
    document.write_text(
        json.dumps(
            {
                "profile_id": "course-notes",
                "title": "Lesson",
                "blocks": [
                    {
                        "kind": "image",
                        "image_path": "evidence/frames/selected.jpg",
                        "knowledge_refs": ["ku-1"],
                        "evidence_refs": ["ev-1"],
                        "source_spans": [{"start_ms": 0, "end_ms": 1000}],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    selected = asset.root / "evidence" / "frames" / "selected.jpg"
    selected.parent.mkdir(parents=True)
    selected.write_bytes(b"selected image")
    candidate = asset.root / "evidence" / "frames" / "candidate.jpg"
    candidate.write_bytes(b"unselected image")
    raw = asset.root / "source" / "subtitles" / "lesson.srt"
    raw.parent.mkdir(parents=True)
    raw.write_text("1\n00:00:00,000 --> 00:00:01,000\nlesson\n", encoding="utf-8")
    repaired = asset.write_jsonl("evidence/timeline.raw.jsonl", [{"evidence_id": "raw-1"}])
    audio = asset.root / "source" / "audio" / "lesson.wav"
    audio.parent.mkdir(parents=True)
    audio.write_bytes(b"rebuildable audio")
    asset.complete_stage("evidence", [timeline, repaired])
    asset.complete_stage("knowledge", [units])
    asset.complete_stage("views/course-notes", [document])
    return asset, external_video


def test_completed_asset_with_selected_frame_returns_asset_and_external_video(tmp_path: Path) -> None:
    asset, external_video = completed_asset_with_selected_frame(tmp_path)

    assert asset.root.is_dir()
    assert external_video.is_file()
    assert external_video.parent != asset.root


def test_plan_l2_cleanup_keeps_evidence_and_selected_frame_without_deleting_external_video(
    tmp_path: Path,
) -> None:
    asset, external_video = completed_asset_with_selected_frame(tmp_path)

    plan = plan_l2_cleanup(asset)

    assert "evidence/timeline.jsonl" in {entry["path"] for entry in plan["keep"]}
    assert "evidence/frames/selected.jpg" in {entry["path"] for entry in plan["keep"]}
    assert "evidence/frames/candidate.jpg" in plan["delete"]
    assert str(external_video) not in plan["delete"]

    execute_l2_cleanup(asset, plan)

    assert external_video.is_file()
    assert not (asset.root / "evidence" / "frames" / "candidate.jpg").exists()
    manifest = json.loads((asset.root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["retention"]["level"] == "L2"
    assert "evidence/frames/candidate.jpg" in manifest["retention"]["last_cleanup"]["deleted"]
    assert "source/audio/lesson.wav" in manifest["retention"]["last_cleanup"]["deleted"]


def test_completed_asset_tampered_evidence_marks_dependent_stages_stale(tmp_path: Path) -> None:
    asset, _ = completed_asset_with_selected_frame(tmp_path)
    timeline = asset.root / "evidence" / "timeline.jsonl"
    timeline.write_text('{"evidence_id":"tampered"}\n', encoding="utf-8")

    assert asset.resume_status() == {
        "evidence": "invalid",
        "knowledge": "stale",
        "views/course-notes": "stale",
    }


def test_verify_asset_checks_hashes_jsonl_and_document_image_references(tmp_path: Path) -> None:
    asset, _ = completed_asset_with_selected_frame(tmp_path)
    selected = asset.root / "evidence" / "frames" / "selected.jpg"
    selected.unlink()

    report = verify_asset(asset.root)

    assert report["valid"] is False
    assert "document image_path does not exist: evidence/frames/selected.jpg" in report["errors"]


def test_l2_cleanup_rejects_unsafe_or_incomplete_assets_without_partial_delete(tmp_path: Path) -> None:
    asset, _ = completed_asset_with_selected_frame(tmp_path)
    candidate = asset.root / "evidence" / "frames" / "candidate.jpg"
    manifest_path = asset.root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["stages"]["evidence"]["outputs"][0].pop("sha256")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="sha256"):
        plan_l2_cleanup(asset)

    assert candidate.is_file()


def test_l2_cleanup_rejects_incomplete_asset_without_deleting_anything(tmp_path: Path) -> None:
    asset = AssetStore.create(tmp_path, "asset-001", {"kind": "local_video"})
    timeline = asset.write_jsonl("evidence/timeline.jsonl", [{"evidence_id": "ev-1"}])
    candidate = asset.root / "evidence" / "frames" / "candidate.jpg"
    candidate.parent.mkdir(parents=True)
    candidate.write_bytes(b"candidate")
    asset.complete_stage("evidence", [timeline])

    with pytest.raises(ValueError, match="incomplete"):
        plan_l2_cleanup(asset)

    assert candidate.is_file()


def test_l2_cleanup_refuses_modified_plan_that_would_delete_a_referenced_frame(tmp_path: Path) -> None:
    asset, _ = completed_asset_with_selected_frame(tmp_path)
    selected = asset.root / "evidence" / "frames" / "selected.jpg"
    plan = plan_l2_cleanup(asset)
    malicious = dict(plan)
    malicious["delete"] = ["evidence/frames/selected.jpg"]

    with pytest.raises(ValueError, match="stale or was modified"):
        execute_l2_cleanup(asset, malicious)

    assert selected.is_file()


def test_l2_cleanup_keeps_windows_style_document_image_reference(tmp_path: Path) -> None:
    asset, _ = completed_asset_with_selected_frame(tmp_path)
    document = asset.root / "views" / "course-notes" / "document.json"
    payload = json.loads(document.read_text(encoding="utf-8"))
    payload["blocks"][0]["image_path"] = "evidence\\frames\\candidate.jpg"
    document.write_text(json.dumps(payload), encoding="utf-8")
    asset.complete_stage("views/course-notes", [document])

    plan = plan_l2_cleanup(asset)

    assert "evidence/frames/candidate.jpg" in {entry["path"] for entry in plan["keep"]}
    assert "evidence/frames/candidate.jpg" not in plan["delete"]


def test_l2_cleanup_keeps_completed_source_outputs_and_preserves_asset_validity(tmp_path: Path) -> None:
    asset, _ = completed_asset_with_selected_frame(tmp_path)
    audio = asset.root / "source" / "audio" / "lesson.wav"
    remote_video = asset.root / "source" / "video" / "download.mp4"
    remote_video.parent.mkdir(parents=True)
    remote_video.write_bytes(b"downloaded remote video")
    manifest = json.loads((asset.root / "manifest.json").read_text(encoding="utf-8"))
    manifest["source"] = {"kind": "bilibili", "bvid": "BV1xx"}
    (asset.root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    asset.complete_stage("source", [audio, remote_video])

    plan = plan_l2_cleanup(asset)

    kept = {entry["path"] for entry in plan["keep"]}
    assert {"source/audio/lesson.wav", "source/video/download.mp4"} <= kept
    assert "source/audio/lesson.wav" not in plan["delete"]
    assert "source/video/download.mp4" not in plan["delete"]

    execute_l2_cleanup(asset, plan)

    assert verify_asset(asset)["valid"] is True
    assert asset.resume_status()["source"] == "ready"


@pytest.mark.parametrize("unsafe_path", ["../outside.jsonl", "{external}"])
def test_execute_l2_cleanup_rejects_manifest_paths_outside_asset_without_deleting_candidates(
    tmp_path: Path, unsafe_path: str
) -> None:
    asset, _ = completed_asset_with_selected_frame(tmp_path)
    candidate = asset.root / "evidence" / "frames" / "candidate.jpg"
    audio = asset.root / "source" / "audio" / "lesson.wav"
    external = tmp_path / "outside.jsonl"
    external.write_text("{}\n", encoding="utf-8")
    manifest_path = asset.root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["stages"]["evidence"]["outputs"][0]["path"] = unsafe_path.format(external=external)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ValueError, match="asset cannot be cleaned"):
        execute_l2_cleanup(asset)

    assert candidate.is_file()
    assert audio.is_file()


def test_execute_l2_cleanup_rejects_asset_symlink_without_partial_deletion(tmp_path: Path) -> None:
    asset, _ = completed_asset_with_selected_frame(tmp_path)
    audio = asset.root / "source" / "audio" / "lesson.wav"
    external = tmp_path / "external-frame.jpg"
    external.write_bytes(b"external")
    linked = asset.root / "evidence" / "frames" / "linked.jpg"
    try:
        linked.symlink_to(external)
    except OSError:
        pytest.skip("symlink creation is unavailable on this platform")

    with pytest.raises(ValueError, match="asset cannot be cleaned"):
        execute_l2_cleanup(asset)

    assert linked.is_symlink()
    assert audio.is_file()
    assert external.is_file()


def test_cli_verify_and_cleanup_use_explicit_apply(tmp_path: Path, capsys) -> None:
    asset, _ = completed_asset_with_selected_frame(tmp_path)
    candidate = asset.root / "evidence" / "frames" / "candidate.jpg"

    assert main(["verify-asset", "--asset", str(asset.root)]) == 0
    assert json.loads(capsys.readouterr().out)["valid"] is True
    assert main(["cleanup-l2", "--asset", str(asset.root), "--dry-run"]) == 0
    dry_run = json.loads(capsys.readouterr().out)
    assert "evidence/frames/candidate.jpg" in dry_run["delete"]
    assert candidate.is_file()

    assert main(["cleanup-l2", "--asset", str(asset.root), "--apply"]) == 0
    assert not candidate.exists()
