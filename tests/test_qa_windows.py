import json
import os
from pathlib import Path

import pytest

from vka.qa_windows import (
    MAX_CONTENT_BYTES,
    MAX_TOTAL_ITEMS,
    MAX_TRANSCRIPT_ITEMS,
    build_evidence_windows,
)
from vka.store import AssetStore


def _complete_asset(tmp_path: Path) -> AssetStore:
    asset = AssetStore.create(
        tmp_path / "assets", "asset-001", {"kind": "bilibili", "bvid": "BV1test"}
    )
    metadata = asset.root / "source" / "metadata.json"
    metadata.write_text('{"title":"Lesson"}\n', encoding="utf-8")
    records = asset.write_jsonl(
        "evidence/records.jsonl",
        [
            _evidence("ev-before", 0, 500, "outside left"),
            _evidence("ev-anchor", 10_000, 11_000, "anchor transcript"),
            {
                **_evidence("ev-frame", 10_250, 10_500, "frame caption"),
                "modality": "frame",
                "artifact_ref": "evidence/frames/frame-001.jpg",
                "quality": {"review": "directly_inspected"},
            },
            _evidence("ev-near", 12_000, 13_000, "near transcript"),
            _evidence("ev-far", 99_000, 100_000, "unrelated transcript"),
            {
                "evidence_id": "ev-external",
                "origin": "external",
                "modality": "document",
                "content": "External document prose must stay out.",
                "spans": [],
                "acquisition": "user_supplied",
            },
            {
                "evidence_id": "ev-generated",
                "origin": "generated",
                "modality": "document",
                "content": "Generated prose must stay out.",
                "spans": [],
                "acquisition": "pipeline",
            },
        ],
    )
    units = asset.write_jsonl(
        "knowledge/units.jsonl",
        [
            {
                "unit_id": "ku-video",
                "type": "concept",
                "title": "Internal title",
                "statement": "Knowledge prose must stay out.",
                "evidence_refs": ["ev-anchor", "ev-frame", "ev-external", "ev-generated"],
                "epistemic_status": "video_explicit",
                "importance": "high",
            },
            {
                "unit_id": "ku-external",
                "type": "concept",
                "title": "External title",
                "statement": "External unit prose must stay out.",
                "evidence_refs": ["ev-anchor"],
                "epistemic_status": "external_enrichment",
                "importance": "low",
            },
            {
                "unit_id": "ku-unselected",
                "type": "concept",
                "title": "Unselected title",
                "statement": "Unselected knowledge prose must stay out.",
                "evidence_refs": ["ev-far"],
                "epistemic_status": "video_explicit",
                "importance": "low",
            },
        ],
    )
    relations = asset.write_jsonl(
        "knowledge/relations.jsonl",
        [
            {
                "relation_id": "rel-video",
                "source_unit_id": "ku-video",
                "target_unit_id": "ku-video",
                "relation_type": "explains",
                "evidence_refs": ["ev-anchor"],
            }
        ],
    )
    synthesis = asset.root / "knowledge" / "synthesis.json"
    synthesis.write_text('{"video_summary":"Lesson"}\n', encoding="utf-8")
    outline = asset.root / "knowledge" / "teaching_outline.json"
    outline.write_text('{"sections": []}\n', encoding="utf-8")
    document = asset.root / "views" / "course-notes" / "document.json"
    document.parent.mkdir(parents=True, exist_ok=True)
    document.write_text('{"prose":"Course document prose must stay out."}\n', encoding="utf-8")
    asset.complete_stage("source", [metadata])
    asset.complete_stage("evidence", [records])
    asset.complete_stage("knowledge", [units, relations, synthesis])
    return asset


def _evidence(evidence_id: str, start_ms: int, end_ms: int, content: str) -> dict[str, object]:
    return {
        "evidence_id": evidence_id,
        "origin": "video",
        "modality": "transcript",
        "content": content,
        "artifact_ref": "source/asr/audio.srt",
        "spans": [{"start_ms": start_ms, "end_ms": end_ms}],
        "acquisition": "asr",
    }


