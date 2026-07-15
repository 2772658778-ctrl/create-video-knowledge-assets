import json
from pathlib import Path

import pytest

import vka.qa_index as qa_index
from vka.qa_index import build_qa_index, lexical_terms, read_chunks, read_qa_index
from vka.qa_revision import register_knowledge_revision
from vka.store import AssetStore


def _complete_qa_asset(tmp_path: Path) -> AssetStore:
    asset = AssetStore.create(
        tmp_path / "assets", "asset-001", {"kind": "bilibili", "bvid": "BV1test"}
    )
    metadata = asset.root / "source" / "metadata.json"
    metadata.write_text('{"title":"Lesson"}\n', encoding="utf-8")
    records = asset.write_jsonl(
        "evidence/records.jsonl",
        [
            {
                "evidence_id": "ev-platform",
                "origin": "video",
                "modality": "transcript",
                "spans": [{"start_ms": 1000, "end_ms": 2000}],
                "content": "Use Colab to fine tune DeepSeek-R1.",
                "acquisition": "asr",
            },
            {
                "evidence_id": "ev-external",
                "origin": "external",
                "modality": "document",
                "spans": [{"start_ms": 3000, "end_ms": 4000}],
                "content": "External context.",
                "acquisition": "user_supplied",
            },
            {
                "evidence_id": "ev-generated",
                "origin": "generated",
                "modality": "document",
                "spans": [{"start_ms": 5000, "end_ms": 6000}],
                "content": "Generated artifact.",
                "acquisition": "pipeline",
            },
        ],
    )
    units = asset.write_jsonl(
        "knowledge/units.jsonl",
        [
            {
                "unit_id": "ku-platform",
                "type": "procedure",
                "title": "Colab fine tuning",
                "statement": "Use Colab to fine tune DeepSeek-R1.",
                "evidence_refs": ["ev-platform", "ev-external", "ev-generated"],
                "epistemic_status": "video_explicit",
                "importance": "high",
            },
            {
                "unit_id": "ku-external",
                "type": "concept",
                "title": "External only",
                "statement": "marketing-only wording",
                "evidence_refs": ["ev-platform"],
                "epistemic_status": "external_enrichment",
                "importance": "low",
            },
        ],
    )
    relations = asset.write_jsonl("knowledge/relations.jsonl", [{"relation_id": "rel-1"}])
    synthesis = asset.root / "knowledge" / "synthesis.json"
    synthesis.write_text('{"video_summary":"Lesson"}\n', encoding="utf-8")
    outline = asset.root / "knowledge" / "teaching_outline.json"
    outline.write_text('{"sections": []}\n', encoding="utf-8")
    document = asset.root / "views" / "course-notes" / "document.json"
    document.parent.mkdir(parents=True, exist_ok=True)
    document.write_text(
        json.dumps(
            {
                "sections": [
                    {"title": "Introduction", "blocks": []},
                    {
                        "title": "Platform fine tuning",
                        "blocks": [
                            {
                                "kind": "paragraph",
                                "text": "marketing-only wording",
                                "knowledge_refs": ["ku-platform"],
                                "evidence_refs": ["ev-platform"],
                            }
                        ],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    asset.complete_stage("source", [metadata])
    asset.complete_stage("evidence", [records])
    asset.complete_stage("knowledge", [units, relations, synthesis])
    return asset


def _register_revision(asset: AssetStore, revision_id: str = "rev-001") -> None:
    revision = asset.root / "knowledge" / "revisions" / revision_id
    revision.mkdir(parents=True)
    (revision / "units.jsonl").write_text(
        json.dumps(
            {
                "unit_id": "revision-unit",
                "type": "procedure",
                "title": "Revision fine tuning",
                "statement": "Use Colab to fine tune DeepSeek-R1.",
                "evidence_refs": ["ev-platform"],
                "epistemic_status": "video_explicit",
                "importance": "high",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (revision / "relations.jsonl").write_text("", encoding="utf-8")
    (revision / "synthesis.json").write_text(
        json.dumps(
            {
                "video_summary": "Fine tuning in Colab.",
                "video_summary_refs": ["revision-unit"],
                "agent_extensions": [],
                "agent_extension_refs": ["revision-unit"],
                "evidence_refs": ["ev-platform"],
            }
        ),
        encoding="utf-8",
    )
    register_knowledge_revision(asset, revision_id)


def test_lexical_terms_keep_identifiers_and_chinese_bigrams() -> None:
    assert lexical_terms("用 Colab 微调 DeepSeek-R1")[:5] == [
        "colab",
        "deepseek",
        "r1",
        "用c",
        "co",
    ]


def test_index_never_indexes_document_only_prose(tmp_path: Path) -> None:
    asset = _complete_qa_asset(tmp_path)

    build_qa_index(asset, profile_id="course-notes")

    chunks = read_chunks(asset.root / "index" / "chunks.jsonl")
    assert [chunk["chunk_id"] for chunk in chunks] == ["ku:ku-platform"]
    assert "marketing-only wording" not in json.dumps(chunks, ensure_ascii=False)
    assert chunks[0]["source_spans"] == [{"start_ms": 1000, "end_ms": 2000}]
    assert chunks[0]["evidence_refs"] == ["ev-platform", "ev-external", "ev-generated"]
    assert chunks[0]["course_locations"] == [
        {"section_index": 2, "title": "Platform fine tuning"}
    ]


def test_index_manifest_skips_unchanged_rebuild(tmp_path: Path) -> None:
    asset = _complete_qa_asset(tmp_path)

    first = build_qa_index(asset)
    chunks_path = asset.root / "index" / "chunks.jsonl"
    before = chunks_path.stat().st_mtime_ns
    second = build_qa_index(asset)

    assert second == first
    assert chunks_path.stat().st_mtime_ns == before


def test_index_rejects_profiles_other_than_course_notes(tmp_path: Path) -> None:
    asset = _complete_qa_asset(tmp_path)

    with pytest.raises(ValueError, match="course-notes"):
        build_qa_index(asset, profile_id="enterprise-knowledge")


def test_revision_index_rejects_a_linked_artifact_directory_without_touching_target(
    tmp_path: Path,
) -> None:
    asset = _complete_qa_asset(tmp_path)
    _register_revision(asset)
    target = tmp_path / "outside-revision-index"
    target.mkdir()
    (target / "preserve.txt").write_text("preserve", encoding="utf-8")
    revision_index = asset.root / "index" / "revisions" / "rev-001"
    revision_index.parent.mkdir(parents=True)
    try:
        revision_index.symlink_to(target, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"directory symlinks are unavailable: {exc}")

    with pytest.raises(ValueError, match="revision index directory.*symlink"):
        build_qa_index(asset, knowledge_revision="rev-001")
    assert (target / "preserve.txt").read_text(encoding="utf-8") == "preserve"
    assert not (target / "chunks.jsonl").exists()


def test_mixed_index_generation_is_rejected_then_rebuilt(tmp_path: Path) -> None:
    asset = _complete_qa_asset(tmp_path)
    build_qa_index(asset)
    chunks_path = asset.root / "index" / "chunks.jsonl"
    chunks_path.write_text(chunks_path.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="QA index generation is incomplete or mixed"):
        read_qa_index(asset)

    manifest = build_qa_index(asset)
    loaded = read_qa_index(asset)

    assert loaded["manifest"] == manifest
    assert loaded["chunks"] == read_chunks(chunks_path)


def test_read_retries_when_index_manifest_changes_during_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    asset = _complete_qa_asset(tmp_path)
    manifest = build_qa_index(asset)
    index_manifest_path = asset.root / "index" / "index-manifest.json"
    original_read_bytes = qa_index._read_bytes
    changed = False

    def racing_read_bytes(path: Path) -> bytes:
        nonlocal changed
        value = original_read_bytes(path)
        if path == index_manifest_path and not changed:
            changed = True
            path.write_bytes(value + b"\n")
        return value

    monkeypatch.setattr(qa_index, "_read_bytes", racing_read_bytes)
    snapshot = read_qa_index(asset)

    assert changed
    assert snapshot["manifest"] == manifest
    connection = snapshot["sqlite_connection"]
    assert connection.execute("SELECT chunk_id FROM chunks").fetchall() == [("ku:ku-platform",)]
    connection.close()