def test_windows_are_bounded_and_preserve_direct_frames(tmp_path: Path) -> None:
    asset = _complete_asset(tmp_path)

    published = build_evidence_windows(
        asset, ["ku-video"], context_ms=2_000, max_transcript_items=2
    )

    windows = published["windows"]
    assert isinstance(windows, list)
    assert len(windows) == 1
    window = windows[0]
    assert window["knowledge_id"] == "ku-video"
    assert window["anchor_evidence_refs"] == ["ev-anchor", "ev-frame"]
    assert window["evidence_refs"] == ["ev-anchor", "ev-frame", "ev-near"]
    assert [item["evidence_id"] for item in window["evidence"]] == [
        "ev-anchor",
        "ev-frame",
        "ev-near",
    ]
    assert sum(item["modality"] == "transcript" for item in window["evidence"]) == 2
    serialized = json.dumps(published, ensure_ascii=False)
    for forbidden in (
        "outside left",
        "unrelated transcript",
        "External document prose must stay out.",
        "Generated prose must stay out.",
        "Course document prose must stay out.",
        "Knowledge prose must stay out.",
    ):
        assert forbidden not in serialized
    assert window["source_spans"] == [
        {"start_ms": 10_000, "end_ms": 11_000},
        {"start_ms": 10_250, "end_ms": 10_500},
        {"start_ms": 12_000, "end_ms": 13_000},
    ]


def test_windows_require_an_explicit_retrieval_selection(tmp_path: Path) -> None:
    asset = _complete_asset(tmp_path)

    published = build_evidence_windows(asset, ["ku-video"])

    assert [window["knowledge_id"] for window in published["windows"]] == ["ku-video"]
    assert "ku-unselected" not in json.dumps(published, ensure_ascii=False)
    persisted = [
        json.loads(line)
        for line in (asset.root / "index" / "evidence-windows.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert [window["knowledge_id"] for window in persisted] == ["ku-video"]
    assert build_evidence_windows(asset, [])["windows"] == []
    with pytest.raises(ValueError, match="selected knowledge IDs"):
        build_evidence_windows(asset, ["ku-missing"])


def test_windows_include_only_direct_frames_as_non_transcript_attachments(tmp_path: Path) -> None:
    asset = _complete_asset(tmp_path)
    records_path = asset.root / "evidence" / "records.jsonl"
    rows = [json.loads(line) for line in records_path.read_text(encoding="utf-8").splitlines()]
    rows.extend(
        [
            {**_evidence("ev-audio", 10_100, 10_200, "audio must stay out"), "modality": "audio"},
            {**_evidence("ev-metadata", 10_100, 10_200, "metadata must stay out"), "modality": "metadata"},
            {**_evidence("ev-document", 10_100, 10_200, "document must stay out"), "modality": "document"},
            {**_evidence("ev-uninspected-frame", 10_100, 10_200, "uninspected frame must stay out"), "modality": "frame"},
        ]
    )
    records_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    units_path = asset.root / "knowledge" / "units.jsonl"
    units = [json.loads(line) for line in units_path.read_text(encoding="utf-8").splitlines()]
    units[0]["evidence_refs"].extend(
        ["ev-audio", "ev-metadata", "ev-document", "ev-uninspected-frame"]
    )
    units_path.write_text("".join(json.dumps(row) + "\n" for row in units), encoding="utf-8")
    asset.complete_stage("evidence", [records_path])
    asset.complete_stage(
        "knowledge",
        [units_path, asset.root / "knowledge" / "relations.jsonl", asset.root / "knowledge" / "synthesis.json"],
    )

    published = build_evidence_windows(asset, ["ku-video"])

    items = [item for window in published["windows"] for item in window["evidence"]]
    assert {item["modality"] for item in items} <= {"transcript", "frame"}
    assert all(
        item["evidence_id"]
        not in {"ev-audio", "ev-metadata", "ev-document", "ev-uninspected-frame"}
        for item in items
    )


def test_windows_partition_frames_and_enforce_item_and_content_caps(tmp_path: Path) -> None:
    asset = _complete_asset(tmp_path)
    records_path = asset.root / "evidence" / "records.jsonl"
    rows = [json.loads(line) for line in records_path.read_text(encoding="utf-8").splitlines()]
    frame_ids = [f"ev-frame-{index}" for index in range(6)]
    rows.extend(
        [
            {
                **_evidence(frame_id, 10_300 + index * 10, 10_305 + index * 10, f"frame {index}"),
                "modality": "frame",
                "quality": {"review": "directly_inspected"},
            }
            for index, frame_id in enumerate(frame_ids)
        ]
    )
    records_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    units_path = asset.root / "knowledge" / "units.jsonl"
    units = [json.loads(line) for line in units_path.read_text(encoding="utf-8").splitlines()]
    units[0]["evidence_refs"].extend(frame_ids)
    units_path.write_text("".join(json.dumps(row) + "\n" for row in units), encoding="utf-8")
    asset.complete_stage("evidence", [records_path])
    asset.complete_stage(
        "knowledge",
        [units_path, asset.root / "knowledge" / "relations.jsonl", asset.root / "knowledge" / "synthesis.json"],
    )

    published = build_evidence_windows(
        asset, ["ku-video"], max_total_items=3, max_content_bytes=64
    )

    windows = published["windows"]
    assert len(windows) > 1
    assert all(len(window["evidence"]) <= 3 for window in windows)
    assert all(
        sum(len(item["content"].encode("utf-8")) for item in window["evidence"]) <= 64
        for window in windows
    )
    frame_occurrences = [
        item["evidence_id"]
        for window in windows
        for item in window["evidence"]
        if item["modality"] == "frame"
    ]
    assert sorted(frame_occurrences) == sorted(["ev-frame", *frame_ids])
    assert len(frame_occurrences) == len(set(frame_occurrences))
    with pytest.raises(ValueError, match="max_content_bytes"):
        build_evidence_windows(asset, ["ku-video"], max_content_bytes=1)


def test_windows_emit_a_shared_direct_frame_once_across_selected_units(
    tmp_path: Path,
) -> None:
    asset = _complete_asset(tmp_path)
    units_path = asset.root / "knowledge" / "units.jsonl"
    units = [json.loads(line) for line in units_path.read_text(encoding="utf-8").splitlines()]
    units[2]["unit_id"] = "ku-shared-frame"
    units[2]["evidence_refs"] = ["ev-near", "ev-frame"]
    units_path.write_text("".join(json.dumps(row) + "\n" for row in units), encoding="utf-8")
    asset.complete_stage(
        "knowledge",
        [
            units_path,
            asset.root / "knowledge" / "relations.jsonl",
            asset.root / "knowledge" / "synthesis.json",
        ],
    )

    published = build_evidence_windows(asset, ["ku-video", "ku-shared-frame"])

    windows = published["windows"]
    assert [window["knowledge_id"] for window in windows] == ["ku-shared-frame", "ku-video"]
    assert all("ev-frame" in window["anchor_evidence_refs"] for window in windows)
    assert [
        item["evidence_id"]
        for window in windows
        for item in window["evidence"]
        if item["evidence_id"] == "ev-frame"
    ] == ["ev-frame"]
    assert all(len(window["evidence"]) <= MAX_TOTAL_ITEMS for window in windows)


def test_windows_deterministic_reuse_and_fingerprint_rebuild(tmp_path: Path) -> None:
    asset = _complete_asset(tmp_path)

    first = build_evidence_windows(asset, ["ku-video"])
    windows_path = asset.root / "index" / "evidence-windows.jsonl"
    first_bytes = windows_path.read_bytes()
    first_mtime = windows_path.stat().st_mtime_ns
    second = build_evidence_windows(asset, ["ku-video"])

    assert second == first
    assert windows_path.read_bytes() == first_bytes
    assert windows_path.stat().st_mtime_ns == first_mtime

    records_path = asset.root / "evidence" / "records.jsonl"
    rows = [json.loads(line) for line in records_path.read_text(encoding="utf-8").splitlines()]
    rows[1]["content"] = "changed canonical anchor"
    records_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    asset.complete_stage("evidence", [records_path])

    rebuilt = build_evidence_windows(asset, ["ku-video"])
    assert rebuilt["qa_asset_fingerprint"] != first["qa_asset_fingerprint"]
    assert json.loads(windows_path.read_text(encoding="utf-8").splitlines()[0])["qa_asset_fingerprint"] == rebuilt["qa_asset_fingerprint"]


def test_windows_rebuild_a_forged_same_fingerprint_cache(tmp_path: Path) -> None:
    asset = _complete_asset(tmp_path)
    expected = build_evidence_windows(asset, ["ku-video"])
    windows_path = asset.root / "index" / "evidence-windows.jsonl"
    forged = [json.loads(line) for line in windows_path.read_text(encoding="utf-8").splitlines()]
    forged[0]["evidence"][0]["content"] = "forged transcript"
    windows_path.write_text("".join(json.dumps(window) + "\n" for window in forged), encoding="utf-8")

    assert build_evidence_windows(asset, ["ku-video"]) == expected
    assert [json.loads(line) for line in windows_path.read_text(encoding="utf-8").splitlines()] == expected["windows"]


def test_windows_reject_malformed_or_unknown_canonical_refs(tmp_path: Path) -> None:
    asset = _complete_asset(tmp_path)
    units_path = asset.root / "knowledge" / "units.jsonl"
    units = [json.loads(line) for line in units_path.read_text(encoding="utf-8").splitlines()]
    units[0]["evidence_refs"] = ["ev-missing"]
    units_path.write_text("".join(json.dumps(row) + "\n" for row in units), encoding="utf-8")
    asset.complete_stage(
        "knowledge",
        [units_path, asset.root / "knowledge" / "relations.jsonl", asset.root / "knowledge" / "synthesis.json"],
    )
    with pytest.raises(ValueError, match="unknown evidence"):
        build_evidence_windows(asset, ["ku-video"])

    asset = _complete_asset(tmp_path / "malformed")
    records_path = asset.root / "evidence" / "records.jsonl"
    rows = [json.loads(line) for line in records_path.read_text(encoding="utf-8").splitlines()]
    rows[0].pop("acquisition")
    records_path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    asset.complete_stage("evidence", [records_path])
    with pytest.raises(ValueError, match="evidence record 1 is invalid"):
        build_evidence_windows(asset, ["ku-video"])


def test_windows_reject_a_linked_destination_without_touching_target(tmp_path: Path) -> None:
    asset = _complete_asset(tmp_path)
    destination = asset.root / "index" / "evidence-windows.jsonl"
    outside = tmp_path / "outside.jsonl"
    outside.write_text('{"preserve":true}\n', encoding="utf-8")
    try:
        destination.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"file symlinks are unavailable: {exc}")

    with pytest.raises(ValueError, match="windows destination.*symlink"):
        build_evidence_windows(asset, ["ku-video"])
    assert outside.read_text(encoding="utf-8") == '{"preserve":true}\n'


def test_maximum_transcript_items_must_be_positive() -> None:
    assert MAX_TRANSCRIPT_ITEMS > 0
    with pytest.raises(ValueError, match="max_transcript_items"):
        build_evidence_windows(Path("missing"), [], max_transcript_items=0)
    assert MAX_TOTAL_ITEMS > 0
    assert MAX_CONTENT_BYTES > 0


def test_windows_reject_profiles_other_than_course_notes(tmp_path: Path) -> None:
    asset = _complete_asset(tmp_path)

    with pytest.raises(ValueError, match="course-notes"):
        build_evidence_windows(asset, ["ku-video"], profile_id="enterprise-knowledge")
